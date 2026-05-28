"""Single source of truth for UI colors, fonts, and sizing.

Hardcoding hex codes across widgets makes theming impossible. Every
visual constant lives here so a light/custom-theme switch later is a
matter of swapping the values, not chasing them across the codebase.
"""

from __future__ import annotations


class Theme:
    """Dark theme - mirrors the in-game ETS2 mod manager look."""

    # Base palette
    BACKGROUND = "#1A1A1A"
    SURFACE = "#2A2A2A"
    SURFACE_HOVER = "#3A3A3A"
    SURFACE_SELECTED = "#3D3D45"

    # Action / accent
    PRIMARY = "#3D7DDB"  # steam blue
    PRIMARY_HOVER = "#5293E8"
    ACCENT = "#F5C842"  # ETS2 mod-manager yellow
    ACCENT_HOVER = "#FFD75A"

    # Status
    SUCCESS = "#7BB72C"  # active mod
    WARNING = "#F5C842"  # conflict border
    DANGER = "#D04545"  # incompatible
    MUTED = "#999999"  # inactive / installed

    # Text
    TEXT = "#E0E0E0"
    TEXT_DIM = "#999999"
    TEXT_MOD_NAME = "#F5C842"  # mod name in orange-yellow

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
