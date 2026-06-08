from __future__ import annotations

from PyQt6.QtCore import Qt
from pytestqt.qtbot import QtBot

from easy_scsmodmanager.services.profile_reader import ActiveMod
from easy_scsmodmanager.ui.widgets.active_list_widgets import (
    _SPACER_FONT_PX_MULTILINE,
    _SPACER_FONT_PX_SINGLE,
    _SPACER_HEIGHT,
    SpacerItem,
)
from easy_scsmodmanager.ui.widgets.active_mod_list import (
    _MAPS_GROUP_ID,
    _SPACER_GROUP_ROLE,
    ActiveModList,
)


def _mods(*names: str) -> list[ActiveMod]:
    return [ActiveMod(name=n, display_name=n) for n in names]


def test_spacers_added_and_not_in_export(qtbot: QtBot) -> None:
    w = ActiveModList()
    qtbot.addWidget(w)
    cat: dict[str, tuple[str, ...]] = {"snd": ("sound",), "trk": ("truck",)}
    # set_active_mods receives profile order and reverses it to display order.
    # Passing [snd, trk] -> _mods = [trk, snd] (trk = top/highest priority).
    # ordered_active_mods() reverses back -> [snd, trk].
    w.set_active_mods(_mods("snd", "trk"), category_for=lambda m: cat[m.name])
    assert [m.name for m in w.ordered_active_mods()] == ["snd", "trk"]
    # spacer rows should push count above 2
    assert w._list.count() > 2


def test_misplaced_mod_marked(qtbot: QtBot) -> None:
    w = ActiveModList()
    qtbot.addWidget(w)
    cat: dict[str, tuple[str, ...]] = {"map1": ("map",), "snd": ("sound",)}
    # set_active_mods(profile_order=[snd, map1])
    # -> _mods (display, top-first) = [map1, snd]
    # map1 (map, group idx 11) is first -> advances current to 11.
    # snd (sound, group idx 2) follows -> 2 < 11 => misplaced.
    w.set_active_mods(_mods("snd", "map1"), category_for=lambda m: cat[m.name])
    assert w.is_misplaced("snd") is True
    assert w.is_misplaced("map1") is False


def test_selected_mods_skips_spacers(qtbot: QtBot) -> None:
    w = ActiveModList()
    qtbot.addWidget(w)
    w.set_active_mods(_mods("a"), category_for=lambda m: ("truck",))
    w._list.selectAll()
    assert all(m is not None for m in w.selected_mods())


def test_no_category_for_still_renders(qtbot: QtBot) -> None:
    """Without category_for, all mods fall into ui_other; no spacer crash."""
    w = ActiveModList()
    qtbot.addWidget(w)
    w.set_active_mods(_mods("a", "b"))
    assert w._list.count() > 2
    assert [m.name for m in w.ordered_active_mods()] == ["a", "b"]


def test_focus_active_finds_mod_among_spacers(qtbot: QtBot) -> None:
    w = ActiveModList()
    qtbot.addWidget(w)
    cat: dict[str, tuple[str, ...]] = {"snd": ("sound",), "trk": ("truck",)}
    w.set_active_mods(_mods("snd", "trk"), category_for=lambda m: cat[m.name])
    assert w.focus_active("trk") is True
    item = w._list.currentItem()
    assert item is not None
    assert item.data(Qt.ItemDataRole.UserRole).name == "trk"


def test_is_misplaced_false_for_unknown_name(qtbot: QtBot) -> None:
    w = ActiveModList()
    qtbot.addWidget(w)
    w.set_active_mods([])
    assert w.is_misplaced("phantom") is False


def test_spacer_item_reserves_full_height(qtbot: QtBot) -> None:
    """sizeHint must equal the fixed height, else list items overlap."""
    spacer = SpacerItem("sound")
    qtbot.addWidget(spacer)
    assert spacer.sizeHint().height() == _SPACER_HEIGHT


def test_single_line_spacer_uses_large_font(qtbot: QtBot) -> None:
    from PyQt6.QtWidgets import QLabel

    spacer = SpacerItem("sound")
    qtbot.addWidget(spacer)
    lbls = spacer.findChildren(QLabel)
    assert len(lbls) == 1
    assert f"font-size: {_SPACER_FONT_PX_SINGLE}px" in lbls[0].styleSheet()


def test_map_base_spacer_uses_compact_font_and_three_lines(qtbot: QtBot) -> None:
    from PyQt6.QtWidgets import QLabel

    spacer = SpacerItem("map_base")
    qtbot.addWidget(spacer)
    lbls = spacer.findChildren(QLabel)
    assert len(lbls) == 3  # world / background / loading
    assert all(f"font-size: {_SPACER_FONT_PX_MULTILINE}px" in lbl.styleSheet() for lbl in lbls)


def test_move_to_group_relocates_misplaced_mod_upward(qtbot: QtBot) -> None:
    """A sound mod stranded below a truck mod moves up into the sound block
    and stops being misplaced."""
    w = ActiveModList()
    qtbot.addWidget(w)
    cat: dict[str, tuple[str, ...]] = {"trk": ("truck",), "snd": ("sound",)}
    # display order top-first = [trk, snd]; snd (sound, idx 2) below trk
    # (truck, idx 10) is misplaced.
    w.set_active_mods(_mods("snd", "trk"), category_for=lambda m: cat[m.name])
    assert w.is_misplaced("snd") is True

    snd = next(m for m in w.display_order() if m.name == "snd")
    w.move_mod_to_group(snd, "sound")

    assert [m.name for m in w.display_order()] == ["snd", "trk"]
    assert w.is_misplaced("snd") is False


def test_move_to_group_relocates_mod_downward(qtbot: QtBot) -> None:
    """Moving a mod to a later group drops it to the bottom of that block."""
    w = ActiveModList()
    qtbot.addWidget(w)
    cat: dict[str, tuple[str, ...]] = {"snd": ("sound",), "trk": ("truck",)}
    # display top-first = [snd, trk], already in order.
    w.set_active_mods(_mods("trk", "snd"), category_for=lambda m: cat[m.name])
    assert [m.name for m in w.display_order()] == ["snd", "trk"]

    snd = next(m for m in w.display_order() if m.name == "snd")
    w.move_mod_to_group(snd, "trucks")

    # snd now sits after the truck mod (end of the trucks block).
    assert [m.name for m in w.display_order()] == ["trk", "snd"]


def _maps_list(qtbot: QtBot) -> ActiveModList:
    w = ActiveModList()
    qtbot.addWidget(w)
    cat: dict[str, tuple[str, ...]] = {"snd": ("sound",), "m1": ("map",), "m2": ("map",)}
    # display top-first = [snd, m1, m2]
    w.set_active_mods(_mods("m2", "m1", "snd"), category_for=lambda m: cat[m.name])
    return w


def test_maps_block_returns_only_map_mods_in_order(qtbot: QtBot) -> None:
    w = _maps_list(qtbot)
    assert [m.name for m in w.maps_block()] == ["m1", "m2"]


def test_apply_combo_order_reorders_block_only(qtbot: QtBot) -> None:
    w = _maps_list(qtbot)
    block = w.maps_block()
    reversed_block = list(reversed(block))
    w.apply_combo_order(reversed_block)
    # the non-map mod keeps its slot, only the maps block flipped
    assert [m.name for m in w.display_order()] == ["snd", "m2", "m1"]


def test_conflict_marks_name_and_sets_tooltip(qtbot: QtBot) -> None:
    w = ActiveModList()
    qtbot.addWidget(w)
    from easy_scsmodmanager.services.conflict_detect import Severity

    w.set_active_mods(
        _mods("a"),
        category_for=lambda m: ("truck",),
        conflict_for=lambda m: "shares def/x with B" if m.name == "a" else "",
        severity_for=lambda m: Severity.PARTIAL if m.name == "a" else None,
    )
    for i in range(w._list.count()):
        item = w._list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) is not None:
            widget = w._list.itemWidget(item)
            assert widget.toolTip() == "shares def/x with B"
            # rich-text label: the coloured partial glyph prefixes the name
            assert "⚠" in widget._name.text()
            assert not w._legend.isHidden()  # legend appears with a conflict
            return
    raise AssertionError("no mod row found")


def test_no_conflict_leaves_name_plain(qtbot: QtBot) -> None:
    w = ActiveModList()
    qtbot.addWidget(w)
    w.set_active_mods(_mods("a"), category_for=lambda m: ("truck",), conflict_for=lambda m: "")
    for i in range(w._list.count()):
        item = w._list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) is not None:
            widget = w._list.itemWidget(item)
            assert not widget._name.text().startswith("⚠")
            return
    raise AssertionError("no mod row found")


def test_maps_spacer_carries_group_id(qtbot: QtBot) -> None:
    w = _maps_list(qtbot)
    roles = [
        w._list.item(i).data(_SPACER_GROUP_ROLE)
        for i in range(w._list.count())
        if w._list.item(i).data(_SPACER_GROUP_ROLE) is not None
    ]
    assert _MAPS_GROUP_ID in roles


def test_full_severity_uses_crossed_circle_glyph(qtbot: QtBot) -> None:
    from easy_scsmodmanager.services.conflict_detect import Severity

    w = ActiveModList()
    qtbot.addWidget(w)
    w.set_active_mods(
        _mods("a"),
        category_for=lambda m: ("truck",),
        severity_for=lambda m: Severity.FULL if m.name == "a" else None,
    )
    for i in range(w._list.count()):
        item = w._list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) is not None:
            widget = w._list.itemWidget(item)
            assert "⊘" in widget._name.text()  # crossed circle, distinct from triangle
            return
    raise AssertionError("no mod row found")
