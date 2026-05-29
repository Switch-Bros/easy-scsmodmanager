from __future__ import annotations

import datetime
from pathlib import Path

from pytestqt.qtbot import QtBot

from easy_scsmodmanager.services.profile_backup import BackupEntry
from easy_scsmodmanager.ui.dialogs.restore_backup_dialog import RestoreBackupDialog


def _entry(name: str = "20260101_120000.zip", size: int = 2048) -> BackupEntry:
    return BackupEntry(
        path=Path("/tmp/backups") / name,
        profile_dir_name="abc123",
        timestamp=datetime.datetime(2026, 1, 1, 12, 0, 0),
        size_bytes=size,
    )


def test_constructs_with_backups_and_preselects_first(qtbot: QtBot) -> None:
    dlg = RestoreBackupDialog("My Profile", [_entry(), _entry("20260102_120000.zip")])
    qtbot.addWidget(dlg)

    # row 0 is auto-selected, so both actions are enabled and nothing crashed
    assert dlg._restore_btn.isEnabled() is True
    assert dlg._delete_btn.isEnabled() is True


def test_buttons_disabled_when_no_backups(qtbot: QtBot) -> None:
    dlg = RestoreBackupDialog("My Profile", [])
    qtbot.addWidget(dlg)

    assert dlg._restore_btn.isEnabled() is False
    assert dlg._delete_btn.isEnabled() is False
