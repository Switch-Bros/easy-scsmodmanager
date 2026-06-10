from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from PyQt6.QtWidgets import QCheckBox  # noqa: E402

from easy_scsmodmanager.services.server_packages import read_server_packages  # noqa: E402
from easy_scsmodmanager.ui.dialogs import server_packages_dialog as mod  # noqa: E402
from easy_scsmodmanager.ui.dialogs.server_packages_dialog import ServerPackagesDialog  # noqa: E402

_RPM = (
    Path(__file__).parent.parent.parent / "fixtures" / "server_packages" / "rpm_server_packages.sii"
)


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "server_packages.sii"
    shutil.copy2(_RPM, target)
    return target


def _first_checkbox(dlg: ServerPackagesDialog) -> QCheckBox:
    holder = dlg._table.cellWidget(0, 1)
    return holder.findChild(QCheckBox)


def test_load_populates_table_and_disables_save(qtbot, tmp_path) -> None:
    dlg = ServerPackagesDialog()
    qtbot.addWidget(dlg)
    dlg._load(read_server_packages(_copy(tmp_path)))

    assert dlg._table.rowCount() == 9
    assert not dlg._hint.isHidden()  # hint shown after a valid load
    assert not dlg._save_btn.isEnabled()  # nothing dirty yet
    assert dlg._table.item(0, 0).text()  # mod display name present


def test_toggle_enables_save_then_writes(qtbot, tmp_path) -> None:
    target = _copy(tmp_path)
    dlg = ServerPackagesDialog()
    qtbot.addWidget(dlg)
    dlg._load(read_server_packages(target))

    _first_checkbox(dlg).setChecked(True)
    assert dlg._save_btn.isEnabled()  # dirty -> save active

    dlg._on_save()
    assert dlg._table.item(0, 0)  # still loaded
    assert not dlg._save_btn.isEnabled()  # dirty cleared after save
    assert read_server_packages(target).mods[0].optional is True  # written


def test_invalid_file_shows_error_no_load(qtbot, tmp_path, monkeypatch) -> None:
    bad = tmp_path / "manifest.sii"
    bad.write_text('SiiNunit\n{\nmod_package: .m {\n display_name: "x"\n}\n}\n')
    monkeypatch.setattr(mod.QFileDialog, "getOpenFileName", lambda *a, **k: (str(bad), ""))

    dlg = ServerPackagesDialog()
    qtbot.addWidget(dlg)
    dlg._on_open()

    assert dlg._table.rowCount() == 0  # nothing loaded
    assert dlg._hint.isHidden()
    assert "valid" in dlg._status.text().lower() or "gültig" in dlg._status.text().lower()


def test_no_change_save_stays_disabled(qtbot, tmp_path) -> None:
    dlg = ServerPackagesDialog()
    qtbot.addWidget(dlg)
    dlg._load(read_server_packages(_copy(tmp_path)))
    cb = _first_checkbox(dlg)
    cb.setChecked(True)
    cb.setChecked(False)  # back to original
    assert not dlg._save_btn.isEnabled()  # net-zero change -> not dirty
