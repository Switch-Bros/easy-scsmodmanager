from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from pytestqt.qtbot import QtBot

from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.ui.widgets.mod_card_grid import ModCardGrid


def _mod(name: str, path: str = "/tmp/m.scs") -> ScannedMod:
    return ScannedMod(
        path=Path(path),
        format=ScsFormat.ZIP,
        manifest=ModManifest(display_name=name),
        error=None,
    )


def test_set_mods_creates_one_card_per_mod(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)

    grid.set_mods([_mod("A"), _mod("B"), _mod("C")])

    assert len(grid.cards()) == 3


def test_set_mods_replaces_previous_cards(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)

    grid.set_mods([_mod("Old1"), _mod("Old2")])
    grid.set_mods([_mod("New")])

    assert len(grid.cards()) == 1
    assert grid.cards()[0].mod.manifest.display_name == "New"


def test_active_names_set_marks_matching_cards_active(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)

    grid.set_mods(
        [_mod("Live", path="/tmp/live.scs"), _mod("Off", path="/tmp/off.scs")],
        active_names={"live"},
    )

    cards = grid.cards()
    assert cards[0].is_active is True
    assert cards[1].is_active is False


def test_icon_for_callable_is_invoked_per_card(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)

    calls: list[ScannedMod] = []

    def icon_for(mod: ScannedMod) -> bytes | None:
        calls.append(mod)
        return None

    grid.set_mods([_mod("A"), _mod("B")], icon_for=icon_for)

    assert len(calls) == 2


def test_selecting_a_card_emits_selection_changed(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods([_mod("A"), _mod("B")])

    with qtbot.waitSignal(grid.selection_changed, timeout=500) as sig:
        grid._on_card_clicked(0, Qt.KeyboardModifier.NoModifier)

    assert len(sig.args[0]) == 1
    assert sig.args[0][0].manifest.display_name == "A"
    assert grid.cards()[0].is_selected is True


def test_selecting_another_card_clears_previous(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods([_mod("A"), _mod("B")])

    grid._on_card_clicked(0, Qt.KeyboardModifier.NoModifier)
    grid._on_card_clicked(1, Qt.KeyboardModifier.NoModifier)

    assert grid.cards()[0].is_selected is False
    assert grid.cards()[1].is_selected is True


def test_clear_selection_drops_all_selected(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods([_mod("A")])
    grid._on_card_clicked(0, Qt.KeyboardModifier.NoModifier)

    with qtbot.waitSignal(grid.selection_changed, timeout=500) as sig:
        grid.clear_selection()

    assert sig.args[0] == []
    assert grid.cards()[0].is_selected is False


def test_double_click_emits_card_activated_with_mod(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods([_mod("Demo")])

    with qtbot.waitSignal(grid.card_activated, timeout=500) as sig:
        grid._on_card_activated(0)

    assert sig.args[0].manifest.display_name == "Demo"


def test_info_requested_relays_the_mod(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    mod = _mod("Detailed")
    grid.set_mods([mod])

    captured: list[ScannedMod] = []
    grid.info_requested.connect(captured.append)
    grid.cards()[0].info_requested.emit()

    assert captured == [mod]


def _grid_with(qtbot: QtBot, n: int) -> ModCardGrid:
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods([_mod(f"M{i}", path=f"/tmp/m{i}.scs") for i in range(n)])
    return grid


def test_plain_click_selects_only_that_card(qtbot: QtBot) -> None:
    grid = _grid_with(qtbot, 4)
    grid._on_card_clicked(1, Qt.KeyboardModifier.NoModifier)
    grid._on_card_clicked(3, Qt.KeyboardModifier.NoModifier)

    assert [m.manifest.display_name for m in grid.selected_mods()] == ["M3"]


def test_ctrl_click_toggles_into_multi_selection(qtbot: QtBot) -> None:
    grid = _grid_with(qtbot, 4)
    grid._on_card_clicked(0, Qt.KeyboardModifier.NoModifier)
    grid._on_card_clicked(2, Qt.KeyboardModifier.ControlModifier)

    assert {m.manifest.display_name for m in grid.selected_mods()} == {"M0", "M2"}


def test_ctrl_click_again_deselects(qtbot: QtBot) -> None:
    grid = _grid_with(qtbot, 4)
    grid._on_card_clicked(0, Qt.KeyboardModifier.NoModifier)
    grid._on_card_clicked(2, Qt.KeyboardModifier.ControlModifier)
    grid._on_card_clicked(2, Qt.KeyboardModifier.ControlModifier)

    assert [m.manifest.display_name for m in grid.selected_mods()] == ["M0"]


def test_shift_click_selects_contiguous_range(qtbot: QtBot) -> None:
    grid = _grid_with(qtbot, 5)
    grid._on_card_clicked(1, Qt.KeyboardModifier.NoModifier)
    grid._on_card_clicked(3, Qt.KeyboardModifier.ShiftModifier)

    assert [m.manifest.display_name for m in grid.selected_mods()] == ["M1", "M2", "M3"]


def test_set_active_names_updates_card_active_state(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods([_mod("Foo", path="/mod/foo.scs"), _mod("Bar", path="/mod/bar.scs")])

    grid.set_active_names({"foo"})

    assert grid.cards()[0].is_active is True
    assert grid.cards()[1].is_active is False


def test_set_mods_active_state_does_not_confuse_workshop_stems(qtbot: QtBot) -> None:
    # two workshop mods, both with stem "universal" but different ids:
    # only the one whose active_name is listed may light up.
    base = "/games/SteamLib/steamapps/workshop/content/227300"
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods(
        [
            _mod("Mod A", path=f"{base}/111/universal.scs"),
            _mod("Mod B", path=f"{base}/222/universal.scs"),
        ],
        active_names={"mod_workshop_package.000000000000006F"},  # 111 == 0x6F
    )

    assert grid.cards()[0].is_active is True
    assert grid.cards()[1].is_active is False
