from __future__ import annotations

import datetime
import os
import zipfile
from pathlib import Path

import pytest

from easy_scsmodmanager.services.profile_backup import (
    BackupEntry,
    create_backup,
    default_backup_root,
    delete_backup,
    list_backups,
    restore_backup,
)


def _make_profile(tmp_path: Path) -> Path:
    profile_dir = tmp_path / "profiles" / "abc123"
    profile_dir.mkdir(parents=True)
    (profile_dir / "profile.sii").write_text("dummy sii content")
    (profile_dir / "controls.sii").write_text("controls")
    (profile_dir / "online_avatar.png").write_bytes(b"\x89PNG fake")
    return profile_dir / "profile.sii"


def test_default_backup_root_uses_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    assert default_backup_root() == tmp_path / "xdg" / "easy-scsmodmanager" / "profile_backups"


def test_default_backup_root_falls_back_to_home_local_share(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert default_backup_root() == (
        tmp_path / ".local" / "share" / "easy-scsmodmanager" / "profile_backups"
    )


def test_create_backup_zips_every_file_in_the_profile_directory(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)

    entry = create_backup(sii, root=tmp_path / "backups")

    assert entry.path.is_file()
    assert entry.profile_dir_name == "abc123"
    with zipfile.ZipFile(entry.path) as zf:
        names = sorted(zf.namelist())
    assert names == ["controls.sii", "online_avatar.png", "profile.sii"]


def test_create_backup_writes_outside_the_profile_tree(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)
    backup_root = tmp_path / "backups"

    entry = create_backup(sii, root=backup_root)

    # Important: backup must not live inside profiles/ so ETS2 ignores it.
    assert backup_root in entry.path.parents
    assert "profiles" not in [p.name for p in entry.path.parents]


def test_create_backup_uses_per_profile_subdirectory(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)

    entry = create_backup(sii, root=tmp_path / "backups")

    assert entry.path.parent == tmp_path / "backups" / "abc123"


def test_create_backup_atomic_no_tmp_file_left_on_disk(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)
    create_backup(sii, root=tmp_path / "backups")

    leftovers = list((tmp_path / "backups" / "abc123").glob("*.tmp"))
    assert leftovers == []


def test_create_backup_raises_when_profile_directory_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_backup(tmp_path / "missing" / "profile.sii", root=tmp_path / "backups")


def test_create_backup_handles_pre_1980_file_timestamps(tmp_path: Path) -> None:
    # some Windows systems leave file timestamps at the Unix epoch (1970-01-01),
    # which is before the ZIP format minimum (1980); strict_timestamps=False clamps it
    sii = _make_profile(tmp_path)
    epoch = 0  # 1970-01-01 00:00:00 UTC
    for f in sii.parent.rglob("*"):
        if f.is_file():
            os.utime(f, (epoch, epoch))

    entry = create_backup(sii, root=tmp_path / "backups")
    assert entry.path.exists()
    with zipfile.ZipFile(entry.path) as zf:
        assert "profile.sii" in zf.namelist()


def test_list_backups_returns_newest_first(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)

    older = create_backup(sii, root=tmp_path / "backups")
    # Bump the timestamp so the second filename differs by at least one second.
    import time as time_module

    time_module.sleep(1.05)
    newer = create_backup(sii, root=tmp_path / "backups")

    backups = list_backups(sii, root=tmp_path / "backups")

    assert [b.path for b in backups] == [newer.path, older.path]


def test_list_backups_returns_empty_when_no_directory(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)

    assert list_backups(sii, root=tmp_path / "backups") == []


def test_restore_backup_overwrites_existing_files(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)
    entry = create_backup(sii, root=tmp_path / "backups")

    # Mess with the live profile
    sii.write_text("user edited this by hand")
    (sii.parent / "controls.sii").write_text("messed up")

    restore_backup(entry, sii)

    assert sii.read_text() == "dummy sii content"
    assert (sii.parent / "controls.sii").read_text() == "controls"


def test_restore_backup_recreates_deleted_target_directory(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)
    entry = create_backup(sii, root=tmp_path / "backups")
    profile_dir = sii.parent
    import shutil

    shutil.rmtree(profile_dir)

    restore_backup(entry, sii)

    assert sii.read_text() == "dummy sii content"


def test_restore_backup_keeps_unrelated_files_untouched(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)
    entry = create_backup(sii, root=tmp_path / "backups")
    new_file = sii.parent / "added_after_backup.txt"
    new_file.write_text("not in backup")

    restore_backup(entry, sii)

    assert new_file.read_text() == "not in backup"


def test_delete_backup_removes_file(tmp_path: Path) -> None:
    sii = _make_profile(tmp_path)
    entry = create_backup(sii, root=tmp_path / "backups")
    assert entry.path.exists()

    delete_backup(entry)

    assert not entry.path.exists()


def test_backup_entry_label_is_human_readable() -> None:
    entry = BackupEntry(
        path=Path("/tmp/x.zip"),
        profile_dir_name="abc",
        timestamp=datetime.datetime(2026, 5, 28, 19, 21, 4),
        size_bytes=1234,
    )

    assert entry.label == "2026-05-28 19:21:04"
