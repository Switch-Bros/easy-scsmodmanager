"""Persistent user settings via QSettings.

QSettings stores per-OS in the idiomatic place (Registry on Windows, plist on
macOS, ini under ~/.config on Linux) - so we never reintroduce a hardcoded home
dir. Kept small on purpose: the chosen language and optional manual path
overrides for when auto-detection misses the game install. An unset value reads
back as ``None``; setting ``None`` clears the key.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings

from easy_scsmodmanager.core.game_paths import Game

ORG = "Switch-Bros"
APP = "easy-scsmodmanager"

_KEY_LANGUAGE = "language"


def _documents_key(game: Game) -> str:
    return f"paths/{game.value}_documents"


def _workshop_key(game: Game) -> str:
    return f"paths/{game.value}_workshop"


def _install_key(game: Game) -> str:
    return f"paths/{game.value}_install"


class SettingsStore:
    """Thin typed wrapper around a QSettings instance."""

    def __init__(self, settings: QSettings | None = None) -> None:
        # Tests inject a QSettings(path, IniFormat) so they never touch the
        # real registry; production uses the org/app default location.
        self._s = settings if settings is not None else QSettings(ORG, APP)

    def get_language(self) -> str | None:
        return _clean(self._s.value(_KEY_LANGUAGE))

    def set_language(self, lang: str | None) -> None:
        _put(self._s, _KEY_LANGUAGE, lang)

    def get_documents_override(self, game: Game) -> Path | None:
        return _as_path(self._s.value(_documents_key(game)))

    def set_documents_override(self, game: Game, path: Path | None) -> None:
        _put(self._s, _documents_key(game), str(path) if path else None)

    def get_workshop_override(self, game: Game) -> Path | None:
        return _as_path(self._s.value(_workshop_key(game)))

    def set_workshop_override(self, game: Game, path: Path | None) -> None:
        _put(self._s, _workshop_key(game), str(path) if path else None)

    def get_install_override(self, game: Game) -> Path | None:
        """The game's install dir (holds base.scs/def.scs), if set manually."""
        return _as_path(self._s.value(_install_key(game)))

    def set_install_override(self, game: Game, path: Path | None) -> None:
        _put(self._s, _install_key(game), str(path) if path else None)


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_path(value: object) -> Path | None:
    text = _clean(value)
    return Path(text) if text else None


def _put(settings: QSettings, key: str, value: str | None) -> None:
    if value:
        settings.setValue(key, value)
    else:
        settings.remove(key)
