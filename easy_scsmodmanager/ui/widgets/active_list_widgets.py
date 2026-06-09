"""The building-block widgets the active list is made of.

Pulled out of active_mod_list.py so that file keeps to the list logic:

- ``ActiveListView`` - the QListWidget subclass that turns drops into
  reorder/insert signals and animates wheel scrolling.
- ``SpacerItem`` - a load-order group header row.
- ``ActiveModItem`` - a single mod row (thumbnail + name).

None of these depend on ActiveModList, so they live here as standalone widgets.
"""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.core.load_order import group_label_keys
from easy_scsmodmanager.services.conflict_detect import Severity
from easy_scsmodmanager.services.profile_reader import ActiveMod
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t

# Severity glyphs: shape differs (triangle vs. crossed circle) so the two levels
# stay distinct in greyscale / for colour-blind users, not colour alone.
# U+2298 renders in Inter on Win+Linux; documented fallback is U+2715 ("X").
_GLYPH_PARTIAL = "⚠"  # warning triangle
_GLYPH_FULL = "⊘"  # circled division slash (crossed circle)
_GLYPH_FREQUENT = "="  # neutral "frequently shared" (not a conflict); fallback "•"

THUMB_SIZE = QSize(Theme.ACTIVE_THUMBNAIL_WIDTH, Theme.ACTIVE_THUMBNAIL_HEIGHT)

# carried by a drag coming from the mod grid: newline-joined mod path strings
MOD_DRAG_MIME = "application/x-escsmm-modpaths"

# gentle animated wheel scrolling for the tall active rows
WHEEL_STEP_PX = 80
WHEEL_DURATION_MS = 200

# every group header is as tall as the 3-line map_base block (+10px top/bottom)
_SPACER_HEIGHT = 80

# spacer font size: the multi-line map_base header stays compact so its three
# lines fit; single-line group headers get a large, easily readable size.
_SPACER_FONT_PX_MULTILINE = 14
_SPACER_FONT_PX_SINGLE = 30

# fixed height for the name label (room for two 11px lines) so every card is
# the same height regardless of whether the name wraps to one line or two
_NAME_HEIGHT = 34


class ActiveListView(QListWidget):
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


class SpacerItem(QWidget):
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
        keys = group_label_keys(group_id)
        font_px = _SPACER_FONT_PX_MULTILINE if len(keys) > 1 else _SPACER_FONT_PX_SINGLE
        for key in keys:
            lbl = QLabel(t(key))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {Theme.ACCENT};"
                f"font-size: {font_px}px;"
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
        severity: Severity | None = None,
        frequent: bool = False,
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

        # an override gets a severity glyph prefixed on the name (no extra row,
        # so card height stays uniform); only the glyph is coloured, the name
        # keeps its colour. Details live in the tooltip.
        self._name = QLabel(_severity_label(mod, severity, frequent))
        self._name.setStyleSheet(f"color: {Theme.TEXT}; font-size: 11px; font-weight: 600;")
        self._name.setWordWrap(True)
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # fixed two-line height keeps every card the same size; a one-line name
        # is vertically centred, a long name fills both lines.
        self._name.setFixedHeight(_NAME_HEIGHT)
        self._name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
                f"#misplaced_mod_item {{ border-left: 3px solid {Theme.MISPLACED}; }}"
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


def _format_label(mod: ActiveMod) -> str:
    return mod.display_name or mod.name


def conflict_legend_html() -> str:
    """One-line legend: the three glyphs in their colours + meaning."""
    return (
        f'<span style="color:{Theme.WARNING}">{_GLYPH_PARTIAL}</span> '
        f'{t("conflict.legend.partial")}'
        f'&nbsp;&nbsp;&nbsp;<span style="color:{Theme.DANGER}">{_GLYPH_FULL}</span> '
        f'{t("conflict.legend.full")}'
        f'&nbsp;&nbsp;&nbsp;<span style="color:{Theme.TEXT_DIM}">{_GLYPH_FREQUENT}</span> '
        f'{t("conflict.legend.frequent")}'
    )


def _severity_label(mod: ActiveMod, severity: Severity | None, frequent: bool = False) -> str:
    name = _format_label(mod)
    # one glyph per card, precedence FULL > PARTIAL > FREQUENT > none
    if severity is Severity.FULL:
        glyph, colour = _GLYPH_FULL, Theme.DANGER
    elif severity is Severity.PARTIAL:
        glyph, colour = _GLYPH_PARTIAL, Theme.WARNING
    elif frequent:
        glyph, colour = _GLYPH_FREQUENT, Theme.TEXT_DIM  # neutral grey, not an alarm
    else:
        return name
    # rich text so only the glyph carries the colour; the name keeps the label's
    # own colour. Escape the name since the label is now HTML.
    safe = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<span style="color:{colour}">{glyph}</span> {safe}'


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
