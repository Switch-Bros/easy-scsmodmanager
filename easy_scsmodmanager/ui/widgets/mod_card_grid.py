"""Scrollable grid of :class:`ModCard` widgets.

Wraps cards into rows that fit the available width and emits selection
signals so the parent panel can drive multi-select. Pagination /
virtual-scrolling is intentionally out of scope for Phase 2 - a 300 mod
grid is fine without it; we can revisit when users hit 1000+.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PyQt6.QtCore import QMimeData, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QGridLayout, QScrollArea, QSizePolicy, QWidget

from easy_scsmodmanager.services.mod_matching import active_name_for
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.widgets.active_mod_list import MOD_DRAG_MIME
from easy_scsmodmanager.ui.widgets.mod_card import ModCard


class ModCardGrid(QScrollArea):
    """Read-only grid view of mod cards."""

    selection_changed = pyqtSignal(list)  # list[ScannedMod]
    card_activated = pyqtSignal(object)  # ScannedMod
    info_requested = pyqtSignal(object)  # ScannedMod

    def __init__(self, columns: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._cards: list[ModCard] = []
        self._selected: set[int] = set()  # indices into self._cards
        self._anchor: int | None = None  # last plain-clicked index, for shift-range

        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setStyleSheet(f"background-color: {Theme.BACKGROUND};")

        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {Theme.BACKGROUND};")
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(8)
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWidget(self._content)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def set_mods(
        self,
        mods: Iterable[ScannedMod],
        *,
        active_names: set[str] | None = None,
        icon_for: Callable[[ScannedMod], bytes | None] | None = None,
        name_for: Callable[[ScannedMod], str] | None = None,
        categories_for: Callable[[ScannedMod], tuple[str, ...]] | None = None,
    ) -> None:
        """Replace the displayed cards.

        ``active_names`` is the set of active_mods names from the profile -
        used to colour status. ``icon_for`` is an optional callable
        ``ScannedMod -> bytes | None`` to look up cached icons.
        ``categories_for`` overrides the category badge per mod (e.g. to use
        effective categories instead of the raw manifest categories).
        """
        self._clear()
        active_names = active_names or set()
        for i, mod in enumerate(mods):
            icon = icon_for(mod) if icon_for is not None else None
            card = ModCard(
                mod,
                is_active=active_name_for(mod) in active_names,
                icon_bytes=icon,
                display_name=name_for(mod) if name_for is not None else None,
                categories_for=categories_for,
            )
            idx = len(self._cards)
            card.clicked.connect(lambda mods, i=idx: self._on_card_clicked(i, mods))
            card.activated.connect(lambda i=idx: self._on_card_activated(i))
            card.info_requested.connect(lambda m=mod: self.info_requested.emit(m))
            card.drag_started.connect(lambda i=idx: self._start_drag(i))
            self._cards.append(card)
            self._grid.addWidget(card, i // self._columns, i % self._columns)
        # Push the cards top-left, do not let the grid stretch them.
        self._grid.setRowStretch(self._grid.rowCount(), 1)
        self._grid.setColumnStretch(self._columns, 1)

    def cards(self) -> list[ModCard]:
        return list(self._cards)

    def set_active_names(self, active_names: set[str]) -> None:
        """Recolour cards to reflect which mods are currently active."""
        for card in self._cards:
            card.set_active(active_name_for(card.mod) in active_names)

    def selected_mods(self) -> list[ScannedMod]:
        return [self._cards[i].mod for i in sorted(self._selected)]

    def clear_selection(self) -> None:
        for i in list(self._selected):
            self._cards[i].set_selected(False)
        self._selected.clear()
        self.selection_changed.emit([])

    def focus_mod(self, mod: ScannedMod) -> bool:
        """Select the card matching ``mod`` and scroll it into view.

        Returns True when a matching card was found.
        """
        for i, card in enumerate(self._cards):
            if card.mod.path == mod.path:
                self._on_card_clicked(i, Qt.KeyboardModifier.NoModifier)
                self.ensureWidgetVisible(card)
                return True
        return False

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _clear(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._cards.clear()
        self._selected.clear()
        self._anchor = None

    def _on_card_clicked(self, index: int, modifiers: Qt.KeyboardModifier) -> None:
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        if ctrl:
            self._toggle(index)
            self._anchor = index
        elif shift and self._anchor is not None:
            self._select_range(self._anchor, index)
        else:
            self._set_single(index)
            self._anchor = index
        self.selection_changed.emit(self.selected_mods())

    def _set_single(self, index: int) -> None:
        for i in list(self._selected):
            self._cards[i].set_selected(False)
        self._selected = {index}
        self._cards[index].set_selected(True)

    def _toggle(self, index: int) -> None:
        if index in self._selected:
            self._selected.discard(index)
            self._cards[index].set_selected(False)
        else:
            self._selected.add(index)
            self._cards[index].set_selected(True)

    def _select_range(self, start: int, end: int) -> None:
        lo, hi = sorted((start, end))
        for i in list(self._selected):
            self._cards[i].set_selected(False)
        self._selected = set(range(lo, hi + 1))
        for i in self._selected:
            self._cards[i].set_selected(True)

    def _on_card_activated(self, index: int) -> None:
        self.card_activated.emit(self._cards[index].mod)

    def _start_drag(self, index: int) -> None:
        # drag the whole selection; if the grabbed card is not selected,
        # make it the selection first
        if index not in self._selected:
            self._set_single(index)
            self.selection_changed.emit(self.selected_mods())
        paths = "\n".join(str(mod.path) for mod in self.selected_mods())
        mime = QMimeData()
        mime.setData(MOD_DRAG_MIME, paths.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)
