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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

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

        self._list = QListWidget()
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
        self._list.itemActivated.connect(self._on_item_clicked)
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
        installed_names = installed_names or set()
        self._list.clear()
        ordered = list(reversed(list(mods)))
        for mod in ordered:
            icon_bytes = icon_for(mod) if icon_for is not None else None
            widget = ActiveModItem(
                mod,
                icon_bytes,
                is_missing=mod.name not in installed_names,
            )
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, mod)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

        self._count.setText(t("active_panel.count", count=len(ordered)))
        self._empty_hint.setVisible(len(ordered) == 0)
        self._list.setVisible(len(ordered) > 0)

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
