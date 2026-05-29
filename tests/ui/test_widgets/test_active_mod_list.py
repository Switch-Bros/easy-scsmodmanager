from __future__ import annotations

from PyQt6.QtCore import Qt
from pytestqt.qtbot import QtBot

from easy_scsmodmanager.services.profile_reader import ActiveMod
from easy_scsmodmanager.ui.widgets.active_mod_list import ActiveModList


def _list(qtbot: QtBot, names: list[str]) -> ActiveModList:
    widget = ActiveModList()
    qtbot.addWidget(widget)
    # input is profile order: index 0 = bottom of the in-game load order
    widget.set_active_mods([ActiveMod(n, n.upper()) for n in names])
    return widget


def test_ordered_active_mods_round_trips_profile_order(qtbot: QtBot) -> None:
    w = _list(qtbot, ["bottom", "mid", "top"])

    assert [m.name for m in w.ordered_active_mods()] == ["bottom", "mid", "top"]


def test_display_order_is_top_priority_first(qtbot: QtBot) -> None:
    w = _list(qtbot, ["bottom", "mid", "top"])

    # top of the visual list is the highest priority (last in profile order)
    assert [m.name for m in w.display_order()] == ["top", "mid", "bottom"]


def test_remove_mod_drops_it(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])

    w.remove_mod(ActiveMod("b", "B"))

    assert [m.name for m in w.ordered_active_mods()] == ["a", "c"]


def test_move_to_top_makes_mod_highest_priority(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])  # c is top priority

    w.move_to_top(ActiveMod("a", "A"))

    assert w.display_order()[0].name == "a"
    assert w.ordered_active_mods()[-1].name == "a"


def test_move_to_top_existing_mod_is_not_duplicated(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])

    w.move_to_top(ActiveMod("b", "B"))

    assert [m.name for m in w.display_order()] == ["b", "c", "a"]


def test_insert_mods_at_display_position(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])  # display: c, b, a

    w.insert_mods([ActiveMod("x", "X")], at=1)

    assert [m.name for m in w.display_order()] == ["c", "x", "b", "a"]


def test_move_rows_relocates_a_block(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c", "d"])  # display: d, c, b, a

    # move the block [c, b] (display rows 1,2) to the top (target row 0)
    w.move_rows([1, 2], 0)

    assert [m.name for m in w.display_order()] == ["c", "b", "d", "a"]


def test_order_changed_emitted_on_mutation(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b"])

    with qtbot.waitSignal(w.order_changed, timeout=500):
        w.remove_mod(ActiveMod("a", "A"))


def test_double_click_removes_the_mod(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])
    top_item = w._list.item(0)  # display top = "c"

    with qtbot.waitSignal(w.order_changed, timeout=500):
        w._on_item_double_clicked(top_item)

    assert "c" not in [m.name for m in w.display_order()]


def test_internal_reorder_signal_moves_rows(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c", "d"])  # display top->bottom: d, c, b, a

    # the list view signals a reorder of display rows 1,2 ("c","b") to the top
    w._list.reorder_requested.emit([1, 2], 0)

    assert [m.name for m in w.display_order()] == ["c", "b", "d", "a"]


def test_focus_active_selects_matching_row(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])

    assert w.focus_active("b") is True
    current = w._list.currentItem().data(Qt.ItemDataRole.UserRole)
    assert current.name == "b"


def test_focus_active_returns_false_for_unknown(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b"])

    assert w.focus_active("nope") is False
