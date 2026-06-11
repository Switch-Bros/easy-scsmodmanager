"""Upload the active mod list and present the resulting share code."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.threads.share_thread import ShareUploadThread
from easy_scsmodmanager.utils.i18n import t

log = logging.getLogger(__name__)


class ShareCreateDialog(QDialog):
    """One-shot dialog: intro -> create -> code + copy (or inline error)."""

    def __init__(
        self,
        *,
        game: str,
        profile_name: str,
        payload: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._game = game
        self._profile_name = profile_name
        self._payload = payload
        self._thread: ShareUploadThread | None = None

        self.setWindowTitle(t("mod_share.create.title"))
        self.setMinimumWidth(460)
        self.setStyleSheet(f"background-color: {Theme.BACKGROUND}; color: {Theme.TEXT};")

        root = QVBoxLayout(self)
        root.setSpacing(8)

        intro = QLabel(
            t(
                "mod_share.create.intro",
                profile=profile_name,
                count=len(payload.get("mods", [])),
            )
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self._create_button = QPushButton(t("mod_share.create.button"))
        self._create_button.clicked.connect(self._start_upload)
        root.addWidget(self._create_button)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status_label)

        code_row = QHBoxLayout()
        self._code_label = QLabel("")
        font = self._code_label.font()
        font.setPointSize(font.pointSize() * 2)
        font.setBold(True)
        self._code_label.setFont(font)
        self._code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        code_row.addWidget(self._code_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self._copy_button = QPushButton(t("mod_share.create.copy"))
        self._copy_button.clicked.connect(self._copy_code)
        self._copy_button.hide()
        code_row.addWidget(self._copy_button)
        root.addLayout(code_row)

        self._ttl_label = QLabel(t("mod_share.create.ttl_hint"))
        self._ttl_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ttl_label.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
        self._ttl_label.hide()
        root.addWidget(self._ttl_label)

        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet(f"color: {Theme.DANGER};")
        root.addWidget(self._error_label)

    # ------------------------------------------------------------------ #
    # upload flow
    # ------------------------------------------------------------------ #

    def _start_upload(self) -> None:
        self._create_button.setEnabled(False)
        self._error_label.setText("")
        self._status_label.setText(t("mod_share.create.uploading"))
        self._thread = ShareUploadThread(self._game, self._profile_name, self._payload)
        self._thread.succeeded.connect(self._on_code)
        self._thread.failed.connect(self._on_error)
        self._thread.start()

    def _on_code(self, code: str) -> None:
        self._status_label.setText(t("mod_share.create.done"))
        self._code_label.setText(code)
        self._copy_button.show()
        self._ttl_label.show()

    def _on_error(self, kind: str) -> None:
        self._status_label.setText("")
        self._error_label.setText(t(f"mod_share.error.{kind}"))
        self._create_button.setEnabled(True)

    def _copy_code(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._code_label.text())
            self._copy_button.setText(t("mod_share.create.copied"))

    def shutdown(self, msecs: int) -> None:
        """Wait for a running upload so app close cannot destroy a live thread."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait(msecs)

    def closeEvent(self, event) -> None:  # noqa: N802
        # a slow upload may outlive the dialog: detach the slots so the
        # thread cannot emit into a destroyed widget
        if self._thread is not None and self._thread.isRunning():
            self._thread.succeeded.disconnect(self._on_code)
            self._thread.failed.disconnect(self._on_error)
        super().closeEvent(event)
