"""Cross-platform discovery of ETS2 and ATS install paths.

A user can have any combination of:

* Linux native install (game installed without Proton) - data under
  ~/.local/share/<game>/ (XDG_DATA_HOME respected).
* Proton install (Steam + Proton) - data inside the Wine prefix at
  <SteamLibrary>/steamapps/compatdata/<app-id>/pfx/drive_c/users/
  steamuser/Documents/<game>/.
* Windows install - data under %USERPROFILE%/Documents/<game>/.
* macOS install - data under ~/Library/Application Support/<game>/.

The detector tries every plausible location relative to the user's
environment (HOME / USERPROFILE / discovered Steam libraries) and
returns every install that actually exists on disk. No path string
lives outside this module.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from easy_scsmodmanager.integrations.steam.library_detector import discover_steam_libraries


class Game(Enum):
    ETS2 = "ets2"
    ATS = "ats"


class InstallKind(Enum):
    LINUX_NATIVE = "linux_native"
    PROTON = "proton"
    WINDOWS = "windows"
    MACOS = "macos"
    MANUAL = "manual"  # user-provided path override (Settings dialog)


GAME_APP_ID: dict[Game, int] = {
    Game.ETS2: 227300,
    Game.ATS: 270880,
}

GAME_DIRECTORY_NAME: dict[Game, str] = {
    Game.ETS2: "Euro Truck Simulator 2",
    Game.ATS: "American Truck Simulator",
}


@dataclass(frozen=True)
class GameInstall:
    game: Game
    kind: InstallKind
    documents_dir: Path
    workshop_dir: Path | None

    @property
    def profiles_dir(self) -> Path:
        return self.documents_dir / "profiles"

    @property
    def mod_dir(self) -> Path:
        return self.documents_dir / "mod"


def linux_native_documents(game: Game) -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path(os.environ.get("HOME", "~")).expanduser() / ".local" / "share"
    return base / GAME_DIRECTORY_NAME[game]


def proton_documents_path(steam_library: Path, game: Game) -> Path:
    return (
        steam_library
        / "steamapps"
        / "compatdata"
        / str(GAME_APP_ID[game])
        / "pfx"
        / "drive_c"
        / "users"
        / "steamuser"
        / "Documents"
        / GAME_DIRECTORY_NAME[game]
    )


def workshop_dir_path(steam_library: Path, game: Game) -> Path:
    return steam_library / "steamapps" / "workshop" / "content" / str(GAME_APP_ID[game])


def windows_documents(game: Game) -> Path:
    user_profile = os.environ.get("USERPROFILE")
    onedrive = os.environ.get("OneDrive")  # noqa: SIM112 - real Windows env name
    docs_root = (
        Path(onedrive) / "Documents" if onedrive else Path(user_profile or "~") / "Documents"
    )
    return docs_root / GAME_DIRECTORY_NAME[game]


def macos_documents(game: Game) -> Path:
    home = Path(os.environ.get("HOME", "~")).expanduser()
    return home / "Library" / "Application Support" / GAME_DIRECTORY_NAME[game]


def find_game_install_dir(
    game: Game,
    steam_libraries: list[Path] | None = None,
) -> Path | None:
    """Locate the game's install directory (the one holding base.scs, def.scs).

    This is ``steamapps/common/<game>`` inside a Steam library - distinct from
    the documents directory (which holds mod/ and profiles/). Used by the SCS
    extractor to offer the game's own archives.
    """
    if steam_libraries is None:
        steam_libraries = discover_steam_libraries()
    for lib in steam_libraries:
        candidate = lib / "steamapps" / "common" / GAME_DIRECTORY_NAME[game]
        if candidate.is_dir():
            return candidate
    return None


def game_install_from_override(
    game: Game,
    documents_dir: Path,
    workshop_dir: Path | None = None,
) -> GameInstall:
    """Build a GameInstall from a user-set documents dir, skipping detection.

    Used when auto-detection misses the install (e.g. ETS2 moved to a
    non-default home dir on Windows). profiles_dir / mod_dir derive from
    documents_dir as usual. The path is trusted as-is; existence is the
    caller's concern.
    """
    return GameInstall(
        game=game,
        kind=InstallKind.MANUAL,
        documents_dir=documents_dir,
        workshop_dir=workshop_dir,
    )


def detect_game_installs(
    game: Game,
    steam_libraries: list[Path] | None = None,
) -> list[GameInstall]:
    """Returns every existing install for the given game across platforms.

    Pass ``steam_libraries=None`` to let the function discover them via
    libraryfolders.vdf, or pass a list (including empty) to skip discovery.
    """
    if steam_libraries is None:
        steam_libraries = discover_steam_libraries()

    installs: list[GameInstall] = []

    native_documents = _native_documents_for_current_platform(game)
    native_kind = _native_install_kind()
    if native_documents and native_kind and native_documents.is_dir():
        installs.append(
            GameInstall(
                game=game,
                kind=native_kind,
                documents_dir=native_documents,
                workshop_dir=None,
            )
        )

    if sys.platform.startswith("linux"):
        for lib in steam_libraries:
            proton_docs = proton_documents_path(lib, game)
            if not proton_docs.is_dir():
                continue
            workshop = workshop_dir_path(lib, game)
            installs.append(
                GameInstall(
                    game=game,
                    kind=InstallKind.PROTON,
                    documents_dir=proton_docs,
                    workshop_dir=workshop if workshop.is_dir() else None,
                )
            )

    return installs


def _native_documents_for_current_platform(game: Game) -> Path | None:
    if sys.platform.startswith("linux"):
        return linux_native_documents(game)
    if sys.platform == "win32":
        return windows_documents(game)
    if sys.platform == "darwin":
        return macos_documents(game)
    return None


def _native_install_kind() -> InstallKind | None:
    if sys.platform.startswith("linux"):
        return InstallKind.LINUX_NATIVE
    if sys.platform == "win32":
        return InstallKind.WINDOWS
    if sys.platform == "darwin":
        return InstallKind.MACOS
    return None
