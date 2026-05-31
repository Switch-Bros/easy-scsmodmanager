"""A single mod entry rendered as a card.

Layout::

    +------------------------------------------+
    |  [*]  [i]                       CATEGORY |   header row
    +------------------------------------------+
    |                                          |
    |              [ ICON 160x90 ]             |   thumbnail
    |                                          |
    +------------------------------------------+
    |  [G] Mod Name (yellow)                   |   name row
    |      Status text             Author      |   meta row
    +------------------------------------------+

The card is read-only in Phase 2 - no drag/drop yet. Selection and
hover states are visual only; the parent panel decides what they mean.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.core.mod_categories import canonical_categories, i18n_key
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t


class ModCard(QFrame):
    """Visual representation of one :class:`ScannedMod`.

    Emits ``clicked`` on single-click and ``activated`` on double-click
    so the parent panel can decide what to do (select, activate, ...).
    """

    clicked = pyqtSignal(object)  # Qt.KeyboardModifiers active at click time
    activated = pyqtSignal()
    favorite_toggled = pyqtSignal(bool)
    info_requested = pyqtSignal()
    drag_started = pyqtSignal()  # left-drag moved past the threshold

    def __init__(
        self,
        mod: ScannedMod,
        *,
        is_active: bool = False,
        icon_bytes: bytes | None = None,
        is_favorite: bool = False,
        display_name: str | None = None,
        categories_for: Callable[[ScannedMod], tuple[str, ...]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mod = mod
        self._is_active = is_active
        self._is_favorite = is_favorite
        self._is_selected = False
        self._display_name_override = display_name
        self._categories_for = categories_for
        self._press_pos: object | None = None

        self.setObjectName("ModCard")
        self.setFixedSize(QSize(Theme.MOD_CARD_WIDTH, Theme.MOD_CARD_HEIGHT))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._build_layout(icon_bytes)
        self._apply_style()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    @property
    def mod(self) -> ScannedMod:
        return self._mod

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_selected(self) -> bool:
        return self._is_selected

    def set_selected(self, selected: bool) -> None:
        if self._is_selected == selected:
            return
        self._is_selected = selected
        self._apply_style()

    def set_active(self, active: bool) -> None:
        if self._is_active == active:
            return
        self._is_active = active
        self._status_indicator.setStyleSheet(_status_box_style(self._status_kind()))
        self._status_text.setText(self._status_label())
        self._apply_style()

    # ------------------------------------------------------------------ #
    # mouse events
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self.clicked.emit(event.modifiers())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if (
            event is not None
            and self._press_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            moved = (event.position().toPoint() - self._press_pos).manhattanLength()
            if moved >= QApplication.startDragDistance():
                self._press_pos = None
                self.drag_started.emit()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------ #
    # building
    # ------------------------------------------------------------------ #

    def _build_layout(self, icon_bytes: bytes | None) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Theme.CARD_PADDING, Theme.CARD_PADDING, Theme.CARD_PADDING, Theme.CARD_PADDING
        )
        root.setSpacing(4)

        root.addLayout(self._build_header_row())
        root.addWidget(self._build_icon(icon_bytes), 0, Qt.AlignmentFlag.AlignCenter)
        root.addLayout(self._build_footer_rows())

    def _build_header_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._fav_btn = _make_tool_button(
            "*" if self._is_favorite else "☆",
            t("mod_card.favorite_tooltip"),
            on_click=self._on_favorite_clicked,
        )
        self._info_btn = _make_tool_button(
            "i",
            t("mod_card.info_tooltip"),
            on_click=self.info_requested.emit,
        )

        self._category = QLabel(self._category_label().upper())
        self._category.setObjectName("CardCategory")
        self._category.setStyleSheet(
            f"color: {Theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.5px;"
        )
        self._category.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(self._fav_btn)
        row.addWidget(self._info_btn)
        row.addStretch(1)
        row.addWidget(self._category)
        return row

    def _build_icon(self, icon_bytes: bytes | None) -> QLabel:
        label = QLabel()
        label.setFixedSize(QSize(Theme.ICON_WIDTH, Theme.ICON_HEIGHT))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"background-color: {Theme.BACKGROUND}; border-radius: 2px;")

        pixmap = QPixmap()
        if icon_bytes is not None and pixmap.loadFromData(icon_bytes):
            label.setPixmap(
                pixmap.scaled(
                    Theme.ICON_WIDTH,
                    Theme.ICON_HEIGHT,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            label.setText("no icon")
            label.setStyleSheet(
                f"background-color: {Theme.BACKGROUND}; "
                f"color: {Theme.TEXT_DIM}; border-radius: 2px;"
            )
        return label

    def _build_footer_rows(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        # Name row: small status indicator box + mod name
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(6)

        self._status_indicator = QLabel()
        self._status_indicator.setFixedSize(QSize(12, 12))
        self._status_indicator.setStyleSheet(_status_box_style(self._status_kind()))

        self._name_label = QLabel(self._display_name())
        self._name_label.setObjectName("CardName")
        self._name_label.setStyleSheet(
            f"color: {Theme.TEXT_MOD_NAME}; font-weight: bold; font-size: 12px;"
        )
        self._name_label.setWordWrap(False)
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        name_row.addWidget(self._status_indicator)
        name_row.addWidget(self._name_label, 1)

        # Meta row: status text on left, author on right
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)

        self._status_text = QLabel(self._status_label())
        self._status_text.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 10px;")

        self._author_label = QLabel(self._author())
        self._author_label.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 10px;")
        self._author_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        meta_row.addWidget(self._status_text)
        meta_row.addStretch(1)
        meta_row.addWidget(self._author_label)

        col.addLayout(name_row)
        col.addLayout(meta_row)
        return col

    # ------------------------------------------------------------------ #
    # state / helpers
    # ------------------------------------------------------------------ #

    def _status_kind(self) -> str:
        if self._mod.error is not None and self._mod.manifest is None:
            return "error"
        if self._is_active:
            return "active"
        return "inactive"

    def _status_label(self) -> str:
        kind = self._status_kind()
        if kind == "error":
            err = (self._mod.error or "").lower()
            if "encrypted" in err or "password" in err:
                return t("status.encrypted")
            if "hashfs" in err and "not implemented" in err:
                return t("status.hashfs_no_reader")
            return t("status.error")
        return {
            "active": t("status.active"),
            "inactive": t("status.inactive"),
        }.get(kind, t("status.inactive"))

    def _display_name(self) -> str:
        if self._display_name_override:
            return self._display_name_override
        if self._mod.manifest is not None and self._mod.manifest.display_name:
            return self._mod.manifest.display_name
        return self._mod.path.stem

    def _author(self) -> str:
        if self._mod.manifest is not None and self._mod.manifest.author:
            return self._mod.manifest.author
        return t("mod_card.no_author")

    def _category_label(self) -> str:
        if self._categories_for is not None:
            tokens = self._categories_for(self._mod)
        else:
            raw = self._mod.manifest.categories if self._mod.manifest else []
            tokens = canonical_categories(raw)
        return " / ".join(t(i18n_key(c)) for c in tokens)

    def _on_favorite_clicked(self) -> None:
        self._is_favorite = not self._is_favorite
        self._fav_btn.setText("*" if self._is_favorite else "☆")
        self.favorite_toggled.emit(self._is_favorite)

    def _apply_style(self) -> None:
        border_color = Theme.PRIMARY if self._is_selected else Theme.SURFACE
        background = Theme.SURFACE_SELECTED if self._is_selected else Theme.SURFACE
        self.setStyleSheet(f"""
            #ModCard {{
                background-color: {background};
                border: {Theme.BORDER_WIDTH}px solid {border_color};
                border-radius: {Theme.CARD_RADIUS}px;
            }}
            #ModCard:hover {{
                background-color: {Theme.SURFACE_HOVER};
            }}
            QToolButton {{
                background-color: transparent;
                color: {Theme.TEXT};
                border: 0;
                font-weight: bold;
                padding: 0;
            }}
            QToolButton:hover {{
                color: {Theme.ACCENT};
            }}
            """)


def _make_tool_button(text: str, tooltip: str, on_click: Callable[[], None]) -> QToolButton:
    btn = QToolButton()
    btn.setText(text)
    btn.setToolTip(tooltip)
    btn.setFixedSize(QSize(20, 20))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(on_click)
    return btn


def _status_box_style(kind: str) -> str:
    color = Theme.status_color(kind)
    return f"background-color: {color}; border-radius: 2px;"
