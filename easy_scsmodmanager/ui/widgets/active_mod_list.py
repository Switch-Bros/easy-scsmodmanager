"""Right-hand panel listing the profile's active mods in priority order.

Each row uses a custom widget (see :mod:`active_list_widgets`): a large
thumbnail on top, the display name below. Selection survives the custom
widgets via the underlying QListWidget item the widget is paired with.

Group header rows (spacers) are injected between mod rows by build_rows();
those items carry UserRole=None and are non-interactive. Mods that sit in
the wrong group get an orange left border and a tooltip.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.core.load_order import (
    GROUPS,
    group_index_for_token,
    group_label_keys,
    group_repr_token,
)
from easy_scsmodmanager.core.load_order_layout import SpacerRow, build_rows
from easy_scsmodmanager.services.profile_reader import ActiveMod
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.widgets.active_list_widgets import (
    MOD_DRAG_MIME,
    ActiveListView,
    ActiveModItem,
    SpacerItem,
)
from easy_scsmodmanager.utils.i18n import t

__all__ = ["ActiveModList", "MOD_DRAG_MIME", "MOVE_TO_GROUP_AUTO"]

# spacer rows carry their group id here so the context menu can recognise the
# maps header (mod rows keep their ActiveMod under the default UserRole).
_SPACER_GROUP_ROLE = Qt.ItemDataRole.UserRole + 1

# group id of the maps block, reused for combo export/import + block lookups
_MAPS_GROUP_ID = "maps"

# sentinel group id for the "Automatic (own category)" menu entry: clear the
# pin and send each mod back to its natural group
MOVE_TO_GROUP_AUTO = "__auto__"


class ActiveModList(QWidget):
    """Title bar + scrollable list of active mods."""

    selection_changed = pyqtSignal(list)  # list[ActiveMod]
    mod_focus_requested = pyqtSignal(object)  # ActiveMod
    order_changed = pyqtSignal()  # the active list was reordered/edited
    mods_dropped = pyqtSignal(list, int, str)  # (grid path strings, target row, target group)
    reorder_pin_requested = pyqtSignal(list, str)  # (moved ActiveMods, target group) - pin first
    move_to_group_requested = pyqtSignal(object, str)  # (ActiveMod or list, group_id)
    export_combo_requested = pyqtSignal()  # right-click on the maps spacer
    import_combo_requested = pyqtSignal()  # right-click on the maps spacer

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # display order: index 0 is the top of the list (highest priority).
        # profile order is the reverse (index 0 = bottom of the load order).
        self._mods: list[ActiveMod] = []
        self._icon_for: Callable[[ActiveMod], bytes | None] | None = None
        self._installed_names: set[str] = set()
        self._category_for: Callable[[ActiveMod], tuple[str, ...]] | None = None
        self._conflict_for: Callable[[ActiveMod], str] | None = None
        self._misplaced: set[str] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        header = QHBoxLayout()
        self._title = QLabel(t("active_panel.title"))
        self._title.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 13px;")
        self._count = QLabel(t("active_panel.count", count=0))
        self._count.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
        self._count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._count)
        root.addLayout(header)

        self._list = ActiveListView()
        self._list.setDragEnabled(True)
        self._list.setAcceptDrops(True)
        self._list.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setDropIndicatorShown(True)  # the line showing where it lands
        self._list.setAutoScroll(True)  # scroll when dragging near the edges
        self._list.setAutoScrollMargin(140)  # generous edge zone (~3x default)
        self._list.reorder_requested.connect(self._on_reorder_requested)
        self._list.external_drop_requested.connect(self._on_external_drop)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT};
                border: 1px solid {Theme.SURFACE_HOVER};
                border-radius: 4px;
                padding: 2px;
            }}
            QListWidget::item {{
                border-radius: 4px;
                margin: 2px 0;
            }}
            QListWidget::item:selected {{
                background-color: {Theme.PRIMARY};
            }}
            """)
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        root.addWidget(self._list, 1)

        self._empty_hint = QLabel(t("active_panel.empty"))
        self._empty_hint.setStyleSheet(
            f"color: {Theme.TEXT_DIM}; font-style: italic; padding: 8px;"
        )
        self._empty_hint.setWordWrap(True)
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.hide()
        root.addWidget(self._empty_hint)

    def set_active_mods(
        self,
        mods: Iterable[ActiveMod],
        *,
        installed_names: set[str] | None = None,
        icon_for: Callable[[ActiveMod], bytes | None] | None = None,
        category_for: Callable[[ActiveMod], tuple[str, ...]] | None = None,
        conflict_for: Callable[[ActiveMod], str] | None = None,
    ) -> None:
        self._installed_names = installed_names or set()
        self._icon_for = icon_for
        self._category_for = category_for
        self._conflict_for = conflict_for
        # store top-priority first; the incoming list is profile order
        self._mods = list(reversed(list(mods)))
        self._rerender()

    def display_order(self) -> list[ActiveMod]:
        """Mods top-to-bottom as shown (top = highest priority)."""
        return list(self._mods)

    def ordered_active_mods(self) -> list[ActiveMod]:
        """Mods in profile order (index 0 = bottom) for the profile writer."""
        return list(reversed(self._mods))

    def remove_mod(self, mod: ActiveMod) -> None:
        self._mods = [m for m in self._mods if m.name != mod.name]
        self._rerender()
        self.order_changed.emit()

    def insert_into_group_block(self, mod: ActiveMod) -> None:
        """Activate ``mod`` into the bottom of its own group's block.

        Guard first: an already-active mod is only shown (focus), never moved -
        no reorder, no dirty Save. Otherwise it lands at the end of its
        effective group's block (the same token the renderer uses, so it is
        never misplaced). Existing overrides are honoured via _primary_token; no
        new pinning is set.
        """
        if any(m.name == mod.name for m in self._mods):
            self.focus_active(mod.name)
            return
        target_idx = group_index_for_token(self._primary_token(mod))
        insert_at = self._group_insert_index(self._mods, target_idx)
        self._mods = self._mods[:insert_at] + [mod] + self._mods[insert_at:]
        self._rerender()
        self.order_changed.emit()
        self.focus_active(mod.name)

    def insert_mods(self, mods: list[ActiveMod], at: int) -> None:
        """Insert mods at mod-display index ``at`` (0 = top of visual list)."""
        at = max(0, min(at, len(self._mods)))
        self._mods = self._mods[:at] + list(mods) + self._mods[at:]
        self._rerender()
        self.order_changed.emit()

    def insert_or_move(self, mods: list[ActiveMod], at: int) -> None:
        """Insert ``mods`` at mod-display index ``at``; mods already in the list
        are relocated there instead of duplicated. Lets the user drag an
        already-active mod from the grid straight to the right spot.

        Pass widget-row indices through ``widget_row_to_mod_index`` first when
        the caller receives a raw drop-target row from the list view.
        """
        names = {m.name for m in mods}
        removed_before = sum(1 for i, m in enumerate(self._mods) if m.name in names and i < at)
        kept = [m for m in self._mods if m.name not in names]
        target = max(0, min(at - removed_before, len(kept)))
        self._mods = kept[:target] + list(mods) + kept[target:]
        self._rerender()
        self.order_changed.emit()

    def widget_row_to_mod_index(self, widget_row: int) -> int:
        """Convert a QListWidget row index (which may include spacer rows) to
        a mod-array display index. Callers that receive raw drop-target rows
        from the list view should use this before calling insert_or_move."""
        count = 0
        for i in range(min(widget_row, self._list.count())):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) is not None:
                count += 1
        return count

    def move_rows(self, rows: list[int], target: int) -> None:
        """Move mod-display rows (indices into self._mods) to target mod-display index."""
        picked = sorted(set(rows))
        moving = [self._mods[r] for r in picked if r < len(self._mods)]
        if not moving:
            return
        remaining = [m for i, m in enumerate(self._mods) if i not in set(picked)]
        insert_at = target - sum(1 for r in picked if r < target)
        insert_at = max(0, min(insert_at, len(remaining)))
        self._mods = remaining[:insert_at] + moving + remaining[insert_at:]
        self._rerender()
        self.order_changed.emit()

    def move_mod_to_group(self, mod: ActiveMod, group_id: str) -> None:
        """Physically relocate ``mod`` to the end of group ``group_id``'s block.

        It lands just before the first mod whose group sorts later, so it sits
        at the bottom of its target block. The relative order of every other
        mod is left untouched. Pair with a group override set by the caller so
        the mod's effective group matches where it now sits.
        """
        target_idx = group_index_for_token(group_repr_token(group_id))
        remaining = [m for m in self._mods if m.name != mod.name]
        insert_at = self._group_insert_index(remaining, target_idx)
        self._mods = remaining[:insert_at] + [mod] + remaining[insert_at:]
        self._rerender()
        self.order_changed.emit()

    def move_mods_to_group(self, mods: list[ActiveMod], group_id: str) -> None:
        """Relocate several mods to the end of ``group_id``'s block at once.

        They keep their relative display order, and the whole batch is a single
        rerender + a single order_changed - so a multi-move stays one user
        action (no per-mod flicker, Save toggles once).
        """
        names = {m.name for m in mods}
        if not names:
            return
        moving = [m for m in self._mods if m.name in names]  # display order
        target_idx = group_index_for_token(group_repr_token(group_id))
        remaining = [m for m in self._mods if m.name not in names]
        insert_at = self._group_insert_index(remaining, target_idx)
        self._mods = remaining[:insert_at] + moving + remaining[insert_at:]
        self._rerender()
        self.order_changed.emit()

    def _group_insert_index(self, mods: Sequence[ActiveMod], target_idx: int) -> int:
        """First index in ``mods`` whose group sorts strictly later than
        ``target_idx`` (so a mod inserted there lands at the bottom of its
        block). The caller passes the list WITHOUT the mod being inserted, so
        this never rescans self._mods - that would be an off-by-one."""
        for i, other in enumerate(mods):
            if group_index_for_token(self._primary_token(other)) > target_idx:
                return i
        return len(mods)

    def group_for_widget_row(self, widget_row: int) -> str:
        """Group id of the region a drop at ``widget_row`` lands in.

        A drop ON a spacer takes that spacer's group (block start); on a mod row
        the nearest spacer above it; past the last row the last block's group.
        """
        count = self._list.count()
        if count == 0:
            return GROUPS[0].id
        row = min(widget_row, count - 1)
        for i in range(row, -1, -1):
            gid = self._list.item(i).data(_SPACER_GROUP_ROLE)
            if gid is not None:
                return str(gid)
        return GROUPS[0].id

    def _on_reorder_requested(self, widget_rows: list[int], widget_target: int) -> None:
        """Translate QListWidget widget-row indices from a drag to mod-display indices."""
        resolved: list[int] = []
        moving: list[ActiveMod] = []
        for r in widget_rows:
            if r < self._list.count():
                data = self._list.item(r).data(Qt.ItemDataRole.UserRole)
                if data is not None:
                    resolved.append(self.widget_row_to_mod_index(r))
                    moving.append(data)
        # pin FIRST so move_rows' rerender already sees the target group, then
        # move (position stays widget-internal); pin-after would only take on the
        # next action
        self.reorder_pin_requested.emit(moving, self.group_for_widget_row(widget_target))
        self.move_rows(resolved, self.widget_row_to_mod_index(widget_target))

    def _on_external_drop(self, paths: list[str], widget_target: int) -> None:
        """Map raw widget-row drop target to mod-space index before forwarding."""
        self.mods_dropped.emit(
            paths,
            self.widget_row_to_mod_index(widget_target),
            self.group_for_widget_row(widget_target),
        )

    def _on_context_menu(self, pos: object) -> None:
        from PyQt6.QtCore import QPoint

        if not isinstance(pos, QPoint):
            return
        item = self._list.itemAt(pos)
        if item is None:
            return
        mod = item.data(Qt.ItemDataRole.UserRole)
        if mod is None:
            if item.data(_SPACER_GROUP_ROLE) == _MAPS_GROUP_ID:
                self._show_maps_spacer_menu(pos)
            return
        # right-click on a row outside the selection collapses onto it (same
        # convention as the grid delete feature), so the move acts on what was
        # clicked, not a stale selection
        if not item.isSelected():
            self._list.clearSelection()
            item.setSelected(True)
            self._list.setCurrentItem(item)
        mods = self.selected_mods()

        menu = QMenu()
        submenu = menu.addMenu(t("active_panel.move_to_group"))
        if submenu is None:
            return
        # visible way back to automatic, set off above the groups
        auto = submenu.addAction(t("active_panel.move_to_group_auto"))
        if auto is not None:
            auto.triggered.connect(
                lambda checked=False: self.move_to_group_requested.emit(mods, MOVE_TO_GROUP_AUTO)
            )
        submenu.addSeparator()
        for g in GROUPS:
            action = submenu.addAction(t(g.label_keys[0]))
            if action is None:
                continue
            gid = g.id
            action.triggered.connect(
                lambda checked=False, gid=gid: self.move_to_group_requested.emit(mods, gid)
            )
        viewport = self._list.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(pos))

    def _show_maps_spacer_menu(self, pos: object) -> None:
        menu = QMenu()
        export = menu.addAction(t("map_combo.export"))
        if export is not None:
            export.triggered.connect(self.export_combo_requested.emit)
        importer = menu.addAction(t("map_combo.import"))
        if importer is not None:
            importer.triggered.connect(self.import_combo_requested.emit)
        viewport = self._list.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(pos))

    def maps_block(self) -> list[ActiveMod]:
        """Mods that sit in the Maps group, in display order (top to bottom)."""
        maps_idx = group_index_for_token(group_repr_token(_MAPS_GROUP_ID))
        return [m for m in self._mods if group_index_for_token(self._primary_token(m)) == maps_idx]

    def apply_combo_order(self, ordered: list[ActiveMod]) -> None:
        """Replace the maps block with ``ordered`` (already in combo order).

        The maps block is contiguous at the bottom of the load order, so we drop
        the reordered run in at the position of the first maps mod and keep every
        non-maps mod exactly where it was.
        """
        block_names = {m.name for m in ordered}
        result: list[ActiveMod] = []
        inserted = False
        for m in self._mods:
            if m.name in block_names:
                if not inserted:
                    result.extend(ordered)
                    inserted = True
            else:
                result.append(m)
        if not inserted:
            result.extend(ordered)
        self._mods = result
        self._rerender()
        self.order_changed.emit()

    def focus_active(self, name: str) -> bool:
        """Select + scroll to the active row with ``name``. False if absent."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            mod = item.data(Qt.ItemDataRole.UserRole)
            if mod is not None and mod.name == name:
                self._list.setCurrentItem(item)
                self._list.scrollToItem(item)
                return True
        return False

    def _primary_token(self, mod: ActiveMod) -> str:
        if self._category_for is not None:
            cats = self._category_for(mod)
            return cats[0] if cats else "other"
        return "other"

    def _expected_label(self, expected_group_id: str) -> str:
        return t(group_label_keys(expected_group_id)[0])

    def _rerender(self) -> None:
        scroll = self._list.verticalScrollBar().value()
        self._list.clear()
        self._misplaced = set()

        items: list[tuple[ActiveMod, str]] = [(mod, self._primary_token(mod)) for mod in self._mods]
        rows = build_rows(items)

        for row in rows:
            if isinstance(row, SpacerRow):
                spacer_widget = SpacerItem(row.group_id)
                item = QListWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.ItemDataRole.UserRole, None)
                item.setData(_SPACER_GROUP_ROLE, row.group_id)
                item.setSizeHint(spacer_widget.sizeHint())
                self._list.addItem(item)
                self._list.setItemWidget(item, spacer_widget)
            else:
                mod = row.mod
                icon_bytes = self._icon_for(mod) if self._icon_for is not None else None
                if row.misplaced:
                    self._misplaced.add(mod.name)
                tips: list[str] = []
                if row.misplaced:
                    tips.append(
                        t(
                            "load_order.misplaced_tooltip",
                            category=self._expected_label(row.expected_group_id),
                        )
                    )
                conflict_tip = self._conflict_for(mod) if self._conflict_for is not None else ""
                if conflict_tip:
                    tips.append(conflict_tip)
                widget = ActiveModItem(
                    mod,
                    icon_bytes,
                    is_missing=mod.name not in self._installed_names,
                    misplaced=row.misplaced,
                    conflict=bool(conflict_tip),
                    tooltip="\n\n".join(tips),
                )
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, mod)
                item.setSizeHint(widget.sizeHint())
                self._list.addItem(item)
                self._list.setItemWidget(item, widget)

        self._count.setText(t("active_panel.count", count=len(self._mods)))
        self._empty_hint.setVisible(len(self._mods) == 0)
        self._list.setVisible(len(self._mods) > 0)
        # keep the viewport where it was; activation re-scrolls via focus_active
        self._list.verticalScrollBar().setValue(scroll)

    def is_misplaced(self, name: str) -> bool:
        return name in self._misplaced

    def selected_mods(self) -> list[ActiveMod]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
            if self._list.item(i).isSelected()
            and self._list.item(i).data(Qt.ItemDataRole.UserRole) is not None
        ]

    def _on_selection_changed(self) -> None:
        self.selection_changed.emit(self.selected_mods())

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        mod = item.data(Qt.ItemDataRole.UserRole)
        if mod is not None:
            self.mod_focus_requested.emit(mod)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        # double-click pulls the mod out of the active list
        mod = item.data(Qt.ItemDataRole.UserRole)
        if mod is not None:
            self.remove_mod(mod)
