"""SQLite-backed cache for mod-scan results.

The first scan of a 300+ mod ETS2 install needs ~12 seconds because every
HashFS archive is partially extracted via sk-zk/Extractor. We cache the
parsed manifest + icon bytes keyed on ``(path, mtime, size)`` so the
second scan drops to milliseconds and only re-reads files the user has
actually changed.

Schema (``user_version=5``)::

    mod_cache(
        path TEXT PRIMARY KEY,
        mtime REAL NOT NULL,
        size INTEGER NOT NULL,
        format TEXT NOT NULL,
        manifest_json TEXT,
        error TEXT,
        icon_bytes BLOB,
        description TEXT,
        is_map INTEGER NOT NULL DEFAULT 0,
        scanned_at REAL NOT NULL
    )

For directory mod payloads ``size`` stores the number of immediate
children (the directory's own ``st_size`` does not change when a file
inside is edited).

The cache is opened in WAL mode with NORMAL sync so a concurrent scanner
process can read while a foreground GUI thread writes new entries.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_scanner import ScannedMod

SCHEMA_VERSION = 6
APP_DIR_NAME = "easy-scsmodmanager"
DB_FILE_NAME = "scan_cache.db"


@dataclass(frozen=True)
class CachedEntry:
    mod: ScannedMod
    icon_bytes: bytes | None
    scanned_at: float
    description: str | None = None


def default_cache_path() -> Path:
    """``$XDG_CACHE_HOME/easy-scsmodmanager/scan_cache.db`` or HOME fallback."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path(os.environ.get("HOME", "~")).expanduser() / ".cache"
    return base / APP_DIR_NAME / DB_FILE_NAME


class ScanCache:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._tune_pragmas()
        self._migrate()

    def get(self, scs_path: Path) -> CachedEntry | None:
        try:
            stat = scs_path.stat()
        except OSError:
            return None

        row = self._conn.execute(
            "SELECT * FROM mod_cache WHERE path = ?",
            (str(scs_path),),
        ).fetchone()
        if row is None:
            return None
        mtime, size = _cache_signature(scs_path, stat)
        if row["mtime"] != mtime or row["size"] != size:
            return None
        return _row_to_entry(row, scs_path)

    def put(
        self,
        scs_path: Path,
        mod: ScannedMod,
        icon_bytes: bytes | None = None,
        description: str | None = None,
    ) -> None:
        stat = scs_path.stat()
        mtime, size = _cache_signature(scs_path, stat)
        manifest_json = _manifest_to_json(mod.manifest)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO mod_cache (
                    path, mtime, size, format, manifest_json,
                    error, icon_bytes, description, is_map, def_files, scanned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    mtime         = excluded.mtime,
                    size          = excluded.size,
                    format        = excluded.format,
                    manifest_json = excluded.manifest_json,
                    error         = excluded.error,
                    icon_bytes    = excluded.icon_bytes,
                    description   = excluded.description,
                    is_map        = excluded.is_map,
                    def_files     = excluded.def_files,
                    scanned_at    = excluded.scanned_at
                """,
                (
                    str(scs_path),
                    mtime,
                    size,
                    mod.format.value,
                    manifest_json,
                    mod.error,
                    icon_bytes,
                    description,
                    int(mod.is_map),
                    json.dumps(list(mod.def_files)),
                    time.time(),
                ),
            )

    def clear(self) -> int:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM mod_cache")
        return cursor.rowcount

    def delete(self, scs_path: Path) -> int:
        # drop one mod after it was trashed; key is str(path), as get/put store it
        with self._conn:
            cursor = self._conn.execute("DELETE FROM mod_cache WHERE path = ?", (str(scs_path),))
        return cursor.rowcount

    def connection(self) -> sqlite3.Connection:
        """Exposes the underlying connection so sibling caches (workshop
        metadata, future icon variants) can share it."""
        return self._conn

    @property
    def path(self) -> Path:
        """The database file path - for opening a separate connection on
        another thread (a sqlite connection must not be shared concurrently)."""
        return self._db_path

    def close(self) -> None:
        with contextlib.suppress(sqlite3.ProgrammingError):
            self._conn.close()

    def __enter__(self) -> ScanCache:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _tune_pragmas(self) -> None:
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.execute("PRAGMA temp_store = MEMORY")

    def _migrate(self) -> None:
        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if current >= SCHEMA_VERSION:
            return
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS mod_cache (
                    path          TEXT    PRIMARY KEY,
                    mtime         REAL    NOT NULL,
                    size          INTEGER NOT NULL,
                    format        TEXT    NOT NULL,
                    manifest_json TEXT,
                    error         TEXT,
                    icon_bytes    BLOB,
                    scanned_at    REAL    NOT NULL
                )
                """)
            if current < 2:
                cols = {row[1] for row in self._conn.execute("PRAGMA table_info(mod_cache)")}
                if "description" not in cols:
                    self._conn.execute("ALTER TABLE mod_cache ADD COLUMN description TEXT")
            if current < 3:
                self._conn.execute("""
                    CREATE TABLE IF NOT EXISTS workshop_meta (
                        workshop_id   TEXT    PRIMARY KEY,
                        title         TEXT,
                        description   TEXT,
                        preview_url   TEXT,
                        preview_bytes BLOB,
                        time_updated  INTEGER,
                        fetched_at    REAL    NOT NULL
                    )
                    """)
            if current < 4:
                # drop rows that failed under the old code so the new readers
                # (fake-lock zips, AEM containers) get a fresh scan
                self._conn.execute("DELETE FROM mod_cache WHERE error IS NOT NULL")
            if current < 5:
                cols = {row[1] for row in self._conn.execute("PRAGMA table_info(mod_cache)")}
                if "is_map" not in cols:
                    self._conn.execute(
                        "ALTER TABLE mod_cache ADD COLUMN is_map INTEGER NOT NULL DEFAULT 0"
                    )
            if current < 6:
                cols = {row[1] for row in self._conn.execute("PRAGMA table_info(mod_cache)")}
                if "def_files" not in cols:
                    self._conn.execute("ALTER TABLE mod_cache ADD COLUMN def_files TEXT")
                # existing rows have no def_files yet; drop them so the next scan
                # re-reads each archive and fills the list (powers conflicts +
                # the physics content signal). One-off slower scan after upgrade.
                self._conn.execute("DELETE FROM mod_cache WHERE def_files IS NULL")
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _manifest_to_json(manifest: ModManifest | None) -> str | None:
    if manifest is None:
        return None
    return json.dumps(
        {
            "display_name": manifest.display_name,
            "package_version": manifest.package_version,
            "author": manifest.author,
            "categories": list(manifest.categories),
            "description_file": manifest.description_file,
            "icon": manifest.icon,
            "compatible_versions": list(manifest.compatible_versions),
        },
        ensure_ascii=False,
    )


def _manifest_from_json(text: str | None) -> ModManifest | None:
    if text is None:
        return None
    data = json.loads(text)
    return ModManifest(
        display_name=data["display_name"],
        package_version=data.get("package_version", ""),
        author=data.get("author", ""),
        categories=tuple(data.get("categories", [])),
        description_file=data.get("description_file", ""),
        icon=data.get("icon", ""),
        compatible_versions=tuple(data.get("compatible_versions", [])),
    )


def _row_to_entry(row: sqlite3.Row, scs_path: Path) -> CachedEntry:
    try:
        description = row["description"]
    except (IndexError, KeyError):
        description = None
    try:
        is_map = bool(row["is_map"])
    except (IndexError, KeyError):
        is_map = False
    try:
        raw_defs = row["def_files"]
        def_files = tuple(json.loads(raw_defs)) if raw_defs else ()
    except (IndexError, KeyError):
        def_files = ()
    mod = ScannedMod(
        path=scs_path,
        format=ScsFormat(row["format"]),
        manifest=_manifest_from_json(row["manifest_json"]),
        error=row["error"],
        description=description,
        is_map=is_map,
        def_files=def_files,
    )
    icon_bytes = row["icon_bytes"]
    return CachedEntry(
        mod=mod,
        icon_bytes=bytes(icon_bytes) if icon_bytes is not None else None,
        scanned_at=row["scanned_at"],
        description=description,
    )


def _cache_signature(path: Path, stat: os.stat_result) -> tuple[float, int]:
    """Returns (mtime, size) that invalidates the cache when the payload
    changes. Directory mods use the count of immediate children for size
    because the directory's own ``st_size`` does not change when files
    inside are edited."""
    if path.is_dir():
        try:
            child_count = sum(1 for _ in path.iterdir())
        except OSError:
            child_count = 0
        return stat.st_mtime, child_count
    return stat.st_mtime, stat.st_size
