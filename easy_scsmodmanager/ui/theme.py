"""Single source of truth for UI colors, fonts, sizing - and the dark theme.

Hardcoding hex codes across widgets makes theming impossible. Every visual
constant lives here, plus the two things that make the app carry its own dark
look regardless of the OS light/dark mode: a fully dark ``build_palette()`` and
a ``GLOBAL_QSS`` for the handful of widgets a palette alone cannot colour
(menus, checkbox indicators, popups, scrollbars, tooltips). app.py installs
both at startup, so a "system dark / apps light" Windows setup no longer leaks
a half-light palette into the window.

A light theme is intentionally out of scope; swapping the token values below is
all a future light/custom theme would need.

Contrast budget (WCAG 2.1, against the surface a colour sits on):
* primary text >= 4.5:1  (TEXT on BACKGROUND/SURFACE)
* secondary text >= 3:1 hard, 4.5 aimed for  (TEXT_DIM on SURFACE)
* disabled text / selection >= 3:1  (TEXT_DISABLED on BACKGROUND,
  SELECTION_TEXT on SELECTION)
The contrast unit test enforces these against the real token values, so an
unreadable colour can never be checked in again.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette


class Theme:
    """Dark theme - mirrors the in-game ETS2 mod manager look."""

    # Base palette
    BACKGROUND = "#1A1A1A"
    SURFACE = "#2A2A2A"
    SURFACE_HOVER = "#3A3A3A"
    SURFACE_SELECTED = "#3D3D45"
    ALTERNATE_BASE = "#303030"  # zebra rows in item views

    # Action / accent
    PRIMARY = "#3D7DDB"  # steam blue
    PRIMARY_HOVER = "#5293E8"
    ACCENT = "#F5C842"  # ETS2 mod-manager yellow
    ACCENT_HOVER = "#FFD75A"

    # Status
    SUCCESS = "#7BB72C"  # active mod
    WARNING = "#F5C842"  # conflict border
    DANGER = "#D04545"  # incompatible / destructive action (4.55:1 on #FFFFFF)
    DANGER_HOVER = "#B83C3C"  # darker on hover so it stays >= 4.5:1 (5.60:1)
    MUTED = "#999999"  # inactive / installed

    # Text
    TEXT = "#E0E0E0"
    TEXT_DIM = "#999999"
    TEXT_DISABLED = "#7A7A7A"  # disabled text, ~3.3:1 on BACKGROUND
    TEXT_MOD_NAME = "#F5C842"  # mod name in orange-yellow

    # Semantic aliases - so widgets/QSS read intent, not raw colour
    BORDER = SURFACE_HOVER
    PLACEHOLDER = TEXT_DIM
    SELECTION = PRIMARY
    SELECTION_TEXT = "#FFFFFF"  # HighlightedText on SELECTION, 4.07:1

    # Sizing - aligned with ETS2's native 276x162 mod icon dimensions
    ICON_WIDTH = 276
    ICON_HEIGHT = 162
    CARD_PADDING = 8
    CARD_RADIUS = 4
    BORDER_WIDTH = 2
    MOD_CARD_WIDTH = ICON_WIDTH + 2 * CARD_PADDING + 2 * BORDER_WIDTH
    MOD_CARD_HEIGHT = ICON_HEIGHT + 80  # icon + 2 text rows + paddings
    MOD_GRID_COLUMNS = 3
    ACTIVE_THUMBNAIL_WIDTH = 200
    ACTIVE_THUMBNAIL_HEIGHT = 112

    # Global stylesheet - ONLY what the palette cannot express. Built here from
    # the tokens above (bare names resolve in the class body during definition).
    GLOBAL_QSS = f"""
        QMenuBar {{ background-color: {BACKGROUND}; color: {TEXT}; }}
        QMenuBar::item {{ background: transparent; padding: 4px 10px; }}
        QMenuBar::item:selected {{ background-color: {SURFACE_SELECTED}; }}
        QMenu {{
            background-color: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER};
        }}
        QMenu::item:selected {{ background-color: {SURFACE_SELECTED}; }}
        QMenu::item:disabled {{ color: {TEXT_DISABLED}; }}
        QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 0; }}

        QCheckBox {{ color: {TEXT}; spacing: 6px; }}
        QCheckBox:disabled {{ color: {TEXT_DISABLED}; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            background-color: {SURFACE}; border: 1px solid {BORDER};
            border-radius: 3px;
        }}
        QCheckBox::indicator:checked {{
            background-color: {PRIMARY}; border: 1px solid {PRIMARY};
        }}
        QCheckBox::indicator:disabled {{ border: 1px solid {TEXT_DISABLED}; }}

        QPushButton {{
            background-color: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER}; border-radius: 3px; padding: 4px 10px;
        }}
        QPushButton:hover {{ background-color: {SURFACE_HOVER}; }}
        QPushButton:disabled {{ color: {TEXT_DISABLED}; }}

        QComboBox QAbstractItemView {{
            background-color: {SURFACE}; color: {TEXT};
            selection-background-color: {SELECTION};
            selection-color: {SELECTION_TEXT};
            border: 1px solid {BORDER};
        }}

        QListWidget {{
            background-color: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER}; border-radius: 4px;
        }}
        QListWidget::item:selected {{
            background-color: {SELECTION}; color: {SELECTION_TEXT};
        }}

        QScrollBar:vertical {{
            background: {BACKGROUND}; width: 12px; margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {SURFACE_HOVER}; min-height: 24px; border-radius: 6px;
        }}
        QScrollBar:horizontal {{
            background: {BACKGROUND}; height: 12px; margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {SURFACE_HOVER}; min-width: 24px; border-radius: 6px;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

        QToolTip {{
            background-color: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER};
        }}
    """

    @staticmethod
    def build_palette() -> QPalette:
        # every role set dark, including the Disabled group and PlaceholderText,
        # so no widget falls back to the OS palette
        pal = QPalette()
        bg = QColor(Theme.BACKGROUND)
        surface = QColor(Theme.SURFACE)
        text = QColor(Theme.TEXT)
        disabled = QColor(Theme.TEXT_DISABLED)

        roles = QPalette.ColorRole
        pal.setColor(roles.Window, bg)
        pal.setColor(roles.WindowText, text)
        pal.setColor(roles.Base, surface)
        pal.setColor(roles.AlternateBase, QColor(Theme.ALTERNATE_BASE))
        pal.setColor(roles.Text, text)
        pal.setColor(roles.PlaceholderText, QColor(Theme.PLACEHOLDER))
        pal.setColor(roles.Button, surface)
        pal.setColor(roles.ButtonText, text)
        pal.setColor(roles.ToolTipBase, surface)
        pal.setColor(roles.ToolTipText, text)
        pal.setColor(roles.Highlight, QColor(Theme.SELECTION))
        pal.setColor(roles.HighlightedText, QColor(Theme.SELECTION_TEXT))
        pal.setColor(roles.Link, QColor(Theme.PRIMARY))
        pal.setColor(roles.BrightText, QColor(Theme.DANGER))

        disabled_grp = QPalette.ColorGroup.Disabled
        for role in (roles.WindowText, roles.Text, roles.ButtonText):
            pal.setColor(disabled_grp, role, disabled)
        return pal

    # Status status text colors
    @classmethod
    def status_color(cls, status: str) -> str:
        return {
            "active": cls.SUCCESS,
            "inactive": cls.MUTED,
            "incompatible": cls.DANGER,
            # Error here means "container readable but metadata not
            # accessible" (typically ZipCrypto-protected manifest in map
            # mods). The mod itself works in-game. Render as muted with
            # an orange warning hint so users do not mistake it for
            # a broken or incompatible mod.
            "error": cls.MUTED,
        }.get(status, cls.MUTED)
