from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings

from easy_scsmodmanager.app import _apply_saved_language
from easy_scsmodmanager.core.settings_store import SettingsStore
from easy_scsmodmanager.utils.i18n import current_language, set_language


def _store(tmp_path: Path) -> SettingsStore:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return SettingsStore(settings)


def test_apply_saved_language_sets_active(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set_language("de")
    set_language("en")  # baseline
    try:
        _apply_saved_language(store)
        assert current_language() == "de"
    finally:
        set_language("en")


def test_apply_saved_language_is_noop_when_unset(tmp_path: Path) -> None:
    store = _store(tmp_path)  # nothing saved
    set_language("en")
    try:
        _apply_saved_language(store)
        assert current_language() == "en"
    finally:
        set_language("en")
