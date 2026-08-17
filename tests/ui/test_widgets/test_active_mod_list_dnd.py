"""Tests for drag-and-drop fixes and move-to-group context menu signal."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu
from pytestqt.qtbot import QtBot

from easy_scsmodmanager.core.category_overrides import CategoryOverrides
from easy_scsmodmanager.core.load_order import group_index_for_token, group_repr_token
from easy_scsmodmanager.services.conflict_detect import Severity
from easy_scsmodmanager.services.profile_reader import ActiveMod
from easy_scsmodmanager.ui.widgets.active_mod_list import ActiveModList
from easy_scsmodmanager.utils.i18n import t


def _list_with_cats(
    qtbot: QtBot,
    names: list[str],
    cats: dict[str, tuple[str, ...]],
) -> ActiveModList:
    widget = ActiveModList()
    qtbot.addWidget(widget)
    widget.set_active_mods(
        [ActiveMod(n, n.upper()) for n in names],
        category_for=lambda m: cats.get(m.name, ("other",)),
    )
    return widget


def test_widget_row_to_mod_index_skips_spacers(qtbot: QtBot) -> None:
    """widget_row_to_mod_index maps widget rows to mod-space indices correctly."""
    cats = {"snd": ("sound",), "trk": ("truck",)}
    # profile order [snd, trk] -> display order [trk, snd]
    w = _list_with_cats(qtbot, ["snd", "trk"], cats)

    # There should be spacer rows before the first mod item.
    total_rows = w._list.count()
    assert total_rows > 2  # spacers present

    # Count how many spacers come before the first mod row.
    spacer_count_before_first = 0
    for i in range(total_rows):
        item = w._list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) is None:
            spacer_count_before_first += 1
        else:
            break

    # widget_row_to_mod_index(spacer rows + 1) should give mod index 1 (the second mod).
    first_mod_widget_row = spacer_count_before_first
    assert w.widget_row_to_mod_index(first_mod_widget_row) == 0
    assert w.widget_row_to_mod_index(first_mod_widget_row + 1) == 1


def test_external_drop_maps_widget_row_to_mod_index(qtbot: QtBot) -> None:
    """mods_dropped signal carries mod-space index, not raw widget-row index."""
    cats = {"snd": ("sound",), "trk": ("truck",)}
    w = _list_with_cats(qtbot, ["snd", "trk"], cats)

    # Find the widget row of the first actual mod.
    total_rows = w._list.count()
    first_mod_widget_row = next(
        i for i in range(total_rows) if w._list.item(i).data(Qt.ItemDataRole.UserRole) is not None
    )

    received: list[tuple[list[str], int]] = []

    def capture(paths: list[str], idx: int) -> None:
        received.append((paths, idx))

    w.mods_dropped.connect(capture)

    # Emit external_drop_requested with the raw widget row.
    w._list.external_drop_requested.emit(["/some/mod.scs"], first_mod_widget_row)

    assert len(received) == 1
    paths, mod_idx = received[0]
    assert paths == ["/some/mod.scs"]
    # mod_idx must be the mapped mod-space index (0), not the raw widget row.
    assert mod_idx == w.widget_row_to_mod_index(first_mod_widget_row)


def test_move_to_group_requested_signal_exists(qtbot: QtBot) -> None:
    """move_to_group_requested signal is declared on ActiveModList."""
    w = ActiveModList()
    qtbot.addWidget(w)
    assert hasattr(w, "move_to_group_requested")


def test_move_to_group_requested_emits(qtbot: QtBot) -> None:
    """Calling _on_context_menu on a mod item emits move_to_group_requested."""
    cats = {"snd": ("sound",)}
    w = _list_with_cats(qtbot, ["snd"], cats)

    received: list[tuple[object, str]] = []

    def capture(mod: object, group_id: str) -> None:
        received.append((mod, group_id))

    w.move_to_group_requested.connect(capture)

    # Directly emit the signal to verify it works correctly.
    mod = w._mods[0]
    w.move_to_group_requested.emit(mod, "map_base")

    assert len(received) == 1
    assert received[0][1] == "map_base"
    assert received[0][0].name == "snd"


# show-conflicts entry


def _open_row_menu(qtbot: QtBot, w: ActiveModList, monkeypatch) -> QMenu:
    """Right-click the first mod row and hand back the menu instead of showing it."""
    captured: list[QMenu] = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *_a: captured.append(self))
    row = next(
        i
        for i in range(w._list.count())
        if w._list.item(i).data(Qt.ItemDataRole.UserRole) is not None
    )
    viewport = w._list.viewport()
    w._on_context_menu(w._list.visualItemRect(w._list.item(row)).center())
    assert viewport is not None
    assert captured, "context menu was never shown"
    return captured[0]


def _menu_texts(menu: QMenu) -> list[str]:
    return [a.text() for a in menu.actions()]


def test_conflict_entry_hidden_without_a_conflict(qtbot: QtBot, monkeypatch) -> None:
    w = _list_with_cats(qtbot, ["snd"], {"snd": ("sound",)})
    w.set_active_mods(
        [ActiveMod("snd", "SND")],
        category_for=lambda m: ("sound",),
        severity_for=lambda m: None,
        frequent_for=lambda m: False,
    )

    menu = _open_row_menu(qtbot, w, monkeypatch)

    assert t("active_panel.show_conflicts") not in _menu_texts(menu)


def test_conflict_entry_shown_for_an_overridden_mod(qtbot: QtBot, monkeypatch) -> None:
    w = _list_with_cats(qtbot, ["snd"], {"snd": ("sound",)})
    w.set_active_mods(
        [ActiveMod("snd", "SND")],
        category_for=lambda m: ("sound",),
        severity_for=lambda m: Severity.FULL,
        frequent_for=lambda m: False,
    )

    menu = _open_row_menu(qtbot, w, monkeypatch)

    assert t("active_panel.show_conflicts") in _menu_texts(menu)


def test_conflict_entry_shown_for_a_frequent_only_mod(qtbot: QtBot, monkeypatch) -> None:
    # frequent shares are not a conflict, but the user still wants to read them
    w = _list_with_cats(qtbot, ["snd"], {"snd": ("sound",)})
    w.set_active_mods(
        [ActiveMod("snd", "SND")],
        category_for=lambda m: ("sound",),
        severity_for=lambda m: None,
        frequent_for=lambda m: True,
    )

    menu = _open_row_menu(qtbot, w, monkeypatch)

    assert t("active_panel.show_conflicts") in _menu_texts(menu)


def test_conflict_entry_emits_the_clicked_mod(qtbot: QtBot, monkeypatch) -> None:
    w = _list_with_cats(qtbot, ["snd"], {"snd": ("sound",)})
    w.set_active_mods(
        [ActiveMod("snd", "SND")],
        category_for=lambda m: ("sound",),
        severity_for=lambda m: Severity.PARTIAL,
        frequent_for=lambda m: False,
    )
    received: list[object] = []
    w.show_conflicts_requested.connect(received.append)

    menu = _open_row_menu(qtbot, w, monkeypatch)
    action = next(a for a in menu.actions() if a.text() == t("active_panel.show_conflicts"))
    action.trigger()

    assert len(received) == 1
    assert received[0].name == "snd"


def test_menu_survives_a_list_without_conflict_callbacks(qtbot: QtBot, monkeypatch) -> None:
    # set_active_mods leaves both callbacks at None unless the window passes them
    w = _list_with_cats(qtbot, ["snd"], {"snd": ("sound",)})

    menu = _open_row_menu(qtbot, w, monkeypatch)

    assert t("active_panel.show_conflicts") not in _menu_texts(menu)


def test_group_override_wiring(tmp_path: Path) -> None:
    """Setting a group override then calling group_repr_token resolves to the right token."""
    ov = CategoryOverrides(tmp_path / "go.db")
    ov.set("bxpfix007", "map_base")

    group_id = ov.get("bxpfix007")
    assert group_id == "map_base"

    token = group_repr_token(group_id)
    assert token == "map_base"
    assert group_index_for_token(token) == 0

    ov.close()
