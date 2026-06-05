"""Discovers Steam library roots across platforms.

Steam stores its known library locations in ``steamapps/libraryfolders.vdf``
inside the Steam install directory. There can be multiple libraries on
different drives (e.g. ``/mnt/games/SteamLibrary``).

This module:

* enumerates platform-typical candidate Steam install locations,
* reads each ``libraryfolders.vdf`` it finds,
* returns the deduplicated set of library roots.

No path is hardcoded into business logic - everything is built from
environment variables (HOME, XDG_DATA_HOME, ProgramFiles(x86), ...).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import vdf

from easy_scsmodmanager.utils.win_registry import read_string

LIBRARYFOLDERS_RELATIVE = Path("steamapps") / "libraryfolders.vdf"

log = logging.getLogger(__name__)


def steam_install_candidates() -> list[Path]:
    """Plattform-typical Steam install paths. Not filtered for existence."""
    if sys.platform == "win32":
        return _windows_candidates()
    if sys.platform == "darwin":
        return _macos_candidates()
    return _linux_candidates()


def find_steam_installs() -> list[Path]:
    """Steam install dirs that actually contain libraryfolders.vdf."""
    return [c for c in steam_install_candidates() if (c / LIBRARYFOLDERS_RELATIVE).is_file()]


def read_library_paths_from_vdf(vdf_path: Path) -> list[Path]:
    """Parse a libraryfolders.vdf and return all library root paths in order."""
    if not vdf_path.is_file():
        raise FileNotFoundError(vdf_path)
    with vdf_path.open("r", encoding="utf-8") as f:
        data = vdf.load(f)

    root = data.get("libraryfolders") or data.get("LibraryFolders") or {}
    paths: list[Path] = []
    for key in sorted(root.keys(), key=_numeric_key):
        entry = root[key]
        if not isinstance(entry, dict):
            continue
        raw = entry.get("path") or entry.get("Path")
        if raw:
            paths.append(Path(raw))
    return paths


def discover_steam_libraries() -> list[Path]:
    """All library roots across all detected Steam installs, deduplicated."""
    installs = find_steam_installs()
    if installs:
        log.info("Steam installs: %s", ", ".join(str(p) for p in installs))
    else:
        log.info("no Steam install found")

    seen: set[Path] = set()
    result: list[Path] = []
    for install in installs:
        for lib in read_library_paths_from_vdf(install / LIBRARYFOLDERS_RELATIVE):
            if lib in seen:
                continue
            seen.add(lib)
            result.append(lib)

    log.info("Steam libraries: %s", ", ".join(str(p) for p in result) or "(none)")
    return result


def _numeric_key(key: str) -> tuple[int, str]:
    # libraryfolders.vdf indexes libraries with "0", "1", "2" ...
    try:
        return (int(key), "")
    except ValueError:
        return (10**9, key)


def _linux_candidates() -> list[Path]:
    home = Path(os.environ.get("HOME", "~")).expanduser()
    xdg_data = os.environ.get("XDG_DATA_HOME")
    xdg_data_path = Path(xdg_data) if xdg_data else home / ".local" / "share"

    return [
        home / ".steam" / "steam",
        xdg_data_path / "Steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
        home / "snap" / "steam" / "common" / ".local" / "share" / "Steam",
    ]


def _registry_steam_path() -> Path | None:
    """Steam's own install dir as Steam recorded it in the registry.

    The most reliable source on Windows - the user may have installed Steam
    anywhere. HKCU\\Software\\Valve\\Steam holds "SteamPath"; the per-machine
    HKLM\\...\\WOW6432Node copy keeps "InstallPath" as a fallback. Either can
    come back with forward slashes ("D:/Steam"), which Path handles fine.
    """
    raw = read_string("HKCU", r"Software\Valve\Steam", "SteamPath") or read_string(
        "HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"
    )
    return Path(raw) if raw else None


def _windows_candidates() -> list[Path]:
    candidates: list[Path] = []
    # registry first - it knows where Steam actually went
    reg = _registry_steam_path()
    if reg:
        candidates.append(reg)
    for var in ("ProgramFiles(x86)", "ProgramFiles", "ProgramW6432"):
        root = os.environ.get(var)
        if root:
            candidates.append(Path(root) / "Steam")
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.append(Path(user_profile) / "scoop" / "apps" / "steam" / "current")
    return candidates


def _macos_candidates() -> list[Path]:
    home = Path(os.environ.get("HOME", "~")).expanduser()
    return [home / "Library" / "Application Support" / "Steam"]
