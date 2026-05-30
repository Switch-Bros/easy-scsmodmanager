from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.core.settings_store import SettingsStore


@pytest.fixture
def store(tmp_path: Path) -> SettingsStore:
    # IniFormat + explicit path keeps the test out of the real registry.
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return SettingsStore(settings)


def test_language_round_trip(store: SettingsStore) -> None:
    assert store.get_language() is None
    store.set_language("de")
    assert store.get_language() == "de"


def test_language_clear(store: SettingsStore) -> None:
    store.set_language("de")
    store.set_language(None)
    assert store.get_language() is None


def test_documents_override_round_trip(store: SettingsStore, tmp_path: Path) -> None:
    assert store.get_documents_override(Game.ETS2) is None
    docs = tmp_path / "ets2docs"
    store.set_documents_override(Game.ETS2, docs)
    assert store.get_documents_override(Game.ETS2) == docs
    # ATS is independent of ETS2.
    assert store.get_documents_override(Game.ATS) is None


def test_workshop_override_round_trip(store: SettingsStore, tmp_path: Path) -> None:
    workshop = tmp_path / "ws"
    store.set_workshop_override(Game.ATS, workshop)
    assert store.get_workshop_override(Game.ATS) == workshop


def test_override_clear(store: SettingsStore, tmp_path: Path) -> None:
    store.set_documents_override(Game.ETS2, tmp_path)
    store.set_documents_override(Game.ETS2, None)
    assert store.get_documents_override(Game.ETS2) is None
