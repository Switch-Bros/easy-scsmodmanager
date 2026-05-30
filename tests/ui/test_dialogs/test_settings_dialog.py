from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.core.settings_store import SettingsStore
from easy_scsmodmanager.ui.dialogs.settings_dialog import DOCUMENTS, INSTALL, SettingsDialog


def _store(tmp_path: Path) -> SettingsStore:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return SettingsStore(settings)


def test_loads_existing_values(qtbot: QtBot, tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set_language("de")
    docs = tmp_path / "ets2docs"
    store.set_documents_override(Game.ETS2, docs)

    dialog = SettingsDialog(store)
    qtbot.addWidget(dialog)

    assert dialog.selected_language() == "de"
    assert dialog._edits[(Game.ETS2, DOCUMENTS)].text() == str(docs)
    assert dialog._edits[(Game.ATS, DOCUMENTS)].text() == ""  # untouched -> auto


def test_save_writes_language_and_paths(qtbot: QtBot, tmp_path: Path) -> None:
    store = _store(tmp_path)
    dialog = SettingsDialog(store)
    qtbot.addWidget(dialog)

    dialog._lang_combo.setCurrentIndex(dialog._lang_combo.findData("de"))
    dialog._paths[(Game.ETS2, DOCUMENTS)] = tmp_path / "docs"  # simulate browses
    dialog._paths[(Game.ETS2, INSTALL)] = tmp_path / "game"

    dialog.accept()

    assert store.get_language() == "de"
    assert store.get_documents_override(Game.ETS2) == tmp_path / "docs"
    assert store.get_install_override(Game.ETS2) == tmp_path / "game"


def test_reset_clears_an_existing_override(qtbot: QtBot, tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set_install_override(Game.ETS2, tmp_path / "old")

    dialog = SettingsDialog(store)
    qtbot.addWidget(dialog)
    dialog._on_reset(Game.ETS2, INSTALL)
    dialog.accept()

    assert store.get_install_override(Game.ETS2) is None
