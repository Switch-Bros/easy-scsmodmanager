"""Shows an available update and drives download/install (or just points to it).

Self-updatable installs (AppImage, frozen Windows exe) get a Download &
Install button that flips to Restart once the verified download lands.
Package installs (deb/rpm/AUR/tar.gz) get a check-only dialog: release notes
plus an Open-Releases button and a short hint on how to update properly.
"""

from __future__ import annotations

import logging
import webbrowser

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager import __version__
from easy_scsmodmanager.services.update_core import UpdateInfo
from easy_scsmodmanager.services.update_service import UpdateService
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t

log = logging.getLogger(__name__)


class UpdateDialog(QDialog):
    """Update info with download/install controls or a releases-page pointer."""

    def __init__(
        self, info: UpdateInfo, service: UpdateService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._info = info
        self._svc = service
        self._dl_path: str | None = None

        self.setWindowTitle(t("update.dialog_title"))
        self.setMinimumWidth(540)
        self.setStyleSheet(f"background-color: {Theme.BACKGROUND}; color: {Theme.TEXT};")
        self._build()

        self._svc.download_progress.connect(self._on_progress)
        self._svc.download_finished.connect(self._on_finished)
        self._svc.download_failed.connect(self._on_failed)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        new = QLabel(t("update.new_version", version=self._info.version))
        new.setStyleSheet("font-weight: bold; font-size: 15px;")
        root.addWidget(new)
        root.addWidget(QLabel(t("update.current_version", version=__version__)))

        if self._info.download_size:
            mb = self._info.download_size / (1024 * 1024)
            root.addWidget(QLabel(t("update.download_size", size=f"{mb:.1f} MB")))

        notes_hdr = QLabel(t("update.release_notes"))
        notes_hdr.setStyleSheet("font-weight: bold;")
        root.addWidget(notes_hdr)

        notes = QTextBrowser()
        notes.setMarkdown(self._info.release_notes)
        notes.setMinimumHeight(200)
        notes.setStyleSheet(f"background-color: {Theme.SURFACE}; color: {Theme.TEXT};")
        root.addWidget(notes)

        if not self._info.can_self_update:
            hint = QLabel(t("update.package_hint"))
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
            root.addWidget(hint)

        self._bar = QProgressBar()
        self._bar.setVisible(False)
        root.addWidget(self._bar)
        self._status = QLabel("")
        self._status.setVisible(False)
        root.addWidget(self._status)

        row = QHBoxLayout()
        row.addStretch()
        later = QPushButton(t("update.later"))
        later.setStyleSheet(_secondary_style())
        later.clicked.connect(self.reject)
        row.addWidget(later)

        self._act = QPushButton()
        self._act.setStyleSheet(_primary_style())
        if self._info.can_self_update:
            self._act.setText(t("update.download_install"))
            self._act.clicked.connect(self._on_act)
        else:
            self._act.setText(t("update.open_releases"))
            self._act.clicked.connect(self._open_releases)
        row.addWidget(self._act)
        root.addLayout(row)

    # ---- self-update flow ---------------------------------------------- #

    def _on_act(self) -> None:
        if self._dl_path:
            self._do_install()
        else:
            self._act.setEnabled(False)
            self._bar.setVisible(True)
            self._bar.setRange(0, self._info.download_size or 0)
            self._status.setVisible(True)
            self._status.setText(t("update.downloading", percent="0"))
            self._svc.download_update(self._info)

    def _on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self._bar.setRange(0, total)
            self._bar.setValue(received)
            self._status.setText(t("update.downloading", percent=str(int(received * 100 / total))))

    def _on_finished(self, path: str) -> None:
        self._dl_path = path
        self._status.setText(t("update.ready_to_install"))
        self._act.setText(t("update.restart_now"))
        self._act.setEnabled(True)

    def _on_failed(self, error: str) -> None:
        self._status.setText(t("update.download_error", error=error))
        self._act.setText(t("update.download_install"))
        self._act.setEnabled(True)
        self._bar.setVisible(False)

    def _do_install(self) -> None:
        self.accept()
        if not UpdateService.install(self._dl_path or ""):
            self._open_releases()

    def _open_releases(self) -> None:
        if self._info.html_url:
            webbrowser.open(self._info.html_url)

    def reject(self) -> None:
        self._svc.cancel()
        super().reject()


def _primary_style() -> str:
    return (
        f"QPushButton {{ background-color: {Theme.PRIMARY}; color: {Theme.TEXT};"
        f"border-radius: 3px; padding: 6px 14px; font-weight: 600; }}"
        f"QPushButton:hover {{ background-color: {Theme.PRIMARY_HOVER}; }}"
        f"QPushButton:disabled {{ background-color: {Theme.SURFACE_HOVER}; color: {Theme.TEXT_DIM}; }}"
    )


def _secondary_style() -> str:
    return (
        f"QPushButton {{ background-color: {Theme.SURFACE_HOVER}; color: {Theme.TEXT};"
        f"border-radius: 3px; padding: 6px 14px; }}"
        f"QPushButton:hover {{ background-color: {Theme.SURFACE_SELECTED}; }}"
    )
