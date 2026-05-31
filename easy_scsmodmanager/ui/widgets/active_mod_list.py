"""Right-hand panel listing the profile's active mods in priority order.

Each row uses a custom widget: a large 200x112 thumbnail on top, the
display name below. Selection survives the custom widgets via the
underlying QListWidget item the widget is paired with.

Group header rows (spacers) are injected between mod rows by build_rows();
those items carry UserRole=None and are non-interactive. Mods that sit in
the wrong group get an orange left border and a tooltip.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSizePolicy,
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
from easy_scsmodmanager.utils.i18n import t

# Orange used for misplaced-mod indicator; Theme has no dedicated constant.
_MISPLACED_COLOUR = "#FFAE00"

THUMB_SIZE = QSize(Theme.ACTIVE_THUMBNAIL_WIDTH, Theme.ACTIVE_THUMBNAIL_HEIGHT)

# carried by a drag coming from the mod grid: newline-joined mod path strings
MOD_DRAG_MIME = "application/x-escsmm-modpaths"

# gentle animated wheel scrolling for the tall active rows
WHEEL_STEP_PX = 80
WHEEL_DURATION_MS = 200

# every group header is as tall as the 3-line map_base block (+10px top/bottom)
_SPACER_HEIGHT = 80


class _ActiveListView(QListWidget):
    """List view that turns drops into model-level reorder / insert signals.

    Internal drag (rows dragged within the list) -> reorder_requested.
    A drag from the grid carrying MOD_DRAG_MIME -> external_drop_requested.
    We never call super().dropEvent so Qt does not move the item widgets
    itself - the owner rebuilds the list from its model instead.
    """

    reorder_requested = pyqtSignal(list, int)  # (source rows, target row)
    external_drop_requested = pyqtSignal(list, int)  # (mod path strings, target row)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._wheel_anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._wheel_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._wheel_anim.setDuration(WHEEL_DURATION_MS)

    def wheelEvent(self, event: object) -> None:  # noqa: N802
        notches = event.angleDelta().y() / 120.0  # type: ignore[attr-defined]
        if not notches:  # touchpad pixel-scroll: let Qt handle it natively
            super().wheelEvent(event)
            return
        bar = self.verticalScrollBar()
        running = self._wheel_anim.state() == QPropertyAnimation.State.Running
        base = self._wheel_anim.endValue() if running else bar.value()
        target = max(bar.minimum(), min(bar.maximum(), int(base - notches * WHEEL_STEP_PX)))
        self._wheel_anim.stop()
        self._wheel_anim.setStartValue(bar.value())
        self._wheel_anim.setEndValue(target)
        self._wheel_anim.start()
        event.accept()  # type: ignore[attr-defined]

    def _target_row(self, event: object) -> int:
        pos = event.position().toPoint()  # type: ignore[attr-defined]
        idx = self.indexAt(pos)
        if not idx.isValid():
            return self.count()
        row = idx.row()
        # dropping on the lower half of a row means "after it"
        if pos.y() > self.visualRect(idx).center().y():
            row += 1
        return row

    def _accepts(self, event: object) -> bool:
        return event.source() is self or event.mimeData().hasFormat(MOD_DRAG_MIME)  # type: ignore[attr-defined]

    def dragEnterEvent(self, event: object) -> None:  # noqa: N802
        super().dragEnterEvent(event)
        event.accept() if self._accepts(event) else event.ignore()  # type: ignore[attr-defined]

    def dragMoveEvent(self, event: object) -> None:  # noqa: N802
        # let the base view run its edge auto-scroll + draw the drop indicator,
        # then keep our own accept/ignore decision
        super().dragMoveEvent(event)
        event.accept() if self._accepts(event) else event.ignore()  # type: ignore[attr-defined]

    def dropEvent(self, event: object) -> None:  # noqa: N802
        target = self._target_row(event)
        if event.source() is self:  # type: ignore[attr-defined]
            rows = sorted({i.row() for i in self.selectedIndexes()})
            self.reorder_requested.emit(rows, target)
            event.accept()  # type: ignore[attr-defined]
        elif event.mimeData().hasFormat(MOD_DRAG_MIME):  # type: ignore[attr-defined]
            raw = bytes(event.mimeData().data(MOD_DRAG_MIME)).decode("utf-8")  # type: ignore[attr-defined]
            paths = [p for p in raw.split("\n") if p]
            self.external_drop_requested.emit(paths, target)
            event.accept()  # type: ignore[attr-defined]
        else:
            event.ignore()  # type: ignore[attr-defined]


class _SpacerItem(QWidget):
    """Header row separating load-order groups in the active list.

    Displays one centered label per key returned by group_label_keys(group_id).
    map_base shows three lines; all other groups show one.
    """

    def __init__(self, group_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_SPACER_HEIGHT)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(2)
        root.addStretch(1)
        for key in group_label_keys(group_id):
            lbl = QLabel(t(key))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {Theme.ACCENT};"
                "font-size: 14px;"
                "font-weight: bold;"
                "letter-spacing: 1px;"
            )
            root.addWidget(lbl)
        root.addStretch(1)

    def sizeHint(self) -> QSize:  # noqa: N802
        # setFixedHeight does not feed into the layout's sizeHint, so the list
        # item would reserve only the label height and the spacer would overlap
        # its neighbour. Pin the hint to the fixed height we actually draw.
        return QSize(super().sizeHint().width(), _SPACER_HEIGHT)


class ActiveModItem(QWidget):
    """Single row in the active list: large thumbnail + name."""

    def __init__(
        self,
        mod: ActiveMod,
        icon_bytes: bytes | None,
        *,
        is_missing: bool,
        misplaced: bool = False,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mod = mod

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 6)
        root.setSpacing(4)

        self._thumb = QLabel()
        self._thumb.setFixedSize(THUMB_SIZE)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(_thumbnail_style())
        self._set_thumbnail(icon_bytes)
        root.addWidget(self._thumb, 0, Qt.AlignmentFlag.AlignCenter)

        self._name = QLabel(_format_label(mod))
        self._name.setStyleSheet(f"color: {Theme.TEXT}; font-size: 11px; font-weight: 600;")
        self._name.setWordWrap(True)
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root.addWidget(self._name)

        if is_missing:
            self._missing = QLabel("⚠ " + t("status.missing_from_disk"))
            self._missing.setStyleSheet(f"color: {Theme.DANGER}; font-size: 10px;")
            self._missing.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(self._missing)

        if misplaced:
            # a bare QWidget only paints its own QSS border when told to style
            # its background; without this the left border never shows.
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setObjectName("misplaced_mod_item")
            self.setStyleSheet(
                f"#misplaced_mod_item {{ border-left: 3px solid {_MISPLACED_COLOUR}; }}"
            )
        if tooltip:
            self.setToolTip(tooltip)

    def _set_thumbnail(self, icon_bytes: bytes | None) -> None:
        if icon_bytes:
            pix = QPixmap()
            if pix.loadFromData(icon_bytes):
                self._thumb.setPixmap(
                    pix.scaled(
                        THUMB_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self._thumb.setPixmap(_placeholder_pixmap())


class ActiveModList(QWidget):
    """Title bar + scrollable list of active mods."""

    selection_changed = pyqtSignal(list)  # list[ActiveMod]
    mod_focus_requested = pyqtSignal(object)  # ActiveMod
    order_changed = pyqtSignal()  # the active list was reordered/edited
    mods_dropped = pyqtSignal(list, int)  # (mod path strings from the grid, target row)
    move_to_group_requested = pyqtSignal(object, str)  # (ActiveMod, group_id)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # display order: index 0 is the top of the list (highest priority).
        # profile order is the reverse (index 0 = bottom of the load order).
        self._mods: list[ActiveMod] = []
        self._icon_for: Callable[[ActiveMod], bytes | None] | None = None
        self._installed_names: set[str] = set()
        self._category_for: Callable[[ActiveMod], tuple[str, ...]] | None = None
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

        self._list = _ActiveListView()
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
    ) -> None:
        self._installed_names = installed_names or set()
        self._icon_for = icon_for
        self._category_for = category_for
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

    def move_to_top(self, mod: ActiveMod) -> None:
        self._mods = [m for m in self._mods if m.name != mod.name]
        self._mods.insert(0, mod)
        self._rerender()
        self._list.scrollToTop()
        self.order_changed.emit()

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
        insert_at = len(remaining)
        for i, other in enumerate(remaining):
            if group_index_for_token(self._primary_token(other)) > target_idx:
                insert_at = i
                break
        self._mods = remaining[:insert_at] + [mod] + remaining[insert_at:]
        self._rerender()
        self.order_changed.emit()

    def _on_reorder_requested(self, widget_rows: list[int], widget_target: int) -> None:
        """Translate QListWidget widget-row indices from a drag to mod-display indices."""
        resolved: list[int] = []
        for r in widget_rows:
            if r < self._list.count():
                data = self._list.item(r).data(Qt.ItemDataRole.UserRole)
                if data is not None:
                    resolved.append(self.widget_row_to_mod_index(r))
        self.move_rows(resolved, self.widget_row_to_mod_index(widget_target))

    def _on_external_drop(self, paths: list[str], widget_target: int) -> None:
        """Map raw widget-row drop target to mod-space index before forwarding."""
        self.mods_dropped.emit(paths, self.widget_row_to_mod_index(widget_target))

    def _on_context_menu(self, pos: object) -> None:
        from PyQt6.QtCore import QPoint

        if not isinstance(pos, QPoint):
            return
        item = self._list.itemAt(pos)
        if item is None:
            return
        mod = item.data(Qt.ItemDataRole.UserRole)
        if mod is None:
            return
        menu = QMenu()
        submenu = menu.addMenu(t("active_panel.move_to_group"))
        if submenu is None:
            return
        for g in GROUPS:
            action = submenu.addAction(t(g.label_keys[0]))
            if action is None:
                continue
            group_id = g.id

            def _make_handler(m: object, gid: str) -> Callable[[], None]:
                def handler() -> None:
                    self.move_to_group_requested.emit(m, gid)

                return handler

            action.triggered.connect(_make_handler(mod, group_id))
        viewport = self._list.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(pos))

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
                spacer_widget = _SpacerItem(row.group_id)
                item = QListWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.ItemDataRole.UserRole, None)
                item.setSizeHint(spacer_widget.sizeHint())
                self._list.addItem(item)
                self._list.setItemWidget(item, spacer_widget)
            else:
                mod = row.mod
                icon_bytes = self._icon_for(mod) if self._icon_for is not None else None
                if row.misplaced:
                    self._misplaced.add(mod.name)
                tip = (
                    t(
                        "load_order.misplaced_tooltip",
                        category=self._expected_label(row.expected_group_id),
                    )
                    if row.misplaced
                    else ""
                )
                widget = ActiveModItem(
                    mod,
                    icon_bytes,
                    is_missing=mod.name not in self._installed_names,
                    misplaced=row.misplaced,
                    tooltip=tip,
                )
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, mod)
                item.setSizeHint(widget.sizeHint())
                self._list.addItem(item)
                self._list.setItemWidget(item, widget)

        self._count.setText(t("active_panel.count", count=len(self._mods)))
        self._empty_hint.setVisible(len(self._mods) == 0)
        self._list.setVisible(len(self._mods) > 0)
        # keep the viewport where it was; move_to_top re-scrolls explicitly
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


def _format_label(mod: ActiveMod) -> str:
    return mod.display_name or mod.name


def _thumbnail_style() -> str:
    return (
        f"background-color: {Theme.BACKGROUND};"
        f"border: 1px solid {Theme.SURFACE_HOVER};"
        "border-radius: 3px;"
    )


def _placeholder_pixmap() -> QPixmap:
    pix = QPixmap(THUMB_SIZE)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(Theme.SURFACE_HOVER))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, THUMB_SIZE.width(), THUMB_SIZE.height(), 4, 4)
    painter.end()
    return pix
