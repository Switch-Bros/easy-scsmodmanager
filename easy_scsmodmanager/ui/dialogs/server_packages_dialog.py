"""Edit which mods are optional in a multiplayer ``server_packages.sii``.

In-game export marks every mod required, so a player needs a separate profile
per server (forum #44). This lets a server admin flip ``optional_mod`` per mod
and write it back surgically (only those tokens change). The file is picked
inside the dialog; nothing is written until Save, and only when something
actually changed.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.services.server_packages import (
    ServerPackages,
    ServerPackagesError,
    read_server_packages,
    write_optional_flags,
)
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t

_PICKER_FILTER = "server_packages.sii (server_packages.sii);;SII (*.sii)"


class ServerPackagesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pkg: ServerPackages | None = None
        self._original: dict[str, bool] = {}  # nameless_id -> optional as loaded
        self._checks: dict[str, QCheckBox] = {}  # nameless_id -> row checkbox

        self.setWindowTitle(t("server_packages.title"))
        self.setMinimumSize(560, 520)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # file row - its own top block so a profile dropdown can grow in above it
        file_row = QHBoxLayout()
        open_btn = QPushButton(t("server_packages.open"))
        open_btn.clicked.connect(self._on_open)
        file_row.addWidget(open_btn)
        self._file_label = QLabel(t("server_packages.no_file"))
        self._file_label.setStyleSheet(f"color: {Theme.TEXT_DIM};")
        file_row.addWidget(self._file_label, 1)
        root.addLayout(file_row)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(
            [t("server_packages.col.mod"), t("server_packages.col.optional")]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 90)
        root.addWidget(self._table, 1)

        self._hint = QLabel("(i) " + t("server_packages.hint.mods_optioning"))
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
        self._hint.setVisible(False)  # only after a valid file is loaded
        root.addWidget(self._hint)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {Theme.TEXT_DIM};")
        root.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._close_btn = QPushButton(t("server_packages.close"))
        self._close_btn.clicked.connect(self._on_close)
        self._save_btn = QPushButton(t("server_packages.save"))
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setEnabled(False)
        btn_row.addWidget(self._close_btn)
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

    # ---- loading -------------------------------------------------------- #

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("server_packages.open"), "", _PICKER_FILTER)
        if not path:
            return
        try:
            pkg = read_server_packages(Path(path))
        except (ServerPackagesError, OSError):
            self._status.setText(t("server_packages.error.invalid"))
            return  # nothing written, the table keeps whatever was there
        self._load(pkg)

    def _load(self, pkg: ServerPackages) -> None:
        self._pkg = pkg
        self._file_label.setStyleSheet(f"color: {Theme.TEXT};")
        self._file_label.setText(pkg.path.name)
        self._file_label.setToolTip(str(pkg.path))
        self._original = {m.nameless_id: m.optional for m in pkg.mods}
        self._checks = {}

        self._table.setRowCount(len(pkg.mods))
        for row, mod in enumerate(pkg.mods):  # file order is kept
            name = QTableWidgetItem(mod.display_name)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, name)
            check = QCheckBox()
            check.setChecked(mod.optional)
            check.stateChanged.connect(self._refresh_dirty)
            self._table.setCellWidget(row, 1, _centered(check))
            self._checks[mod.nameless_id] = check

        self._hint.setVisible(True)
        self._status.clear()
        self._refresh_dirty()

    # ---- dirty / save --------------------------------------------------- #

    def _is_dirty(self) -> bool:
        return self._pkg is not None and any(
            cb.isChecked() != self._original[nid] for nid, cb in self._checks.items()
        )

    def _refresh_dirty(self) -> None:
        self._save_btn.setEnabled(self._is_dirty())

    def _on_save(self) -> None:
        if self._pkg is None or not self._is_dirty():
            return
        desired = {nid: cb.isChecked() for nid, cb in self._checks.items()}
        try:
            write_optional_flags(self._pkg.path, self._pkg.text, desired)
        except (ServerPackagesError, OSError) as exc:
            self._status.setText(str(exc))
            return
        # re-read so the kept text + originals match the new bytes for further edits
        self._pkg = read_server_packages(self._pkg.path)
        self._original = {m.nameless_id: m.optional for m in self._pkg.mods}
        self._status.setText(t("server_packages.saved"))
        self._refresh_dirty()

    # ---- closing -------------------------------------------------------- #

    def _on_close(self) -> None:
        if self._confirm_discard():
            self.reject()

    def _confirm_discard(self) -> bool:
        if not self._is_dirty():
            return True
        answer = QMessageBox.question(
            self,
            t("server_packages.title"),
            t("server_packages.discard"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: object) -> None:  # noqa: N802 - Esc / [x] also confirm
        if self._confirm_discard():
            event.accept()  # type: ignore[attr-defined]
        else:
            event.ignore()  # type: ignore[attr-defined]


def _centered(widget: QWidget) -> QWidget:
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addStretch(1)
    layout.addWidget(widget)
    layout.addStretch(1)
    return holder
