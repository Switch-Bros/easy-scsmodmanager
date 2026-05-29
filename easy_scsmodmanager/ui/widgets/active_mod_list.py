"""Right-hand panel listing the profile's active mods in priority order.

Each row uses a custom widget: a large 200x112 thumbnail on top, the
display name below. Selection survives the custom widgets via the
underlying QListWidget item the widget is paired with.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.services.profile_reader import ActiveMod
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t

THUMB_SIZE = QSize(Theme.ACTIVE_THUMBNAIL_WIDTH, Theme.ACTIVE_THUMBNAIL_HEIGHT)

# carried by a drag coming from the mod grid: newline-joined mod path strings
MOD_DRAG_MIME = "application/x-escsmm-modpaths"


class _ActiveListView(QListWidget):
    """List view that turns drops into model-level reorder / insert signals.

    Internal drag (rows dragged within the list) -> reorder_requested.
    A drag from the grid carrying MOD_DRAG_MIME -> external_drop_requested.
    We never call super().dropEvent so Qt does not move the item widgets
    itself - the owner rebuilds the list from its model instead.
    """

    reorder_requested = pyqtSignal(list, int)  # (source rows, target row)
    external_drop_requested = pyqtSignal(list, int)  # (mod path strings, target row)

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
        event.accept() if self._accepts(event) else event.ignore()  # type: ignore[attr-defined]

    def dragMoveEvent(self, event: object) -> None:  # noqa: N802
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


class ActiveModItem(QWidget):
    """Single row in the active list: large thumbnail + name."""

    def __init__(
        self,
        mod: ActiveMod,
        icon_bytes: bytes | None,
        *,
        is_missing: bool,
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # display order: index 0 is the top of the list (highest priority).
        # profile order is the reverse (index 0 = bottom of the load order).
        self._mods: list[ActiveMod] = []
        self._icon_for: Callable[[ActiveMod], bytes | None] | None = None
        self._installed_names: set[str] = set()

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
        self._list.reorder_requested.connect(self.move_rows)
        self._list.external_drop_requested.connect(self.mods_dropped.emit)
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
    ) -> None:
        self._installed_names = installed_names or set()
        self._icon_for = icon_for
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
        at = max(0, min(at, len(self._mods)))
        self._mods = self._mods[:at] + list(mods) + self._mods[at:]
        self._rerender()
        self.order_changed.emit()

    def move_rows(self, rows: list[int], target: int) -> None:
        picked = sorted(set(rows))
        moving = [self._mods[r] for r in picked]
        remaining = [m for i, m in enumerate(self._mods) if i not in set(picked)]
        insert_at = target - sum(1 for r in picked if r < target)
        insert_at = max(0, min(insert_at, len(remaining)))
        self._mods = remaining[:insert_at] + moving + remaining[insert_at:]
        self._rerender()
        self.order_changed.emit()

    def _rerender(self) -> None:
        self._list.clear()
        for mod in self._mods:
            icon_bytes = self._icon_for(mod) if self._icon_for is not None else None
            widget = ActiveModItem(
                mod,
                icon_bytes,
                is_missing=mod.name not in self._installed_names,
            )
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, mod)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

        self._count.setText(t("active_panel.count", count=len(self._mods)))
        self._empty_hint.setVisible(len(self._mods) == 0)
        self._list.setVisible(len(self._mods) > 0)

    def selected_mods(self) -> list[ActiveMod]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
            if self._list.item(i).isSelected()
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
