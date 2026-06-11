"""Smoke test that the main window can be constructed and shown.

Uses pytest-qt's qtbot to manage the QApplication lifecycle.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from easy_scsmodmanager.ui.main_window import MainWindow  # noqa: E402


def test_main_window_constructs(qtbot) -> None:
    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    assert window.windowTitle().startswith("Easy SCSModManager")
    assert window.minimumWidth() >= 1000


def test_switch_game_changes_game_persists_and_rescans(qtbot, tmp_path, monkeypatch) -> None:
    from PyQt6.QtCore import QSettings

    from easy_scsmodmanager.core.game_paths import Game
    from easy_scsmodmanager.core.settings_store import SettingsStore

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    # isolate settings from the real registry and stub the rescan
    window._settings = SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    rescans: list[Game] = []
    monkeypatch.setattr(window, "_detect_install_and_scan", lambda: rescans.append(window._game))

    window._switch_game(Game.ATS)

    assert window._game is Game.ATS
    assert window._settings.get_active_game() is Game.ATS
    assert rescans == [Game.ATS]


_PROFILE_TEMPLATE = (
    "SiiNunit\n{\nuser_profile : _nameless.x {\n" ' profile_name: "T"\n active_mods: 0\n}\n}\n'
)


def test_save_writes_active_list_to_profile(qtbot, tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from easy_scsmodmanager.services.profile_reader import ActiveMod, read_profile

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)

    sii = tmp_path / "profiles" / "abc" / "profile.sii"
    sii.parent.mkdir(parents=True)
    sii.write_text(_PROFILE_TEMPLATE, encoding="utf-8")
    window._profile_choices = [(sii, read_profile(sii))]
    window._activate_profile(sii)
    window._active_list.set_active_mods([ActiveMod("a", "A"), ActiveMod("b", "B")])

    # user declines the pre-save backup
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window._on_save_clicked()

    assert [m.name for m in read_profile(sii).active_mods] == ["a", "b"]


def test_save_refreshes_header_and_chooser_counts(qtbot, tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from easy_scsmodmanager.services.profile_reader import ActiveMod, read_profile
    from easy_scsmodmanager.utils.i18n import t

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    sii = tmp_path / "profiles" / "abc" / "profile.sii"
    sii.parent.mkdir(parents=True)
    sii.write_text(_PROFILE_TEMPLATE, encoding="utf-8")
    window._profile_choices = [(sii, read_profile(sii))]
    window._activate_profile(sii)
    assert window._profile_header._meta_label.text() == t("active_panel.count", count=0)

    window._active_list.set_active_mods([ActiveMod("a", "A"), ActiveMod("b", "B")])
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window._on_save_clicked()

    # the header meta text and the chooser entry both show the saved count
    assert window._profile_header._meta_label.text() == t("active_panel.count", count=2)
    chooser_profile = next(p for s, p in window._profile_choices if s == sii)
    assert len(chooser_profile.active_mods) == 2


def test_reload_after_share_refreshes_header_count(qtbot, tmp_path) -> None:
    from easy_scsmodmanager.services.profile_reader import ActiveMod, read_profile
    from easy_scsmodmanager.services.profile_writer import save_active_mods
    from easy_scsmodmanager.utils.i18n import t

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    sii = tmp_path / "profiles" / "abc" / "profile.sii"
    sii.parent.mkdir(parents=True)
    sii.write_text(_PROFILE_TEMPLATE, encoding="utf-8")
    window._profile_choices = [(sii, read_profile(sii))]
    window._activate_profile(sii)

    # a share apply rewrites profile.sii behind the window's back
    save_active_mods(sii, [ActiveMod("a", "A"), ActiveMod("b", "B")], backup=False)
    window._reload_profile_after_share()

    assert window._profile_header._meta_label.text() == t("active_panel.count", count=2)
    assert window._save_btn.isEnabled() is False


def test_save_aborts_on_cancel(qtbot, tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from easy_scsmodmanager.services.profile_reader import ActiveMod, read_profile

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)

    sii = tmp_path / "profiles" / "abc" / "profile.sii"
    sii.parent.mkdir(parents=True)
    sii.write_text(_PROFILE_TEMPLATE, encoding="utf-8")
    window._profile_sii_path = sii
    window._profile = read_profile(sii)
    window._active_list.set_active_mods([ActiveMod("a", "A")])

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    window._on_save_clicked()

    # nothing written - still zero active mods on disk
    assert list(read_profile(sii).active_mods) == []


def _profile_pair(tmp_path, monkeypatch, window) -> tuple:
    """Two on-disk profiles wired into the window; ``b`` is the newer one."""
    import os

    from PyQt6.QtCore import QSettings

    from easy_scsmodmanager.core.game_paths import Game, GameInstall, InstallKind
    from easy_scsmodmanager.core.settings_store import SettingsStore

    window._settings = SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    docs = tmp_path / "docs"
    sii_a = docs / "profiles" / "aa" / "profile.sii"
    sii_b = docs / "profiles" / "bb" / "profile.sii"
    for sii in (sii_a, sii_b):
        sii.parent.mkdir(parents=True)
        sii.write_text(_PROFILE_TEMPLATE, encoding="utf-8")
    os.utime(sii_a, (1_000_000, 1_000_000))  # a is old, b stays freshly written
    window._install = GameInstall(
        game=Game.ETS2, kind=InstallKind.PROTON, documents_dir=docs, workshop_dir=None
    )
    monkeypatch.setattr(
        "easy_scsmodmanager.ui.main_window.discover_profiles", lambda install: [sii_a, sii_b]
    )
    return sii_a, sii_b


def test_load_profiles_reopens_last_selected(qtbot, tmp_path, monkeypatch) -> None:
    from easy_scsmodmanager.core.game_paths import Game

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    sii_a, _sii_b = _profile_pair(tmp_path, monkeypatch, window)
    window._settings.set_last_selected_profile(Game.ETS2, sii_a)

    window._load_profiles()

    # the remembered one wins even though b was modified more recently
    assert window._profile_sii_path == sii_a


def test_load_profiles_falls_back_when_remembered_is_gone(qtbot, tmp_path, monkeypatch) -> None:
    from easy_scsmodmanager.core.game_paths import Game

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    _sii_a, sii_b = _profile_pair(tmp_path, monkeypatch, window)
    window._settings.set_last_selected_profile(Game.ETS2, tmp_path / "gone" / "profile.sii")

    window._load_profiles()

    # stale key: back to the most recently modified profile, key refreshed
    assert window._profile_sii_path == sii_b
    assert window._settings.get_last_selected_profile(Game.ETS2) == sii_b


def test_choosing_a_profile_stores_it_as_last_selected(qtbot, tmp_path, monkeypatch) -> None:
    from easy_scsmodmanager.core.game_paths import Game
    from easy_scsmodmanager.ui.widgets.profile_header import ProfileChoice

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    sii_a, sii_b = _profile_pair(tmp_path, monkeypatch, window)
    window._load_profiles()
    assert window._profile_sii_path == sii_b  # nothing remembered yet

    window._on_profile_chosen(
        ProfileChoice(sii_path=sii_a, display_name="A", active_count=0, is_current=False)
    )

    assert window._profile_sii_path == sii_a
    assert window._settings.get_last_selected_profile(Game.ETS2) == sii_a


def test_double_click_grid_card_inserts_into_group_block(qtbot) -> None:
    from pathlib import Path

    from PyQt6.QtCore import Qt

    from easy_scsmodmanager.core.models.mod_manifest import ModManifest
    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    window._active_list.set_active_mods([ActiveMod("existing", "Existing")])

    mod = ScannedMod(
        path=Path("/mod/newmod.scs"),
        format=ScsFormat.ZIP,
        manifest=ModManifest(display_name="New Mod"),
        error=None,
    )
    window._on_mod_activated(mod)

    # added group-aware (same "other" block here) and selected, Save enabled
    names = [m.name for m in window._active_list.display_order()]
    assert "newmod" in names
    assert window._save_btn.isEnabled() is True
    current = window._active_list._list.currentItem()
    assert current.data(Qt.ItemDataRole.UserRole).name == "newmod"


def test_drop_from_grid_inserts_mods_at_row(qtbot) -> None:
    from pathlib import Path

    from easy_scsmodmanager.core.models.mod_manifest import ModManifest
    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    dropped = ScannedMod(
        path=Path("/mod/dropme.scs"),
        format=ScsFormat.ZIP,
        manifest=ModManifest(display_name="Drop Me"),
        error=None,
    )
    window._all_mods = [dropped]
    window._active_list.set_active_mods([ActiveMod("existing", "Existing")])

    window._on_mods_dropped(["/mod/dropme.scs"], 0, "ui_other")  # drop at display top

    assert window._active_list.display_order()[0].name == "dropme"
    assert window._active_list.display_order()[0].display_name == "Drop Me"


def test_drop_relocates_already_active_mod_without_duplicating(qtbot) -> None:
    from pathlib import Path

    from easy_scsmodmanager.core.models.mod_manifest import ModManifest
    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    mod = ScannedMod(
        path=Path("/mod/already.scs"),
        format=ScsFormat.ZIP,
        manifest=ModManifest(display_name="Already"),
        error=None,
    )
    window._all_mods = [mod]
    window._active_list.set_active_mods(
        [ActiveMod("already", "Already"), ActiveMod("other", "Other")]
    )

    window._on_mods_dropped(["/mod/already.scs"], 0, "ui_other")  # drag from grid to the top

    order = [m.name for m in window._active_list.display_order()]
    assert order.count("already") == 1  # moved, not duplicated
    assert order[0] == "already"  # relocated to the drop position


def test_search_matches_the_visible_name_not_just_the_manifest(qtbot) -> None:
    # The dash bug: a workshop mod whose only readable name is the profile's
    # active display ("...Dashboard"). Searching "dash" must find it even though
    # its manifest carries no name and its file stem is "universal".
    from pathlib import Path

    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_matching import active_name_for
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.services.profile_reader import ActiveMod, Profile
    from easy_scsmodmanager.ui.widgets.filter_toolbar import FilterState

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)

    mod = ScannedMod(
        path=Path("/lib/steamapps/workshop/content/227300/123/universal.scs"),
        format=ScsFormat.ZIP,
        manifest=None,
        error=None,
    )
    window._all_mods = [mod]
    window._profile = Profile(
        dir_name="abc",
        profile_name="T",
        active_mods=(ActiveMod(active_name_for(mod), "MAN TGX Improved Dashboard"),),
    )

    # the window feeds its scan context into the presenter before it derives
    window._sync_presenter()
    found = window._presenter.filter_and_sort([mod], FilterState(search="dash"))

    assert found == [mod]


def test_restore_reachable_when_profile_failed_to_parse(qtbot, tmp_path, monkeypatch) -> None:
    # the whole point of restore is to recover a profile that no longer parses
    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    window._profile_sii_path = tmp_path / "profile.sii"
    window._profile = None  # corrupt / unparseable

    monkeypatch.setattr(
        "easy_scsmodmanager.ui.controllers.profile_backup_controller.list_backups",
        lambda p: [],
    )
    window._backup.restore()

    # reached the "no backups" branch (status set) instead of silently returning
    assert window.statusBar().currentMessage() != ""


def test_restore_button_enabled_for_corrupt_active_profile(qtbot, tmp_path) -> None:
    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    sii = tmp_path / "profiles" / "abc" / "profile.sii"
    sii.parent.mkdir(parents=True)
    window._profile_choices = [(sii, None)]  # parsed to None (corrupt)

    window._activate_profile(sii)

    assert window._profile_header._restore_btn.isEnabled() is True
    assert window._profile_header._backup_btn.isEnabled() is False


def test_grid_click_jump_gated_by_setting(qtbot, tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from PyQt6.QtCore import QSettings

    from easy_scsmodmanager.core.settings_store import SettingsStore
    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    window._settings = SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))

    jumped: list[str] = []
    monkeypatch.setattr(window._active_list, "focus_active", lambda name: jumped.append(name))
    mod = ScannedMod(path=Path("/tmp/x.scs"), format=ScsFormat.ZIP, manifest=None, error=None)

    window._settings.set_grid_click_jumps_to_active(False)
    window._on_grid_selection_changed([mod])
    assert jumped == []  # default off: no jump

    window._settings.set_grid_click_jumps_to_active(True)
    window._on_grid_selection_changed([mod])
    assert len(jumped) == 1  # opt-in on: jumps


def test_apply_group_pin_clears_when_target_is_home(qtbot, monkeypatch) -> None:
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    monkeypatch.setattr(window._presenter, "natural_group_token_for", lambda a: "truck")
    window._group_overrides.set("m", "trailers")  # stale pin

    window._apply_group_pin(ActiveMod("m", "M"), "trucks")  # trucks == home

    assert window._group_overrides.get("m") is None


def test_apply_group_pin_sets_for_foreign_group(qtbot, monkeypatch) -> None:
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    monkeypatch.setattr(window._presenter, "natural_group_token_for", lambda a: "truck")

    window._apply_group_pin(ActiveMod("m", "M"), "trailers")  # foreign

    assert window._group_overrides.get("m") == "trailers"


def test_on_move_to_group_list_batches(qtbot, monkeypatch) -> None:
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    monkeypatch.setattr(window._presenter, "natural_group_token_for", lambda a: "other")
    moved: list = []
    monkeypatch.setattr(
        window._active_list, "move_mods_to_group", lambda mods, gid: moved.append((mods, gid))
    )

    window._on_move_to_group([ActiveMod("a", "A"), ActiveMod("b", "B")], "trucks")

    assert len(moved) == 1
    assert [m.name for m in moved[0][0]] == ["a", "b"]
    assert moved[0][1] == "trucks"


def test_drop_into_foreign_group_pins_it(qtbot) -> None:
    from pathlib import Path

    from easy_scsmodmanager.core.models.mod_manifest import ModManifest
    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_matching import active_name_for
    from easy_scsmodmanager.services.mod_scanner import ScannedMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    mod = ScannedMod(
        path=Path("/mod/weatherfix.scs"),
        format=ScsFormat.ZIP,
        manifest=ModManifest(display_name="Weather Fix"),
        error=None,
    )
    window._all_mods = [mod]
    window._active_list.set_active_mods([])

    # drop into the trucks block (foreign for a no-match mod whose natural is other)
    window._on_mods_dropped(["/mod/weatherfix.scs"], 0, "trucks")

    assert window._group_overrides.get(active_name_for(mod)) == "trucks"


def test_reorder_pin_applies_pin_rule(qtbot, monkeypatch) -> None:
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    monkeypatch.setattr(window._presenter, "natural_group_token_for", lambda a: "other")

    window._on_reorder_pin([ActiveMod("m", "M")], "trucks")  # foreign -> pin

    assert window._group_overrides.get("m") == "trucks"
