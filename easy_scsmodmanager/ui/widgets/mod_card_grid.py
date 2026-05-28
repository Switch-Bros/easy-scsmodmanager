"""Scrollable grid of :class:`ModCard` widgets.

Wraps cards into rows that fit the available width and emits selection
signals so the parent panel can drive multi-select. Pagination /
virtual-scrolling is intentionally out of scope for Phase 2 - a 300 mod
grid is fine without it; we can revisit when users hit 1000+.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QScrollArea, QSizePolicy, QWidget

from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.widgets.mod_card import ModCard


class ModCardGrid(QScrollArea):
    """Read-only grid view of mod cards."""

    selection_changed = pyqtSignal(list)  # list[ScannedMod]
    card_activated = pyqtSignal(object)  # ScannedMod

    def __init__(self, columns: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._cards: list[ModCard] = []
        self._selected: set[int] = set()  # indices into self._cards

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
    ) -> None:
        """Replace the displayed cards.

        ``active_names`` is the set of mod stem names from the active
        profile - used to colour status. ``icon_for`` is an optional
        callable ``ScannedMod -> bytes | None`` to look up cached icons.
        """
        self._clear()
        active_names = active_names or set()
        for i, mod in enumerate(mods):
            icon = icon_for(mod) if icon_for is not None else None
            card = ModCard(
                mod,
                is_active=mod.path.stem in active_names,
                icon_bytes=icon,
            )
            idx = len(self._cards)
            card.clicked.connect(lambda i=idx: self._on_card_clicked(i))
            card.activated.connect(lambda i=idx: self._on_card_activated(i))
            self._cards.append(card)
            self._grid.addWidget(card, i // self._columns, i % self._columns)
        # Push the cards top-left, do not let the grid stretch them.
        self._grid.setRowStretch(self._grid.rowCount(), 1)
        self._grid.setColumnStretch(self._columns, 1)

    def cards(self) -> list[ModCard]:
        return list(self._cards)

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
                self._on_card_clicked(i)
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

    def _on_card_clicked(self, index: int) -> None:
        # Phase 2: single-click toggles a single-selection. Multi-select
        # with Ctrl/Shift comes in Phase 3 together with drag-and-drop.
        for i in list(self._selected):
            if i != index:
                self._cards[i].set_selected(False)
        self._selected.clear()
        self._cards[index].set_selected(True)
        self._selected.add(index)
        self.selection_changed.emit(self.selected_mods())

    def _on_card_activated(self, index: int) -> None:
        self.card_activated.emit(self._cards[index].mod)
