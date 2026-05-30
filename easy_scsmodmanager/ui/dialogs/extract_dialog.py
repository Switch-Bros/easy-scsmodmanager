"""Unpack the game's .scs archives (base.scs, def.scs, dlc_*.scs) to a folder.

Lists the archives found in the game install directory as a checkable list,
plus a button to add any other .scs. Each selected archive extracts into its
own sub-folder of the destination (base.scs -> <dest>/base/), mirroring how
modders use the official scs_extractor.exe - but with our own reader, on every
platform, and with an optional "empty first" cleanup. Runs on a worker thread.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.services.scs_extractor import ExtractResult
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.threads.extract_thread import ExtractThread
from easy_scsmodmanager.utils.i18n import t


class ExtractDialog(QDialog):
    def __init__(self, install_dir: Path | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thread: ExtractThread | None = None

        self.setWindowTitle(t("dialog.extract.title"))
        self.setMinimumSize(640, 520)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BACKGROUND}; }}
            QLabel {{ color: {Theme.TEXT}; }}
            QListWidget, QLineEdit {{
                background-color: {Theme.SURFACE}; color: {Theme.TEXT};
                border: 1px solid {Theme.SURFACE_HOVER}; border-radius: 3px;
            }}
            QCheckBox {{ color: {Theme.TEXT}; }}
            QPushButton {{
                background-color: {Theme.SURFACE}; color: {Theme.TEXT};
                border: 1px solid {Theme.SURFACE_HOVER}; border-radius: 3px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ background-color: {Theme.SURFACE_HOVER}; }}
        """)
        self._build(install_dir)

    def _build(self, install_dir: Path | None) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        root.addWidget(QLabel(t("dialog.extract.archives_heading")))
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        root.addWidget(self._list, 1)
        if install_dir is not None:
            for scs in sorted(install_dir.glob("*.scs")):
                self._add_archive(scs)
        else:
            note = QLabel(t("dialog.extract.no_install"))
            note.setStyleSheet(f"color: {Theme.TEXT_DIM};")
            note.setWordWrap(True)
            root.addWidget(note)

        add_btn = QPushButton(t("dialog.extract.add_files"))
        add_btn.clicked.connect(self._on_add_files)
        root.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignLeft)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel(t("dialog.extract.dest")))
        self._dest_edit = QLineEdit()
        self._dest_edit.setReadOnly(True)
        dest_row.addWidget(self._dest_edit, 1)
        dest_browse = QPushButton(t("dialog.extract.browse"))
        dest_browse.clicked.connect(self._on_pick_dest)
        dest_row.addWidget(dest_browse)
        root.addLayout(dest_row)

        self._clean = QCheckBox(t("dialog.extract.clean"))
        root.addWidget(self._clean)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {Theme.TEXT_DIM};")
        root.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._extract_btn = QPushButton(t("dialog.extract.start"))
        self._extract_btn.clicked.connect(self._on_extract)
        self._close_btn = QPushButton(t("dialog.extract.close"))
        self._close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._extract_btn)
        btn_row.addWidget(self._close_btn)
        root.addLayout(btn_row)

    def _add_archive(self, scs: Path, checked: bool = False) -> None:
        if str(scs) in self._archive_paths():
            return
        item = QListWidgetItem(scs.name)
        item.setData(Qt.ItemDataRole.UserRole, str(scs))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._list.addItem(item)

    def _on_add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, t("dialog.extract.title"), "", "SCS (*.scs)")
        for f in files:
            self._add_archive(Path(f), checked=True)

    def _on_pick_dest(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, t("dialog.extract.dest"))
        if chosen:
            self._dest_edit.setText(chosen)

    def _items(self) -> list[QListWidgetItem]:
        items = (self._list.item(i) for i in range(self._list.count()))
        return [it for it in items if it is not None]

    def _archive_paths(self) -> set[str]:
        return {str(it.data(Qt.ItemDataRole.UserRole)) for it in self._items()}

    def _checked_archives(self) -> list[Path]:
        return [
            Path(it.data(Qt.ItemDataRole.UserRole))
            for it in self._items()
            if it.checkState() == Qt.CheckState.Checked
        ]

    def _on_extract(self) -> None:
        archives = self._checked_archives()
        if not archives:
            self._status.setText(t("dialog.extract.need_source"))
            return
        dest = self._dest_edit.text().strip()
        if not dest:
            self._status.setText(t("dialog.extract.need_dest"))
            return
        dest_dir = Path(dest)
        jobs = [(scs, dest_dir / scs.stem) for scs in archives]

        self._set_running(True)
        self._thread = ExtractThread(jobs, clean=self._clean.isChecked())
        self._thread.progress.connect(self._on_progress)
        self._thread.finished_with_results.connect(self._on_finished)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _on_progress(self, done: int, total: int, name: str) -> None:
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(done)
        self._status.setText(t("dialog.extract.progress", name=name, done=done, total=total))

    def _on_finished(self, results: list[tuple[Path, ExtractResult]]) -> None:
        extracted = sum(r.extracted for _, r in results)
        failed = sum(r.failed for _, r in results)
        cancelled = any(r.cancelled for _, r in results)
        if cancelled:
            self._status.setText(t("dialog.extract.cancelled", extracted=extracted))
        else:
            self._status.setText(
                t("dialog.extract.done", extracted=extracted, archives=len(results), failed=failed)
            )
        self._set_running(False)

    def _on_failed(self, message: str) -> None:
        self._status.setText(message)
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self._progress.setVisible(running)
        self._extract_btn.setEnabled(not running)
        if running:
            self._close_btn.setText(t("dialog.extract.cancel"))
            self._close_btn.clicked.disconnect()
            self._close_btn.clicked.connect(self._on_cancel)
        else:
            self._close_btn.setText(t("dialog.extract.close"))
            self._close_btn.clicked.disconnect()
            self._close_btn.clicked.connect(self.reject)

    def _on_cancel(self) -> None:
        if self._thread is not None:
            self._thread.cancel()
