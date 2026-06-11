"""One import dialog for all three share sources (code / file / profile.sii).

Pure view: no network and no file IO in here. The dialog emits request
signals and the ModShareController feeds results back via show_share /
show_error. Modeless on purpose - "check again" can trigger a rescan in
the main window while the dialog stays open.
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.core.game_paths import GAME_DIRECTORY_NAME
from easy_scsmodmanager.services.mod_share import (
    CODE_LENGTH,
    ShareDiff,
    ShareList,
    normalize_code,
)
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.widgets.share_preview_widget import SharePreviewWidget
from easy_scsmodmanager.utils.i18n import t

_DEBOUNCE_MS = 350

_SOURCES = ("code", "file", "profile")


class ShareImportDialog(QDialog):
    code_lookup_requested = pyqtSignal(str)
    file_requested = pyqtSignal()
    profile_requested = pyqtSignal()
    recheck_requested = pyqtSignal()
    apply_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._share: ShareList | None = None
        self._game_matches = False
        self._target_profile = ""

        self.setWindowTitle(t("mod_share.import.title"))
        self.setMinimumWidth(460)
        self.setStyleSheet(f"background-color: {Theme.BACKGROUND}; color: {Theme.TEXT};")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- source toggle -------------------------------------------- #
        toggle_row = QHBoxLayout()
        self._source_group = QButtonGroup(self)
        self._source_buttons: dict[str, QPushButton] = {}
        for source in _SOURCES:
            button = QPushButton(t(f"mod_share.import.source_{source}"))
            button.setCheckable(True)
            self._source_group.addButton(button)
            self._source_buttons[source] = button
            toggle_row.addWidget(button)
            button.clicked.connect(lambda _checked=False, s=source: self._on_source(s))
        layout.addLayout(toggle_row)

        # --- code source ---------------------------------------------- #
        self._code_prompt = QLabel(t("mod_share.import.code_prompt"))
        layout.addWidget(self._code_prompt)
        self._code_edit = QLineEdit()
        self._code_edit.textChanged.connect(self._on_code_text)
        layout.addWidget(self._code_edit)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._fire_lookup)

        # --- file / profile sources ------------------------------------ #
        self._pick_file_button = QPushButton(t("mod_share.import.pick_file"))
        self._pick_file_button.clicked.connect(self.file_requested.emit)
        layout.addWidget(self._pick_file_button)
        self._pick_profile_button = QPushButton(t("mod_share.import.pick_profile"))
        self._pick_profile_button.clicked.connect(self.profile_requested.emit)
        layout.addWidget(self._pick_profile_button)

        # --- shared preview area -------------------------------------- #
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        self._header_label = QLabel("")
        layout.addWidget(self._header_label)
        self._preview = SharePreviewWidget()
        layout.addWidget(self._preview)

        self._recheck_button = QPushButton(t("mod_share.import.recheck"))
        self._recheck_button.clicked.connect(self.recheck_requested.emit)
        self._recheck_button.hide()
        layout.addWidget(self._recheck_button)

        self._include_missing = QCheckBox(t("mod_share.import.include_missing"))
        self._include_missing.setChecked(True)
        layout.addWidget(self._include_missing)

        self._apply_button = QPushButton("")
        self._apply_button.setEnabled(False)
        self._apply_button.clicked.connect(self.apply_requested.emit)
        layout.addWidget(self._apply_button)

        self.set_source("code")

    # ------------------------------------------------------------------ #
    # controller-facing api
    # ------------------------------------------------------------------ #

    def set_source(self, source: str) -> None:
        self._source_buttons[source].setChecked(True)
        self._on_source(source)

    def reset(self) -> None:
        """Start clean: a reopened dialog must not show a previous preview."""
        self._code_edit.clear()
        self._status_label.setStyleSheet("")
        self._status_label.setText("")
        self._clear_result()

    def set_target_profile(self, name: str) -> None:
        self._target_profile = name
        self._update_apply()

    def show_lookup_busy(self) -> None:
        self._clear_result()
        self._status_label.setStyleSheet("")
        self._status_label.setText(t("mod_share.import.looking_up"))

    def show_share(self, share: ShareList, diff: ShareDiff, *, game_matches: bool) -> None:
        self._share = share
        self._game_matches = game_matches
        self._status_label.setStyleSheet("")
        self._status_label.setText(
            ""
            if game_matches
            else t("mod_share.import.game_mismatch", game=GAME_DIRECTORY_NAME[share.game])
        )
        self._header_label.setText(
            t(
                "mod_share.import.preview_header",
                profile=share.profile_name,
                game=GAME_DIRECTORY_NAME[share.game],
                count=len(share.entries),
            )
        )
        self._preview.set_diff(diff)
        self._recheck_button.setVisible(bool(diff.missing_names()))
        self._update_apply()

    def show_error(self, message: str) -> None:
        self._clear_result()
        self._status_label.setStyleSheet(f"color: {Theme.DANGER};")
        self._status_label.setText(message)

    def current_share(self) -> ShareList | None:
        return self._share

    def include_missing(self) -> bool:
        return self._include_missing.isChecked()

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _clear_result(self) -> None:
        self._share = None
        self._game_matches = False
        self._header_label.setText("")
        self._preview.set_diff(
            ShareDiff(found=(), missing_workshop=(), missing_local=(), outdated=())
        )
        self._recheck_button.hide()
        self._update_apply()

    def _on_source(self, source: str) -> None:
        if source != "code":
            self._debounce.stop()
        is_code = source == "code"
        self._code_prompt.setVisible(is_code)
        self._code_edit.setVisible(is_code)
        self._pick_file_button.setVisible(source == "file")
        self._pick_profile_button.setVisible(source == "profile")

    def _on_code_text(self, raw: str) -> None:
        code = normalize_code(raw)
        if code != raw:
            self._code_edit.setText(code)  # re-enters once with the clean text
            return
        self._debounce.stop()
        if len(code) == CODE_LENGTH:
            self._debounce.start()

    def _fire_lookup(self) -> None:
        self.code_lookup_requested.emit(self._code_edit.text())

    def _update_apply(self) -> None:
        ready = self._share is not None and self._game_matches
        self._apply_button.setEnabled(ready)
        self._apply_button.setText(t("mod_share.import.apply", profile=self._target_profile))
