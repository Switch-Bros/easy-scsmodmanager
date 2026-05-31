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
    # item(0) may now be a spacer row; find the first actual mod item.
    top_item = next(
        w._list.item(i)
        for i in range(w._list.count())
        if w._list.item(i).data(Qt.ItemDataRole.UserRole) is not None
    )
    assert top_item.data(Qt.ItemDataRole.UserRole).name == "c"  # display top = "c"

    with qtbot.waitSignal(w.order_changed, timeout=500):
        w._on_item_double_clicked(top_item)

    assert "c" not in [m.name for m in w.display_order()]


def test_internal_reorder_signal_moves_rows(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c", "d"])  # display top->bottom: d, c, b, a

    # reorder_requested carries widget-row indices; spacers precede the mods.
    # Find the widget rows for "c" and "b" and the row of "d" as target.
    from PyQt6.QtCore import Qt as _Qt

    row_of = {
        w._list.item(i).data(_Qt.ItemDataRole.UserRole).name: i
        for i in range(w._list.count())
        if w._list.item(i).data(_Qt.ItemDataRole.UserRole) is not None
    }
    # emit: move "c" and "b" to before "d" (= the top mod position)
    w._list.reorder_requested.emit([row_of["c"], row_of["b"]], row_of["d"])

    assert [m.name for m in w.display_order()] == ["c", "b", "d", "a"]


def test_focus_active_selects_matching_row(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])

    assert w.focus_active("b") is True
    current = w._list.currentItem().data(Qt.ItemDataRole.UserRole)
    assert current.name == "b"


def test_focus_active_returns_false_for_unknown(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b"])

    assert w.focus_active("nope") is False


def test_insert_or_move_relocates_an_already_active_mod(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c", "d"])  # display top->bottom: d, c, b, a

    # "a" is at the very bottom; drop it at the top
    w.insert_or_move([ActiveMod("a", "A")], at=0)

    assert w.display_order()[0].name == "a"
    assert [m.name for m in w.display_order()].count("a") == 1  # moved, not duplicated


def test_insert_or_move_inserts_a_new_mod(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b"])  # display: b, a

    w.insert_or_move([ActiveMod("x", "X")], at=1)

    assert [m.name for m in w.display_order()] == ["b", "x", "a"]


def test_insert_or_move_relocates_a_block(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c", "d", "e"])  # display: e, d, c, b, a

    # drag the bottom block [b, a] up to the top
    w.insert_or_move([ActiveMod("b", "B"), ActiveMod("a", "A")], at=0)

    assert [m.name for m in w.display_order()][:2] == ["b", "a"]
    assert len(w.display_order()) == 5  # nothing duplicated or lost
