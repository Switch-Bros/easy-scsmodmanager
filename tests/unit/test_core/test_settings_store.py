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


def test_map_base_names_default_and_round_trip(tmp_path: Path) -> None:
    from easy_scsmodmanager.core.map_base_mods import DEFAULT_MAP_BASE_NAMES

    s = SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    assert s.get_map_base_names() == DEFAULT_MAP_BASE_NAMES
    s.set_map_base_names(["Foo", "Bar"])
    assert s.get_map_base_names() == ("Foo", "Bar")


def test_active_game_defaults_to_ets2(store: SettingsStore) -> None:
    assert store.get_active_game() == Game.ETS2


def test_active_game_round_trip(store: SettingsStore) -> None:
    store.set_active_game(Game.ATS)
    assert store.get_active_game() == Game.ATS


def test_active_game_ignores_a_garbage_value(store: SettingsStore) -> None:
    store._s.setValue("active_game", "nonsense")
    assert store.get_active_game() == Game.ETS2


def test_update_check_on_startup_defaults_true(store: SettingsStore) -> None:
    assert store.get_update_check_on_startup() is True


def test_update_check_on_startup_roundtrips_false(store: SettingsStore) -> None:
    store.set_update_check_on_startup(False)
    assert store.get_update_check_on_startup() is False
    store.set_update_check_on_startup(True)
    assert store.get_update_check_on_startup() is True


def test_last_selected_profile_defaults_none(store: SettingsStore) -> None:
    assert store.get_last_selected_profile(Game.ETS2) is None


def test_last_selected_profile_round_trip_per_game(store: SettingsStore, tmp_path: Path) -> None:
    ets2_sii = tmp_path / "profiles" / "aa" / "profile.sii"
    store.set_last_selected_profile(Game.ETS2, ets2_sii)
    assert store.get_last_selected_profile(Game.ETS2) == ets2_sii
    # ATS keeps its own slot - the games have separate profile sets
    assert store.get_last_selected_profile(Game.ATS) is None


def test_last_selected_profile_clear(store: SettingsStore, tmp_path: Path) -> None:
    store.set_last_selected_profile(Game.ATS, tmp_path / "profile.sii")
    store.set_last_selected_profile(Game.ATS, None)
    assert store.get_last_selected_profile(Game.ATS) is None


def test_grid_click_jump_defaults_false(store: SettingsStore) -> None:
    assert store.get_grid_click_jumps_to_active() is False


def test_grid_click_jump_roundtrips_true(store: SettingsStore) -> None:
    store.set_grid_click_jumps_to_active(True)
    assert store.get_grid_click_jumps_to_active() is True
