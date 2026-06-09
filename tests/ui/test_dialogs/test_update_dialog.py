from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from easy_scsmodmanager.services.update_core import UpdateInfo  # noqa: E402
from easy_scsmodmanager.services.update_service import UpdateService  # noqa: E402
from easy_scsmodmanager.ui.dialogs import update_dialog as mod  # noqa: E402
from easy_scsmodmanager.ui.dialogs.update_dialog import UpdateDialog  # noqa: E402
from easy_scsmodmanager.utils.i18n import t  # noqa: E402


def _dialog(qtbot) -> UpdateDialog:
    info = UpdateInfo(
        version="1.4.0",
        download_url="http://x/a.AppImage",
        download_size=1,
        asset_name="a.AppImage",
        sha256sums_url="",
        release_notes="notes",
        html_url="http://releases",
    )
    dlg = UpdateDialog(info, UpdateService())
    qtbot.addWidget(dlg)
    dlg._dl_path = "/tmp/x"
    return dlg


def test_install_success_quits(qtbot, monkeypatch) -> None:
    dlg = _dialog(qtbot)
    monkeypatch.setattr(UpdateService, "install", staticmethod(lambda p: True))
    quits: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", lambda *a: quits.append(True))
    dlg._perform_install()
    assert quits == [True]


def test_install_failure_resets_and_opens_releases(qtbot, monkeypatch) -> None:
    dlg = _dialog(qtbot)
    monkeypatch.setattr(UpdateService, "install", staticmethod(lambda p: False))
    quits: list[bool] = []
    opened: list[str] = []
    monkeypatch.setattr(QApplication, "quit", lambda *a: quits.append(True))
    monkeypatch.setattr(mod.webbrowser, "open", lambda u: opened.append(u))
    dlg._act.setEnabled(False)
    dlg._perform_install()
    assert dlg._act.isEnabled()  # C2: dialog usable again
    assert quits == []  # no quit on failure
    assert opened == ["http://releases"]


def test_do_install_shows_restarting_without_accepting(qtbot, monkeypatch) -> None:
    dlg = _dialog(qtbot)
    # do not let the timer fire the actual install during this test
    monkeypatch.setattr(mod.QTimer, "singleShot", lambda ms, cb: None)
    dlg._do_install()
    assert not dlg._act.isEnabled()  # C1: button disabled
    assert not dlg._status.isHidden()  # status label shown
    assert dlg._status.text() == t("update.restarting")
    assert dlg.result() == 0  # dialog NOT accepted - hint stays visible
