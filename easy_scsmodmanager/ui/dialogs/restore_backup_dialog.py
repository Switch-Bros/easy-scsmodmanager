"""Dialog that lets the user pick a backup to restore (or delete)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.services.profile_backup import (
    BackupEntry,
    delete_backup,
    disk_usage_human,
)
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t


class RestoreBackupDialog(QDialog):
    """Modal dialog: list of backups, with Restore + Delete buttons."""

    def __init__(
        self,
        profile_display_name: str,
        backups: list[BackupEntry],
        parent: QWidget | None = None,
        game_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._backups = backups
        self._selected: BackupEntry | None = None

        self.setWindowTitle(t("dialog.restore.title"))
        self.setMinimumWidth(480)
        # styling comes from the global dark palette + GLOBAL_QSS now

        root = QVBoxLayout(self)
        root.setSpacing(8)

        header = QLabel(
            t("dialog.restore.header", profile=profile_display_name, count=len(backups))
        )
        header.setStyleSheet(f"color: {Theme.TEXT}; font-weight: bold;")
        header.setWordWrap(True)
        root.addWidget(header)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for entry in backups:
            item = QListWidgetItem(f"{entry.label}   ({disk_usage_human(entry.size_bytes)})")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list.addItem(item)
        if backups:
            self._list.setCurrentRow(0)
        root.addWidget(self._list, 1)

        warning = QLabel(t("dialog.restore.warning", game=game_name))
        warning.setStyleSheet(f"color: {Theme.DANGER}; font-size: 11px;")
        warning.setWordWrap(True)
        root.addWidget(warning)

        # Buttons: Restore (primary) + Delete (danger) + Close
        button_row = QHBoxLayout()
        self._delete_btn = QPushButton(t("dialog.restore.delete"))
        self._delete_btn.setStyleSheet(_secondary_button_style())
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        button_row.addWidget(self._delete_btn)
        button_row.addStretch(1)

        self._buttons = QDialogButtonBox()
        self._restore_btn = QPushButton(t("common.restore"))
        self._restore_btn.setStyleSheet(_primary_button_style())
        self._restore_btn.setDefault(True)
        self._buttons.addButton(self._restore_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        self._buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self._on_restore_clicked)
        self._buttons.rejected.connect(self.reject)
        button_row.addWidget(self._buttons)
        root.addLayout(button_row)

        # connect only now that the buttons exist - setCurrentRow above would
        # otherwise fire _on_selection_changed before _restore_btn is built
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._update_buttons_state()

    @property
    def selected(self) -> BackupEntry | None:
        return self._selected

    # ------------------------------------------------------------------ #
    # handlers
    # ------------------------------------------------------------------ #

    def _current_entry(self) -> BackupEntry | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _on_selection_changed(self) -> None:
        self._update_buttons_state()

    def _update_buttons_state(self) -> None:
        enabled = self._current_entry() is not None
        self._restore_btn.setEnabled(enabled)
        self._delete_btn.setEnabled(enabled)

    def _on_restore_clicked(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        choice = QMessageBox.question(
            self,
            t("dialog.restore.confirm_title"),
            t("dialog.restore.confirm_body", label=entry.label),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        self._selected = entry
        self.accept()

    def _on_delete_clicked(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        choice = QMessageBox.question(
            self,
            t("dialog.restore.delete_confirm_title"),
            t("dialog.restore.delete_confirm_body", label=entry.label),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        delete_backup(entry)
        # Remove the matching row.
        for i in range(self._list.count()):
            row_entry = self._list.item(i).data(Qt.ItemDataRole.UserRole)
            if row_entry is entry:
                self._list.takeItem(i)
                break
        self._backups.remove(entry)
        self._update_buttons_state()


def _primary_button_style() -> str:
    return (
        f"QPushButton {{ background-color: {Theme.PRIMARY}; color: {Theme.TEXT};"
        f"border-radius: 3px; padding: 6px 14px; font-weight: 600; }}"
        f"QPushButton:hover {{ background-color: {Theme.PRIMARY_HOVER}; }}"
        f"QPushButton:disabled {{ background-color: {Theme.SURFACE_HOVER}; color: {Theme.TEXT_DIM}; }}"
    )


def _secondary_button_style() -> str:
    return (
        f"QPushButton {{ background-color: {Theme.SURFACE_HOVER}; color: {Theme.TEXT};"
        f"border-radius: 3px; padding: 6px 14px; }}"
        f"QPushButton:hover {{ background-color: {Theme.DANGER}; }}"
        f"QPushButton:disabled {{ color: {Theme.TEXT_DIM}; }}"
    )
