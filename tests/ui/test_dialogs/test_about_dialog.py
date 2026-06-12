# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json

from PyQt6.QtCore import QTimer
from pytestqt.qtbot import QtBot

import easy_scsmodmanager as pkg
import easy_scsmodmanager.utils.i18n as i18n
from easy_scsmodmanager.ui.dialogs import about_dialog
from easy_scsmodmanager.ui.dialogs.about_dialog import AboutDialog
from easy_scsmodmanager.utils.i18n import emoji


def test_dialog_builds_without_exception(qtbot: QtBot) -> None:
    dlg = AboutDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle()


def test_dialog_exec_then_accept(qtbot: QtBot) -> None:
    dlg = AboutDialog()
    qtbot.addWidget(dlg)
    QTimer.singleShot(0, dlg.accept)
    dlg.exec()


def test_one_credit_row_per_entry(qtbot: QtBot) -> None:
    dlg = AboutDialog()
    qtbot.addWidget(dlg)
    assert len(dlg._credit_labels) == len(about_dialog._CREDITS)


def test_version_metadata_present() -> None:
    assert pkg.__release_date__
    assert pkg.__author__
    assert pkg.__license__ == "GPL-3.0"


def test_app_name_and_version_importable() -> None:
    from easy_scsmodmanager import __app_name__, __version__

    assert __app_name__ and __version__


def test_built_with_contains_yellow_heart() -> None:
    assert emoji("yellow_heart") in about_dialog._built_with()


def test_about_body_removed_but_title_kept() -> None:
    root = i18n._i18n_root()
    for lang in ("en", "de", "zh"):
        data = json.loads(root.joinpath(lang, "main.json").read_text(encoding="utf-8"))
        assert "dialog.about.body" not in data
        assert "dialog.about.title" in data
