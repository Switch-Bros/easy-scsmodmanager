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


_TOKENS = {"a_trailer": ("trailer",), "b_truck": ("truck",)}


def _grouped(qtbot: QtBot, names: list[str]) -> ActiveModList:
    widget = ActiveModList()
    qtbot.addWidget(widget)
    widget.set_active_mods(
        [ActiveMod(n, n.upper()) for n in names],
        category_for=lambda m: _TOKENS.get(m.name, ("other",)),
    )
    return widget


def test_insert_into_group_block_appends_to_end_of_block(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])  # all "other"

    w.insert_into_group_block(ActiveMod("x", "X"))

    # lands at the bottom of the (single) block, not forced to the top
    assert [m.name for m in w.display_order()] == ["c", "b", "a", "x"]


def test_insert_into_group_block_no_duplicate_for_active(qtbot: QtBot) -> None:
    # migrated no-duplicate test - also the L2 guard
    w = _list(qtbot, ["a", "b", "c"])

    w.insert_into_group_block(ActiveMod("b", "B"))

    assert [m.name for m in w.display_order()] == ["c", "b", "a"]


def test_l2_guard_already_active_emits_nothing_and_selects(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b", "c"])
    calls: list[int] = []
    w.order_changed.connect(lambda: calls.append(1))

    w.insert_into_group_block(ActiveMod("b", "B"))

    assert calls == []  # no reorder, Save stays clean
    assert w._list.currentItem().data(Qt.ItemDataRole.UserRole).name == "b"


def test_successful_insert_emits_order_changed_once_and_selects(qtbot: QtBot) -> None:
    w = _list(qtbot, ["a", "b"])
    calls: list[int] = []
    w.order_changed.connect(lambda: calls.append(1))

    w.insert_into_group_block(ActiveMod("x", "X"))

    assert calls == [1]
    assert w._list.currentItem().data(Qt.ItemDataRole.UserRole).name == "x"


def test_group_insert_index_is_shared_helper(qtbot: QtBot) -> None:
    from easy_scsmodmanager.core.load_order import group_index_for_token

    w = _grouped(qtbot, ["b_truck"])
    trailer_idx = group_index_for_token("trailer")
    truck_idx = group_index_for_token("truck")
    # a trailer sorts before the existing truck -> index 0; a second truck -> end
    assert w._group_insert_index(w.display_order(), trailer_idx) == 0
    assert w._group_insert_index(w.display_order(), truck_idx) == 1


def test_llbbc_buggy_order_is_misplaced(qtbot: QtBot) -> None:
    # display [b_truck (top), a_trailer (below)] - trailer under trucks = misplaced
    w = _grouped(qtbot, ["a_trailer", "b_truck"])
    assert w.is_misplaced("a_trailer") is True


def test_llbbc_activation_is_order_invariant_and_not_misplaced(qtbot: QtBot) -> None:
    forward = _grouped(qtbot, [])
    forward.insert_into_group_block(ActiveMod("a_trailer", "A"))
    forward.insert_into_group_block(ActiveMod("b_truck", "B"))

    backward = _grouped(qtbot, [])
    backward.insert_into_group_block(ActiveMod("b_truck", "B"))
    backward.insert_into_group_block(ActiveMod("a_trailer", "A"))

    for w in (forward, backward):
        assert w.is_misplaced("a_trailer") is False
        assert w.is_misplaced("b_truck") is False
        # trailers sort above trucks regardless of activation order
        assert [m.name for m in w.display_order()] == ["a_trailer", "b_truck"]


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


def _rel(order: list[str], a: str, b: str) -> bool:
    return order.index(a) < order.index(b)


def test_move_mods_to_group_batch_one_emit_relative_order(qtbot: QtBot) -> None:
    widget = ActiveModList()
    qtbot.addWidget(widget)
    cat = {"x": ("trailer",), "y": ("truck",), "z": ("trailer",)}
    widget.set_active_mods(
        [ActiveMod(n, n.upper()) for n in ["x", "y", "z"]],
        category_for=lambda m: cat.get(m.name, ("other",)),
    )
    before = [m.name for m in widget.display_order()]
    calls: list[int] = []
    widget.order_changed.connect(lambda: calls.append(1))

    widget.move_mods_to_group([ActiveMod("x", "X"), ActiveMod("z", "Z")], "trucks")

    assert calls == [1]  # one emit for the whole batch
    order = [m.name for m in widget.display_order()]
    # whatever their original relative order was, it survives the batch move
    assert _rel(order, "x", "z") == _rel(before, "x", "z")


def test_move_mods_to_group_across_two_blocks_keeps_order(qtbot: QtBot) -> None:
    widget = ActiveModList()
    qtbot.addWidget(widget)
    cat = {"a": ("trailer",), "b": ("truck",), "c": ("other",)}
    widget.set_active_mods(
        [ActiveMod(n, n.upper()) for n in ["a", "b", "c"]],
        category_for=lambda m: cat.get(m.name, ("other",)),
    )
    before = [m.name for m in widget.display_order()]
    # selection spans two blocks (a=trailer, c=other) -> relative order stays
    widget.move_mods_to_group([ActiveMod("c", "C"), ActiveMod("a", "A")], "trucks")

    order = [m.name for m in widget.display_order()]
    assert _rel(order, "a", "c") == _rel(before, "a", "c")


def test_group_for_widget_row(qtbot: QtBot) -> None:
    from PyQt6.QtCore import Qt as _Qt

    from easy_scsmodmanager.ui.widgets.active_mod_list import _SPACER_GROUP_ROLE

    w = _grouped(qtbot, ["a_trailer", "b_truck"])
    # a drop ON a spacer takes that spacer's group; the row just below it (a
    # mod) is in the same region
    for i in range(w._list.count()):
        gid = w._list.item(i).data(_SPACER_GROUP_ROLE)
        if gid == "trucks":
            assert w.group_for_widget_row(i) == "trucks"  # on the spacer
            below = w._list.item(i + 1)
            if below is not None and below.data(_Qt.ItemDataRole.UserRole) is not None:
                assert w.group_for_widget_row(i + 1) == "trucks"  # mod under it
    # all group headers render; maps is always last, so a drop past the end
    # falls into the maps region
    assert w.group_for_widget_row(w._list.count() + 5) == "maps"


def test_external_drop_emits_group(qtbot: QtBot) -> None:
    w = _grouped(qtbot, ["a_trailer", "b_truck"])
    captured: list = []
    w.mods_dropped.connect(lambda paths, row, gid: captured.append((paths, row, gid)))

    w._on_external_drop(["/x.scs"], w._list.count())  # drop past the end

    assert len(captured) == 1
    assert captured[0][2] == "maps"  # last region
