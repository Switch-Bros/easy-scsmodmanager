"""Persistent user settings via QSettings.

QSettings stores per-OS in the idiomatic place (Registry on Windows, plist on
macOS, ini under ~/.config on Linux) - so we never reintroduce a hardcoded home
dir. Kept small on purpose: the chosen language and optional manual path
overrides for when auto-detection misses the game install. An unset value reads
back as ``None``; setting ``None`` clears the key.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PyQt6.QtCore import QSettings

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.core.map_base_mods import DEFAULT_MAP_BASE_NAMES

ORG = "Switch-Bros"
APP = "easy-scsmodmanager"

_KEY_LANGUAGE = "language"
_KEY_MAP_BASE_NAMES = "map_base_names"
_KEY_ACTIVE_GAME = "active_game"
_KEY_UPDATE_CHECK = "update_check_on_startup"
_KEY_GRID_JUMP = "grid_click_jumps_to_active"


def _documents_key(game: Game) -> str:
    return f"paths/{game.value}_documents"


def _workshop_key(game: Game) -> str:
    return f"paths/{game.value}_workshop"


def _install_key(game: Game) -> str:
    return f"paths/{game.value}_install"


def _last_profile_key(game: Game) -> str:
    return f"profiles/{game.value}_last_selected"


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

    def get_active_game(self) -> Game:
        """The game the window should open on. Defaults to ETS2."""
        raw = _clean(self._s.value(_KEY_ACTIVE_GAME))
        for game in Game:
            if game.value == raw:
                return game
        return Game.ETS2

    def set_active_game(self, game: Game) -> None:
        _put(self._s, _KEY_ACTIVE_GAME, game.value)

    def get_last_selected_profile(self, game: Game) -> Path | None:
        """The profile.sii the user last had open for this game, if any."""
        return _as_path(self._s.value(_last_profile_key(game)))

    def set_last_selected_profile(self, game: Game, path: Path | None) -> None:
        _put(self._s, _last_profile_key(game), str(path) if path else None)

    def get_update_check_on_startup(self) -> bool:
        return _as_bool(self._s.value(_KEY_UPDATE_CHECK), default=True)

    def set_update_check_on_startup(self, enabled: bool) -> None:
        # store the bool literally - _put would drop a False as "unset"
        self._s.setValue(_KEY_UPDATE_CHECK, enabled)

    def get_grid_click_jumps_to_active(self) -> bool:
        return _as_bool(self._s.value(_KEY_GRID_JUMP), default=False)

    def set_grid_click_jumps_to_active(self, enabled: bool) -> None:
        self._s.setValue(_KEY_GRID_JUMP, enabled)

    def get_map_base_names(self) -> tuple[str, ...]:
        raw = _clean(self._s.value(_KEY_MAP_BASE_NAMES))
        if not raw:
            return DEFAULT_MAP_BASE_NAMES
        parts = [p.strip() for p in raw.split("\n")]
        return tuple(p for p in parts if p)

    def set_map_base_names(self, names: Iterable[str]) -> None:
        joined = "\n".join(n.strip() for n in names if n.strip())
        _put(self._s, _KEY_MAP_BASE_NAMES, joined or None)


def _as_bool(value: object, *, default: bool) -> bool:
    # QSettings hands bools back as the strings "true"/"false"
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


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
