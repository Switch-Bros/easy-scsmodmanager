"""Modal dialog showing a mod's manifest details and description text."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.core.mod_categories import canonical_categories, i18n_key
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t
from easy_scsmodmanager.utils.scs_markup import scs_markup_to_html


class ModInfoDialog(QDialog):
    """Read-only details for one mod: name, author, version, category, description."""

    def __init__(
        self, mod: ScannedMod, parent: QWidget | None = None, *, display_name: str | None = None
    ) -> None:
        super().__init__(parent)
        self._mod = mod
        self._display_name_override = display_name

        self.setWindowTitle(t("dialog.info.title"))
        self.setMinimumSize(440, 360)
        self.setStyleSheet(f"background-color: {Theme.BACKGROUND}; color: {Theme.TEXT};")

        root = QVBoxLayout(self)
        root.setSpacing(8)

        self._header = QLabel(self._display_name())
        self._header.setStyleSheet(
            f"color: {Theme.TEXT_MOD_NAME}; font-weight: bold; font-size: 16px;"
        )
        self._header.setWordWrap(True)
        root.addWidget(self._header)

        meta = self._meta_line()
        if meta:
            meta_label = QLabel(meta)
            meta_label.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
            meta_label.setWordWrap(True)
            root.addWidget(meta_label)

        desc_caption = QLabel(t("dialog.info.description"))
        desc_caption.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
        root.addWidget(desc_caption)

        self._description = QTextEdit()
        self._description.setReadOnly(True)
        self._description.setHtml(scs_markup_to_html(self._description_or_fallback()))
        self._description.setStyleSheet(
            f"background-color: {Theme.SURFACE}; color: {Theme.TEXT}; "
            f"border: {Theme.BORDER_WIDTH}px solid {Theme.SURFACE}; border-radius: 4px;"
        )
        root.addWidget(self._description, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close is not None:
            close.setText(t("dialog.info.close"))
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)

    def description_text(self) -> str:
        return self._description.toPlainText()

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    def _display_name(self) -> str:
        if self._display_name_override:
            return self._display_name_override
        if self._mod.manifest is not None and self._mod.manifest.display_name:
            return self._mod.manifest.display_name
        return self._mod.path.stem

    def _meta_line(self) -> str:
        man = self._mod.manifest
        if man is None:
            return ""
        parts: list[str] = []
        if man.author:
            parts.append(f"{t('dialog.info.author')}: {man.author}")
        if man.package_version:
            parts.append(f"{t('dialog.info.version')}: {man.package_version}")
        cats = canonical_categories(man.categories)
        names = ", ".join(t(i18n_key(c)) for c in cats)
        parts.append(f"{t('dialog.info.category')}: {names}")
        return "   |   ".join(parts)

    def _description_or_fallback(self) -> str:
        text = (self._mod.description or "").strip()
        return text if text else t("dialog.info.no_description")
