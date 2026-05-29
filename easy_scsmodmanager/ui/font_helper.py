#
# easy_scsmodmanager/ui/font_helper.py
# Loads the bundled Inter + Noto Color Emoji fonts and applies them app-wide
#
# Inter is OFL-licensed and close to Steam's own look, so the app matches ETS2's
# launcher feel on every platform. Variable font = all weights in one file.
#

from __future__ import annotations

import logging
from importlib import resources

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

__all__ = ["FontHelper"]

_FONT_PKG = "easy_scsmodmanager.resources.fonts"


class FontHelper:
    """Loads Inter + emoji fonts and hands out QFonts. Idempotent load."""

    FONT_NAME = "Inter"
    FONT_FILE = "InterVariable.ttf"
    EMOJI_FILE = "NotoColorEmoji.ttf"

    _loaded = False

    @classmethod
    def load(cls) -> None:
        if cls._loaded:
            return
        cls._add(cls.FONT_FILE, required=True)
        cls._add(cls.EMOJI_FILE, required=False)  # nice-to-have, don't die without it
        cls._loaded = True

    @classmethod
    def _add(cls, filename: str, *, required: bool) -> None:
        try:
            res = resources.files(_FONT_PKG) / filename
            with resources.as_file(res) as path:
                fid = QFontDatabase.addApplicationFont(str(path)) if path.exists() else -1
        except (FileNotFoundError, ModuleNotFoundError):
            fid = -1
        if fid == -1:
            if required:
                raise FileNotFoundError(f"font not found: {filename}")
            logger.warning(f"optional font missing, skipping: {filename}")
            return
        fams = QFontDatabase.applicationFontFamilies(fid)
        logger.info(f"loaded font {fams[0] if fams else filename}")

    @classmethod
    def font(cls, size: int = 10, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
        cls.load()
        f = QFont(cls.FONT_NAME, size)
        f.setWeight(weight)
        return f

    @classmethod
    def apply_app_font(cls, app: QApplication, size: int = 10) -> None:
        cls.load()
        app.setFont(cls.font(size))
        logger.info(f"app font set to {cls.FONT_NAME} {size}pt")
