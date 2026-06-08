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


def test_set_mods_name_for_overrides_card_display_name(qtbot: QtBot) -> None:
    grid = ModCardGrid()
    qtbot.addWidget(grid)

    grid.set_mods(
        [_mod("ignored", path="/ws/227300/1/universal.scs")],
        name_for=lambda m: "Resolved Title",
    )

    assert grid.cards()[0]._display_name() == "Resolved Title"


def test_right_click_collapses_selection_and_delete_emits_list(qtbot):
    from pathlib import Path

    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.ui.widgets.mod_card_grid import ModCardGrid

    mods = [
        ScannedMod(path=Path("/mods/a.scs"), format=ScsFormat.ZIP, manifest=None, error=None),
        ScannedMod(path=Path("/mods/b.scs"), format=ScsFormat.ZIP, manifest=None, error=None),
    ]
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods(mods)

    # nothing selected; right-click on card 1 collapses selection onto it
    grid._collapse_selection_to(grid.cards()[1])
    assert grid.selected_mods() == [mods[1]]

    captured: list = []
    grid.delete_requested.connect(captured.append)
    grid.cards()[1].delete_requested.emit()
    assert captured == [[mods[1]]]


def test_select_all_selects_every_card(qtbot):
    from pathlib import Path

    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.ui.widgets.mod_card_grid import ModCardGrid

    mods = [
        ScannedMod(path=Path(f"/mods/m{i}.scs"), format=ScsFormat.ZIP, manifest=None, error=None)
        for i in range(4)
    ]
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods(mods)

    grid.select_all()

    assert grid.selected_mods() == mods  # all four


def test_select_all_only_covers_the_filtered_grid(qtbot):
    # the grid only ever holds the filtered list, so "all" = "all visible"
    from pathlib import Path

    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.ui.widgets.mod_card_grid import ModCardGrid

    local = [
        ScannedMod(path=Path("/mods/a.scs"), format=ScsFormat.ZIP, manifest=None, error=None),
        ScannedMod(path=Path("/mods/b.scs"), format=ScsFormat.ZIP, manifest=None, error=None),
    ]
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods(local)  # caller already filtered out workshop mods

    grid.select_all()

    assert [m.path.name for m in grid.selected_mods()] == ["a.scs", "b.scs"]


def _grid_and_mods(qtbot, n):
    from pathlib import Path

    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.ui.widgets.mod_card_grid import ModCardGrid

    mods = [
        ScannedMod(path=Path(f"/m/m{i}.scs"), format=ScsFormat.ZIP, manifest=None, error=None)
        for i in range(n)
    ]
    grid = ModCardGrid()
    qtbot.addWidget(grid)
    grid.set_mods(mods)
    return grid, mods


def test_columns_for_width_exact_fit():
    from easy_scsmodmanager.ui.theme import Theme
    from easy_scsmodmanager.ui.widgets.mod_card_grid import (
        _GRID_MARGIN,
        _GRID_SPACING,
        ModCardGrid,
    )

    w = Theme.MOD_CARD_WIDTH
    for n in (3, 4, 5):
        width = n * w + (n - 1) * _GRID_SPACING + 2 * _GRID_MARGIN
        assert ModCardGrid._columns_for_width(width) == n


def test_columns_for_width_never_below_one():
    from easy_scsmodmanager.ui.widgets.mod_card_grid import ModCardGrid

    assert ModCardGrid._columns_for_width(10) == 1  # tiny window -> 1, no zero-div


def test_reflow_changes_columns_keeps_cards(qtbot, monkeypatch):
    grid, mods = _grid_and_mods(qtbot, 9)
    monkeypatch.setattr(grid, "_compute_columns", lambda: 2)
    grid._relayout(force=True)
    assert grid._columns == 2
    before = [c.mod.path for c in grid.cards()]
    widths = [c.maximumWidth() for c in grid.cards()]

    monkeypatch.setattr(grid, "_compute_columns", lambda: 5)
    assert grid._relayout() is True  # cols changed -> rebuilt
    assert grid._columns == 5
    assert [c.mod.path for c in grid.cards()] == before  # same order, same count
    assert [c.maximumWidth() for c in grid.cards()] == widths  # card width unchanged


def test_reflow_guard_skips_when_columns_unchanged(qtbot, monkeypatch):
    grid, _ = _grid_and_mods(qtbot, 6)
    monkeypatch.setattr(grid, "_compute_columns", lambda: grid._columns)
    assert grid._relayout() is False  # no column change -> no rebuild


def test_selection_survives_reflow(qtbot, monkeypatch):
    grid, mods = _grid_and_mods(qtbot, 8)
    grid._set_single(5)
    assert 5 in grid._selected

    monkeypatch.setattr(grid, "_compute_columns", lambda: 4)
    grid._relayout(force=True)

    assert 5 in grid._selected
    assert grid.selected_mods() == [mods[5]]
