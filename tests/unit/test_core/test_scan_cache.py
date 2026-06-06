from __future__ import annotations

from pathlib import Path

import pytest

from easy_scsmodmanager.core.db.scan_cache import ScanCache, default_cache_path
from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_scanner import ScannedMod


def _make_scs(path: Path, size: int = 64) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * size)
    return path


def _manifest(display_name: str = "Demo") -> ModManifest:
    return ModManifest(display_name=display_name, author="Author", categories=("sound",))


def _scanned(scs_path: Path, manifest: ModManifest | None = None) -> ScannedMod:
    return ScannedMod(
        path=scs_path,
        format=ScsFormat.ZIP,
        manifest=manifest if manifest is not None else _manifest(),
        error=None,
    )


# ---------------------------------------------------------------------------
# default_cache_path
# ---------------------------------------------------------------------------


def test_default_cache_path_uses_xdg_cache_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))

    assert default_cache_path() == tmp_path / "xdg" / "easy-scsmodmanager" / "scan_cache.db"


def test_default_cache_path_falls_back_to_home_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert default_cache_path() == tmp_path / ".cache" / "easy-scsmodmanager" / "scan_cache.db"


# ---------------------------------------------------------------------------
# ScanCache - get/put round trip
# ---------------------------------------------------------------------------


def test_put_then_get_returns_same_scanned_mod(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod_a.scs")
    mod = _scanned(scs, _manifest("Alpha"))

    with ScanCache(db) as cache:
        cache.put(scs, mod, icon_bytes=b"\xff\xd8jpg")
        entry = cache.get(scs)

    assert entry is not None
    assert entry.mod.format == ScsFormat.ZIP
    assert entry.mod.manifest is not None
    assert entry.mod.manifest.display_name == "Alpha"
    assert entry.mod.error is None
    assert entry.icon_bytes == b"\xff\xd8jpg"


def test_get_returns_none_for_unknown_path(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "missing.scs")

    with ScanCache(db) as cache:
        assert cache.get(scs) is None


def test_get_returns_none_when_mtime_changed(tmp_path: Path) -> None:
    import os
    import time

    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod.scs")
    mod = _scanned(scs)

    with ScanCache(db) as cache:
        cache.put(scs, mod)
        # Push mtime forward by 10 seconds to simulate a file update.
        new_mtime = scs.stat().st_mtime + 10
        os.utime(scs, (new_mtime, new_mtime))
        time.sleep(0)

        assert cache.get(scs) is None


def test_get_returns_none_when_size_changed(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod.scs", size=64)
    mod = _scanned(scs)

    with ScanCache(db) as cache:
        cache.put(scs, mod)
        scs.write_bytes(b"\x00" * 128)  # double the size

        assert cache.get(scs) is None


def test_get_returns_none_for_path_with_no_underlying_file(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "vanishes.scs")
    mod = _scanned(scs)

    with ScanCache(db) as cache:
        cache.put(scs, mod)
        scs.unlink()

        assert cache.get(scs) is None


def test_put_overwrites_existing_entry_for_same_path(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod.scs")

    with ScanCache(db) as cache:
        cache.put(scs, _scanned(scs, _manifest("Old")))
        cache.put(scs, _scanned(scs, _manifest("New")))
        entry = cache.get(scs)

    assert entry is not None
    assert entry.mod.manifest is not None
    assert entry.mod.manifest.display_name == "New"


def test_put_stores_error_entry_with_null_manifest(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "broken.scs")
    mod = ScannedMod(path=scs, format=ScsFormat.UNKNOWN, manifest=None, error="bad magic")

    with ScanCache(db) as cache:
        cache.put(scs, mod)
        entry = cache.get(scs)

    assert entry is not None
    assert entry.mod.manifest is None
    assert entry.mod.error == "bad magic"


def test_def_files_round_trip_through_cache(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod.scs")
    mod = ScannedMod(
        path=scs,
        format=ScsFormat.ZIP,
        manifest=_manifest(),
        error=None,
        def_files=("def/vehicle/physics.sii", "def/climate.sii"),
    )

    with ScanCache(db) as cache:
        cache.put(scs, mod)
        entry = cache.get(scs)

    assert entry is not None
    assert entry.mod.def_files == ("def/vehicle/physics.sii", "def/climate.sii")


def test_schema6_upgrade_drops_rows_lacking_def_files(tmp_path: Path) -> None:
    # a row written before schema 6 has no def_files; the upgrade must drop it
    # so the next scan re-reads the archive and captures its def list
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod.scs")

    with ScanCache(db) as cache:
        cache.put(scs, _scanned(scs))
        cache._conn.execute("UPDATE mod_cache SET def_files = NULL")
        cache._conn.execute("PRAGMA user_version = 5")
        cache._conn.commit()

    with ScanCache(db) as cache:
        assert cache.get(scs) is None  # dropped -> will be rescanned


def test_def_files_default_empty_for_legacy_rows(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod.scs")

    with ScanCache(db) as cache:
        cache.put(scs, _scanned(scs))
        entry = cache.get(scs)

    assert entry is not None
    assert entry.mod.def_files == ()


def test_put_stores_none_icon_separately_from_empty_bytes(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod.scs")

    with ScanCache(db) as cache:
        cache.put(scs, _scanned(scs), icon_bytes=None)
        entry = cache.get(scs)

    assert entry is not None
    assert entry.icon_bytes is None


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_removes_all_entries(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    a = _make_scs(tmp_path / "a.scs")
    b = _make_scs(tmp_path / "b.scs")

    with ScanCache(db) as cache:
        cache.put(a, _scanned(a))
        cache.put(b, _scanned(b))
        deleted = cache.clear()

        assert deleted == 2
        assert cache.get(a) is None
        assert cache.get(b) is None


# ---------------------------------------------------------------------------
# concurrency / persistence
# ---------------------------------------------------------------------------


def test_entries_persist_across_cache_reopens(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    scs = _make_scs(tmp_path / "mod.scs")

    with ScanCache(db) as cache:
        cache.put(scs, _scanned(scs, _manifest("Persisted")))

    with ScanCache(db) as cache:
        entry = cache.get(scs)

    assert entry is not None
    assert entry.mod.manifest is not None
    assert entry.mod.manifest.display_name == "Persisted"


def test_cache_creates_parent_directory_for_db(tmp_path: Path) -> None:
    db = tmp_path / "deep" / "nested" / "cache.db"

    with ScanCache(db) as cache:
        cache.put(_make_scs(tmp_path / "mod.scs"), _scanned(tmp_path / "mod.scs"))

    assert db.is_file()
    assert db.parent.is_dir()


def test_schema_upgrade_clears_errored_entries_for_rescan(tmp_path: Path) -> None:
    # mods that errored under an older schema (fake-lock / AEM before the
    # readers landed) must be dropped on upgrade so they get re-scanned;
    # successfully cached mods stay put.
    db = tmp_path / "cache.db"
    good = _make_scs(tmp_path / "good.scs")
    bad = _make_scs(tmp_path / "bad.scs")
    errored = ScannedMod(
        path=bad, format=ScsFormat.UNKNOWN, manifest=None, error="Unknown SCS container format"
    )

    with ScanCache(db) as cache:
        cache.put(good, _scanned(good))
        cache.put(bad, errored)
        # pretend this db predates the current reader work
        cache._conn.execute("PRAGMA user_version = 3")
        cache._conn.commit()

    with ScanCache(db) as cache:
        assert cache.get(bad) is None  # re-scan with the new readers
        assert cache.get(good) is not None  # untouched


def test_delete_removes_entry(tmp_path: Path) -> None:
    scs = _make_scs(tmp_path / "mod_a.scs")
    with ScanCache(tmp_path / "c.db") as cache:
        cache.put(scs, _scanned(scs), icon_bytes=None)
        assert cache.get(scs) is not None

        removed = cache.delete(scs)

        assert removed == 1
        assert cache.get(scs) is None


def test_delete_missing_path_returns_zero(tmp_path: Path) -> None:
    with ScanCache(tmp_path / "c.db") as cache:
        assert cache.delete(tmp_path / "never.scs") == 0
