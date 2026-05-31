"""Settings dialog: UI language and manual game-path overrides.

Writes through a :class:`SettingsStore`. The language change only takes effect
on the next start (``t()`` resolves at widget construction), so the dialog says
so rather than pretending to switch live. An empty path means "auto-detect".

Two kinds of path override: the *documents* dir (mod/ + profiles/) and the
*install* dir (holds base.scs/def.scs, used by the SCS extractor).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.core.map_base_mods import DEFAULT_MAP_BASE_NAMES
from easy_scsmodmanager.core.settings_store import SettingsStore
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import available_languages, current_language, t

DOCUMENTS = "documents"
INSTALL = "install"

# (game, kind, label key)
_PATH_FIELDS = (
    (Game.ETS2, DOCUMENTS, "settings.paths.ets2_documents"),
    (Game.ATS, DOCUMENTS, "settings.paths.ats_documents"),
    (Game.ETS2, INSTALL, "settings.paths.ets2_install"),
    (Game.ATS, INSTALL, "settings.paths.ats_install"),
)


class SettingsDialog(QDialog):
    def __init__(self, store: SettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._paths: dict[tuple[Game, str], Path | None] = {
            (game, kind): self._load(game, kind) for game, kind, _ in _PATH_FIELDS
        }
        self._edits: dict[tuple[Game, str], QLineEdit] = {}

        self.setWindowTitle(t("dialog.settings.title"))
        self.setMinimumWidth(580)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BACKGROUND}; }}
            QLabel {{ color: {Theme.TEXT}; }}
            QLineEdit, QComboBox {{
                background-color: {Theme.SURFACE}; color: {Theme.TEXT};
                border: 1px solid {Theme.SURFACE_HOVER}; border-radius: 3px;
                padding: 4px 6px;
            }}
            QPushButton {{
                background-color: {Theme.SURFACE}; color: {Theme.TEXT};
                border: 1px solid {Theme.SURFACE_HOVER}; border-radius: 3px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ background-color: {Theme.SURFACE_HOVER}; }}
        """)
        self._build()

    def _load(self, game: Game, kind: str) -> Path | None:
        if kind == DOCUMENTS:
            return self._store.get_documents_override(game)
        return self._store.get_install_override(game)

    def _save(self, game: Game, kind: str, path: Path | None) -> None:
        if kind == DOCUMENTS:
            self._store.set_documents_override(game, path)
        else:
            self._store.set_install_override(game, path)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        form = QFormLayout()
        self._lang_combo = QComboBox()
        for code, name in available_languages().items():
            self._lang_combo.addItem(name, code)
        idx = self._lang_combo.findData(self._store.get_language() or current_language())
        self._lang_combo.setCurrentIndex(max(idx, 0))
        form.addRow(t("settings.language.label"), self._lang_combo)
        root.addLayout(form)

        hint = QLabel(t("settings.language.restart_hint"))
        hint.setStyleSheet(f"color: {Theme.TEXT_DIM};")
        root.addWidget(hint)

        root.addWidget(self._heading("settings.paths.heading"))
        self._add_rows(root, DOCUMENTS)
        root.addWidget(self._heading("settings.paths.install_heading"))
        self._add_rows(root, INSTALL)

        self._build_map_base_section(root)

        buttons = QDialogButtonBox()
        buttons.addButton(t("dialog.settings.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(t("dialog.settings.cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _heading(self, key: str) -> QLabel:
        label = QLabel(t(key))
        label.setStyleSheet(f"color: {Theme.TEXT_DIM}; margin-top: 6px;")
        return label

    def _add_rows(self, root: QVBoxLayout, kind: str) -> None:
        for game, field_kind, label_key in _PATH_FIELDS:
            if field_kind == kind:
                root.addLayout(self._build_path_row(game, kind, label_key))

    def _build_path_row(self, game: Game, kind: str, label_key: str) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(t(label_key))
        label.setMinimumWidth(180)

        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setPlaceholderText(t("settings.paths.auto"))
        path = self._paths[(game, kind)]
        if path is not None:
            edit.setText(str(path))
        self._edits[(game, kind)] = edit

        browse = QPushButton(t("settings.paths.browse"))
        browse.clicked.connect(lambda: self._on_browse(game, kind))
        reset = QPushButton(t("settings.paths.reset"))
        reset.clicked.connect(lambda: self._on_reset(game, kind))

        row.addWidget(label)
        row.addWidget(edit, 1)
        row.addWidget(browse)
        row.addWidget(reset)
        return row

    def _on_browse(self, game: Game, kind: str) -> None:
        chosen = QFileDialog.getExistingDirectory(self, t("settings.browse_caption"))
        if chosen:
            self._paths[(game, kind)] = Path(chosen)
            self._edits[(game, kind)].setText(chosen)

    def _on_reset(self, game: Game, kind: str) -> None:
        self._paths[(game, kind)] = None
        self._edits[(game, kind)].setText("")

    def _build_map_base_section(self, root: QVBoxLayout) -> None:
        root.addWidget(self._heading("settings.map_base.heading"))
        hint = QLabel(t("settings.map_base.hint"))
        hint.setStyleSheet(f"color: {Theme.TEXT_DIM};")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._map_base_list = QListWidget()
        self._map_base_list.setMaximumHeight(140)
        for name in self._store.get_map_base_names():
            self._map_base_list.addItem(name)
        root.addWidget(self._map_base_list)

        buttons = QHBoxLayout()
        add = QPushButton(t("settings.map_base.add"))
        add.clicked.connect(self._on_map_base_add)
        remove = QPushButton(t("settings.map_base.remove"))
        remove.clicked.connect(self._on_map_base_remove)
        reset = QPushButton(t("settings.map_base.reset"))
        reset.clicked.connect(self._on_map_base_reset)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        buttons.addWidget(reset)
        root.addLayout(buttons)

    def _on_map_base_add(self) -> None:
        text, ok = QInputDialog.getText(
            self, t("settings.map_base.add_title"), t("settings.map_base.add_label")
        )
        if ok and text.strip():
            self._map_base_list.addItem(text.strip())

    def _on_map_base_remove(self) -> None:
        for item in self._map_base_list.selectedItems():
            self._map_base_list.takeItem(self._map_base_list.row(item))

    def _on_map_base_reset(self) -> None:
        self._map_base_list.clear()
        for name in DEFAULT_MAP_BASE_NAMES:
            self._map_base_list.addItem(name)

    def _map_base_names(self) -> list[str]:
        return [self._map_base_list.item(i).text() for i in range(self._map_base_list.count())]

    def selected_language(self) -> str:
        return str(self._lang_combo.currentData())

    def accept(self) -> None:
        self._store.set_language(self._lang_combo.currentData())
        for game, kind, _ in _PATH_FIELDS:
            self._save(game, kind, self._paths[(game, kind)])
        self._store.set_map_base_names(self._map_base_names())
        super().accept()
