"""Top-right widget that identifies which profile is loaded.

Shows avatar (when present), the decoded profile name and the
active-mod count. A small switch-profile button opens a popup menu
populated by the main window with all discovered profiles - clicking
one emits :pyattr:`profile_selected`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.services.profile_reader import Profile
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t


@dataclass(frozen=True)
class ProfileChoice:
    """Lightweight view of a profile for the switcher menu."""

    sii_path: Path
    display_name: str
    active_count: int
    is_current: bool


class ProfileHeader(QWidget):
    AVATAR_SIZE = 48

    profile_selected = pyqtSignal(object)  # ProfileChoice
    backup_requested = pyqtSignal()
    restore_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: Profile | None = None
        self._choices: list[ProfileChoice] = []
        self._game_name = ""

        self.setStyleSheet(f"background-color: {Theme.SURFACE}; border-radius: 4px;")

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(10)

        self._avatar = QLabel()
        self._avatar.setFixedSize(QSize(self.AVATAR_SIZE, self.AVATAR_SIZE))
        self._avatar.setStyleSheet(f"background-color: {Theme.BACKGROUND}; border-radius: 24px;")
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._avatar)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        self._name_label = QLabel(t("profile_header.no_profile"))
        self._name_label.setStyleSheet(
            f"color: {Theme.ACCENT}; font-weight: bold; font-size: 13px;"
        )
        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 11px;")
        text_col.addWidget(self._name_label)
        text_col.addWidget(self._meta_label)
        root.addLayout(text_col, 1)

        self._switch_btn = QToolButton()
        self._switch_btn.setText("▾")
        self._switch_btn.setToolTip(t("profile_header.switch_profile"))
        self._switch_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._switch_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {Theme.PRIMARY};
                color: {Theme.TEXT};
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QToolButton:hover {{ background-color: {Theme.PRIMARY_HOVER}; }}
            QToolButton::menu-indicator {{ image: none; }}
            """)
        self._menu = QMenu(self)
        self._switch_btn.setMenu(self._menu)
        self._switch_btn.setEnabled(False)

        action_col = QVBoxLayout()
        action_col.setContentsMargins(0, 0, 0, 0)
        action_col.setSpacing(3)
        action_col.addWidget(self._switch_btn)

        backup_row = QHBoxLayout()
        backup_row.setContentsMargins(0, 0, 0, 0)
        backup_row.setSpacing(4)
        self._backup_btn = QPushButton(t("profile_header.backup"))
        self._backup_btn.setToolTip(t("profile_header.backup_tooltip", game=self._game_name))
        self._backup_btn.setStyleSheet(_secondary_button_style())
        self._backup_btn.setEnabled(False)
        self._backup_btn.clicked.connect(self.backup_requested.emit)
        self._restore_btn = QPushButton(t("common.restore"))
        self._restore_btn.setToolTip(t("profile_header.restore_tooltip"))
        self._restore_btn.setStyleSheet(_secondary_button_style())
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self.restore_requested.emit)
        backup_row.addWidget(self._backup_btn)
        backup_row.addWidget(self._restore_btn)
        action_col.addLayout(backup_row)

        root.addLayout(action_col)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def set_game_name(self, game_name: str) -> None:
        # keep the backup tooltip naming the active game, not a hardcoded one
        self._game_name = game_name
        self._backup_btn.setToolTip(t("profile_header.backup_tooltip", game=game_name))

    def set_profile(
        self,
        profile: Profile | None,
        *,
        avatar_path: Path | None = None,
        meta_text: str = "",
        restorable: bool = False,
    ) -> None:
        self._profile = profile

        if profile is None:
            self._name_label.setText(t("profile_header.no_profile"))
            self._meta_label.setText("")
            self._avatar.clear()
            self._backup_btn.setEnabled(False)
            # a corrupt/unreadable profile still has a path to restore from
            self._restore_btn.setEnabled(restorable)
            return

        self._name_label.setText(profile.profile_name or profile.dir_name)
        self._meta_label.setText(meta_text)
        self._backup_btn.setEnabled(True)
        self._restore_btn.setEnabled(True)

        if avatar_path is not None and avatar_path.is_file():
            pix = QPixmap(str(avatar_path))
            if not pix.isNull():
                self._avatar.setPixmap(
                    pix.scaled(
                        self.AVATAR_SIZE,
                        self.AVATAR_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self._avatar.clear()

    def set_profile_choices(self, choices: list[ProfileChoice]) -> None:
        """Populate the switcher menu with the available profiles."""
        self._choices = choices
        self._menu.clear()
        for choice in choices:
            label = f"{choice.display_name}  ({choice.active_count} active)"
            if choice.is_current:
                label = "✓  " + label
            action = QAction(label, self._menu)
            action.triggered.connect(lambda _checked=False, c=choice: self.profile_selected.emit(c))
            self._menu.addAction(action)
        self._switch_btn.setEnabled(len(choices) > 1)


def _primary_button_style() -> str:
    return (
        f"QToolButton {{ background-color: {Theme.PRIMARY}; color: {Theme.TEXT};"
        f"border-radius: 3px; padding: 4px 10px; font-size: 12px; }}"
        f"QToolButton:hover {{ background-color: {Theme.PRIMARY_HOVER}; }}"
        f"QToolButton:disabled {{ background-color: {Theme.SURFACE_HOVER}; color: {Theme.TEXT_DIM}; }}"
        "QToolButton::menu-indicator { image: none; }"
    )


def _secondary_button_style() -> str:
    return (
        f"QPushButton {{ background-color: {Theme.SURFACE_HOVER}; color: {Theme.TEXT};"
        f"border: 1px solid {Theme.SURFACE_HOVER}; border-radius: 3px;"
        f"padding: 3px 10px; font-size: 11px; }}"
        f"QPushButton:hover {{ background-color: {Theme.PRIMARY}; }}"
        f"QPushButton:disabled {{ color: {Theme.TEXT_DIM}; }}"
    )
