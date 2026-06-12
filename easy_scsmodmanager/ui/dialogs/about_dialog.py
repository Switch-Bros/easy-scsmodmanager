# SPDX-License-Identifier: GPL-3.0-or-later
"""Two-column About dialog: logo on the left, project info on the right.

The description, credits and "built with" line are curated here on purpose and
deliberately NOT routed through the translation files - only EN and DE are kept
in sync by hand, and other locales fall back to EN. Everything that is genuinely
reusable (the Close button) still goes through ``t()``.
"""

from __future__ import annotations

import webbrowser
from importlib import resources

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager import (
    __app_name__,
    __author__,
    __license__,
    __release_date__,
    __version__,
)
from easy_scsmodmanager.ui.font_helper import FontHelper
from easy_scsmodmanager.ui.menu.main_menu import GITHUB_REPO_URL
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import current_language, emoji, t

__all__ = ["AboutDialog"]

# Curated copy - controlled by SwitchBros, intentionally outside the i18n files.
_DESCRIPTION = {
    "en": (
        "Free, open-source mod and profile manager for Euro Truck Simulator 2 "
        "and American Truck Simulator. Conflict detection, load-order groups, "
        "profiles, and mod-list sharing."
    ),
    "de": (
        "Freier, quelloffener Mod- und Profil-Manager für Euro Truck Simulator 2 "
        "und American Truck Simulator. Konflikterkennung, Load-Order-Gruppen, "
        "Profile und Mod-Listen-Teilen."
    ),
}

# (name, contribution, url) - each rendered as one clickable row.
_CREDITS = [
    (
        "huayishuang",
        "Simplified Chinese translation",
        "https://github.com/huayishuang",
    ),
    (
        "Naider266",
        "Mod-list sharing idea - ETS2 Profile Mod Swapper",
        "https://ets2-mod-swapper.vercel.app",
    ),
]

_THANKS = (
    "Thanks to the forum community for reports & ideas "
    "(LLBBC, 00player00, TwinShadow, Sikay ...)"
)


def _description() -> str:
    return _DESCRIPTION.get(current_language(), _DESCRIPTION["en"])


def _built_with() -> str:
    # BVB Dortmund yellow-black-yellow - had to pick a club.
    hearts = emoji("yellow_heart") + emoji("black_heart") + emoji("yellow_heart")
    prefix = "Erstellt mit" if current_language() == "de" else "Built with"
    return f"{prefix} Python, PyQt6 & {hearts}"


class _ClickableLabel(QLabel):
    """A QLabel that emits ``clicked`` on a left mouse press."""

    clicked = pyqtSignal()

    def mousePressEvent(self, ev) -> None:  # noqa: N802 (Qt override)
        self.clicked.emit()
        super().mousePressEvent(ev)


class AboutDialog(QDialog):
    """Modal About dialog using the app theme tokens (no hardcoded colours)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("dialog.about.title"))
        self.setMinimumWidth(560)
        self._credit_labels: list[QLabel] = []

        self.setStyleSheet(
            f"QDialog {{ background-color: {Theme.BACKGROUND}; }}"
            f"QLabel {{ color: {Theme.TEXT}; background: transparent; }}"
            f"QPushButton {{ background-color: {Theme.SURFACE}; color: {Theme.TEXT};"
            f" border: 1px solid {Theme.BORDER}; border-radius: 3px; padding: 8px 24px; }}"
            f"QPushButton:hover {{ background-color: {Theme.SURFACE_HOVER}; }}"
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.addLayout(self._logo_col())

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet(f"color: {Theme.SURFACE_HOVER};")
        divider.setFixedWidth(1)
        root.addSpacing(20)
        root.addWidget(divider)
        root.addSpacing(20)

        root.addLayout(self._info_col(), stretch=1)

    # ------------------------------------------------------------------ #
    # columns
    # ------------------------------------------------------------------ #
    def _logo_col(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = _ClickableLabel()
        logo.setCursor(Qt.CursorShape.PointingHandCursor)
        logo.setToolTip(GITHUB_REPO_URL)

        res = resources.files("easy_scsmodmanager.resources") / "icon.png"
        with resources.as_file(res) as path:
            pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    200,
                    200,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            logo.setText(__app_name__)
            logo.setFont(FontHelper.font(16, QFont.Weight.Bold))

        logo.clicked.connect(lambda: webbrowser.open(GITHUB_REPO_URL))
        col.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
        return col

    def _info_col(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(6)

        name = QLabel(__app_name__)
        name.setFont(FontHelper.font(18, QFont.Weight.Bold))
        name.setStyleSheet(f"color: {Theme.WHITE};")
        col.addWidget(name)

        version = QLabel(f"Version {__version__}  -  {__release_date__}")
        version.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 12px;")
        col.addWidget(version)

        col.addSpacing(8)

        desc = QLabel(_description())
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px;")
        col.addWidget(desc)

        col.addSpacing(4)
        col.addWidget(self._hline())

        credits_hdr = QLabel("Credits")
        credits_hdr.setFont(FontHelper.font(11, QFont.Weight.Bold))
        col.addWidget(credits_hdr)

        for credit_name, contribution, url in _CREDITS:
            row = self._link_label(
                f'<a href="{url}" style="color: {Theme.PRIMARY}; '
                f'text-decoration: none;"><b>{credit_name}</b></a> - {contribution}'
            )
            self._credit_labels.append(row)
            col.addWidget(row)

        thanks = QLabel(_THANKS)
        thanks.setWordWrap(True)
        thanks.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
        col.addWidget(thanks)

        col.addWidget(self._hline())

        meta = QLabel(f"License: {__license__}  |  Author: {__author__}")
        meta.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 12px;")
        col.addWidget(meta)

        link = self._link_label(
            f'GitHub: <a href="{GITHUB_REPO_URL}" '
            f'style="color: {Theme.PRIMARY};">{GITHUB_REPO_URL}</a>'
        )
        link.setStyleSheet("font-size: 12px;")
        col.addWidget(link)

        col.addStretch()

        built = QLabel(_built_with())
        built.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
        built.setAlignment(Qt.AlignmentFlag.AlignRight)
        col.addWidget(built)

        col.addSpacing(4)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close = QPushButton(t("common.close"))
        close.setMinimumWidth(100)
        close.clicked.connect(self.accept)
        button_row.addWidget(close)
        col.addLayout(button_row)

        return col

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _link_label(self, rich_text: str) -> QLabel:
        label = QLabel(rich_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setCursor(Qt.CursorShape.PointingHandCursor)
        label.linkActivated.connect(webbrowser.open)
        return label

    @staticmethod
    def _hline() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {Theme.SURFACE_HOVER};")
        line.setFixedHeight(1)
        return line
