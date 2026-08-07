"""Profile backup + restore.

Stores zipped snapshots of the profile directory under the user's data
home, *outside* the ETS2/ATS profiles tree, so the game never sees
them. Layout::

    $XDG_DATA_HOME/easy-scsmodmanager/profile_backups/<hex-dir-name>/
        2026-05-28_19-21-04.zip
        2026-05-28_19-31-12.zip
        ...

Backups capture every file in the profile directory (profile.sii,
controls.sii, online_avatar.png, ...). Restore extracts back into the
original directory, overwriting whatever is there.

Note: ETS2 should not be running while you restore - the game keeps
profile.sii open and may rewrite it on exit.
"""

from __future__ import annotations

import contextlib
import datetime
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "easy-scsmodmanager"
BACKUP_SUBDIR = "profile_backups"
TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"


@dataclass(frozen=True)
class BackupEntry:
    path: Path
    profile_dir_name: str
    timestamp: datetime.datetime
    size_bytes: int

    @property
    def label(self) -> str:
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")


def default_backup_root() -> Path:
    """``$XDG_DATA_HOME/easy-scsmodmanager/profile_backups/`` or HOME fallback."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path(os.environ.get("HOME", "~")).expanduser() / ".local" / "share"
    return base / APP_DIR_NAME / BACKUP_SUBDIR


def backup_directory_for(sii_path: Path, root: Path | None = None) -> Path:
    """The directory under ``root`` that holds backups for this profile."""
    base = root if root is not None else default_backup_root()
    return base / sii_path.parent.name


def create_backup(sii_path: Path, root: Path | None = None) -> BackupEntry:
    """Zip the profile directory of ``sii_path`` into a fresh backup.

    Raises FileNotFoundError if the profile directory does not exist.
    """
    profile_dir = sii_path.parent
    if not profile_dir.is_dir():
        raise FileNotFoundError(profile_dir)

    target_dir = backup_directory_for(sii_path, root)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now()
    target = target_dir / f"{timestamp.strftime(TIMESTAMP_FORMAT)}.zip"

    # Write to a tmp file in the same directory then atomically rename so a
    # crash mid-write never leaves a half-zipped backup behind.
    with tempfile.NamedTemporaryFile(dir=target_dir, suffix=".zip.tmp", delete=False) as tmp_fp:
        tmp_path = Path(tmp_fp.name)

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as zf:
            for entry in sorted(profile_dir.rglob("*")):
                if entry.is_file():
                    zf.write(entry, entry.relative_to(profile_dir))
        tmp_path.replace(target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return BackupEntry(
        path=target,
        profile_dir_name=profile_dir.name,
        timestamp=timestamp,
        size_bytes=target.stat().st_size,
    )


def list_backups(sii_path: Path, root: Path | None = None) -> list[BackupEntry]:
    """Returns backups for this profile, newest first."""
    target_dir = backup_directory_for(sii_path, root)
    if not target_dir.is_dir():
        return []
    entries: list[BackupEntry] = []
    for zip_path in target_dir.glob("*.zip"):
        try:
            ts = datetime.datetime.strptime(zip_path.stem, TIMESTAMP_FORMAT)
        except ValueError:
            ts = datetime.datetime.fromtimestamp(zip_path.stat().st_mtime)
        entries.append(
            BackupEntry(
                path=zip_path,
                profile_dir_name=sii_path.parent.name,
                timestamp=ts,
                size_bytes=zip_path.stat().st_size,
            )
        )
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries


def restore_backup(backup: BackupEntry, sii_path: Path) -> None:
    """Extract ``backup`` over the profile directory of ``sii_path``.

    Existing files are overwritten; files missing from the backup are
    NOT touched (we never blow away anything we did not capture). The
    target directory is recreated if it has been deleted in the
    meantime.
    """
    profile_dir = sii_path.parent
    profile_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup.path, "r") as zf:
        zf.extractall(profile_dir)


def delete_backup(backup: BackupEntry) -> None:
    """Removes a backup from disk. Used by the cleanup buttons."""
    with contextlib.suppress(FileNotFoundError):
        backup.path.unlink()


def total_size_for_profile(sii_path: Path, root: Path | None = None) -> int:
    """Sum of bytes used by every backup of this profile."""
    return sum(b.size_bytes for b in list_backups(sii_path, root))


def disk_usage_human(num_bytes: int) -> str:
    """Compact human-readable form: 2.3 MB, 12 KB, 480 B."""
    size: float = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


# Keep shutil import used by tests that want to mock copytree path-checks.
_ = shutil
