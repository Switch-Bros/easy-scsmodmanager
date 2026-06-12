"""Top-of-browser toolbar with search, sort and category filters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from easy_scsmodmanager.core.mod_categories import OFFICIAL_CATEGORIES, i18n_key
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t

SEARCH_DEBOUNCE_MS = 200


class SortKey(Enum):
    DATE = "date"
    NAME = "name"
    AUTHOR = "author"
    STATUS = "status"


class ModSource(Enum):
    ALL = "all"
    WORKSHOP = "workshop"
    LOCAL = "local"


@dataclass(frozen=True)
class FilterState:
    search: str = ""
    source: ModSource = ModSource.ALL
    favorites_only: bool = False
    sort_key: SortKey = SortKey.NAME
    sort_descending: bool = False
    category: str | None = None  # None = all categories


class FilterToolbar(QWidget):
    filter_changed = pyqtSignal(object)  # FilterState

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = FilterState()
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(SEARCH_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._emit_filter)

        # only the two anonymous labels ("Sort:", "Category:") still need a
        # local rule; inputs/combos/checkboxes fall to the global dark QSS
        self.setStyleSheet(f"QLabel {{ color: {Theme.TEXT_DIM}; }}")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(t("filter.search.placeholder"))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        row.addWidget(self._search, 2)

        row.addWidget(QLabel(t("filter.source")))
        self._source = QComboBox()
        self._source.addItem(t("filter.source.all"), ModSource.ALL)
        self._source.addItem(t("filter.source.workshop"), ModSource.WORKSHOP)
        self._source.addItem(t("filter.source.local"), ModSource.LOCAL)
        self._source.currentIndexChanged.connect(self._on_source_changed)
        row.addWidget(self._source)

        self._favorites = QCheckBox(t("filter.favorites_only"))
        self._favorites.toggled.connect(self._on_favorites_toggled)
        row.addWidget(self._favorites)

        row.addWidget(QLabel(t("filter.sort.label")))
        self._sort = QComboBox()
        for key in SortKey:
            # "Author" collapses onto the shared common.author label; the other
            # sort keys keep their dedicated filter.sort.* strings.
            label_key = "common.author" if key is SortKey.AUTHOR else f"filter.sort.{key.value}"
            self._sort.addItem(t(label_key), key)
        self._sort.currentIndexChanged.connect(self._on_sort_changed)
        row.addWidget(self._sort)

        self._sort_dir = QComboBox()
        self._sort_dir.addItem(t("filter.sort.asc"), False)
        self._sort_dir.addItem(t("filter.sort.desc"), True)
        self._sort_dir.currentIndexChanged.connect(self._on_sort_dir_changed)
        row.addWidget(self._sort_dir)

        row.addWidget(QLabel(t("common.category")))
        self._category = QComboBox()
        # Fixed, game-ordered list - never derived from the mods themselves.
        self._category.addItem(t("filter.category.all"), None)
        for token in OFFICIAL_CATEGORIES:
            self._category.addItem(t(i18n_key(token)), token)
        self._category.currentIndexChanged.connect(self._on_category_changed)
        row.addWidget(self._category, 1)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> FilterState:
        return self._state

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _on_search_changed(self, text: str) -> None:
        self._state = self._replace(search=text)
        self._debounce.start()

    def _on_source_changed(self, _index: int) -> None:
        src = self._source.currentData()
        if src is not None:
            self._state = self._replace(source=src)
            self._emit_filter()

    def _on_favorites_toggled(self, checked: bool) -> None:
        self._state = self._replace(favorites_only=checked)
        self._emit_filter()

    def _on_sort_changed(self, _index: int) -> None:
        key = self._sort.currentData()
        if key is not None:
            self._state = self._replace(sort_key=key)
            self._emit_filter()

    def _on_sort_dir_changed(self, _index: int) -> None:
        desc = bool(self._sort_dir.currentData())
        self._state = self._replace(sort_descending=desc)
        self._emit_filter()

    def _on_category_changed(self, _index: int) -> None:
        cat = self._category.currentData()
        self._state = self._replace(category=cat)
        self._emit_filter()

    def _replace(self, **changes: Any) -> FilterState:
        return replace(self._state, **changes)

    def _emit_filter(self) -> None:
        self.filter_changed.emit(self._state)
