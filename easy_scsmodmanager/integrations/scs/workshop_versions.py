"""Reads ``versions.sii`` from a Steam workshop content directory.

Workshop mods that ship more than one game-version variant store the
slot names + compatible game versions in ``versions.sii``::

    SiiNunit {
        package_version_info : .latest { package_name: "latest" }
        package_version_info : .158_content {
            package_name: "158_content"
            compatible_versions[]: "1.58.*"
        }
        package_version_info : .157_content {
            package_name: "157_content"
            compatible_versions[]: "1.57.*"
        }
        ...
    }

The actual payload (a ``.scs`` file or a directory) sits next to
``versions.sii`` under the slot name. We use this to pick a single
active slot per workshop folder so the scanner does not list every
historical version as a separate mod.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

from easy_scsmodmanager.integrations.sii.parser import SiiParseError, parse_sii

VERSIONS_SII = "versions.sii"
PACKAGE_VERSION_CLASS = "package_version_info"


@dataclass(frozen=True)
class VersionSlot:
    name: str
    compatible_versions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_default(self) -> bool:
        """A slot without compatible_versions is the catch-all (``universal``
        / ``latest``)."""
        return not self.compatible_versions

    def matches(self, game_version: str) -> bool:
        if not game_version:
            return False
        return any(fnmatch.fnmatch(game_version, p) for p in self.compatible_versions)


def read_versions_sii(workshop_dir: Path) -> list[VersionSlot]:
    """Returns the slots declared in versions.sii (empty if file is missing)."""
    target = workshop_dir / VERSIONS_SII
    if not target.is_file():
        return []
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
        units = parse_sii(text)
    except (SiiParseError, OSError):
        return []
    slots: list[VersionSlot] = []
    for unit in units:
        if unit.unit_class != PACKAGE_VERSION_CLASS:
            continue
        name = str(unit.properties.get("package_name", "")) or unit.unit_name.lstrip(".")
        raw_versions = unit.properties.get("compatible_versions", [])
        versions = tuple(raw_versions) if isinstance(raw_versions, list) else ()
        slots.append(VersionSlot(name=name, compatible_versions=versions))
    return slots


def pick_active_slot(slots: list[VersionSlot], game_version: str | None = None) -> str | None:
    """Returns the package_name of the slot that ETS2 would load.

    Preference order:
    1. The slot whose ``compatible_versions`` matches the running game
       version (e.g. ``"1.58.*"`` for game 1.58).
    2. The first slot without ``compatible_versions`` (the universal /
       latest fallback).
    3. The very first slot in the file (last resort).

    Returns None when no slots are declared.
    """
    if not slots:
        return None
    if game_version:
        for slot in slots:
            if slot.matches(game_version):
                return slot.name
    for slot in slots:
        if slot.is_default:
            return slot.name
    return slots[0].name


_NUMERIC_HELPER_NAMES = re.compile(r"^\d+(_content)?$|^downgrade_info_package$")


def workshop_helper_names(slots: list[VersionSlot], active: str | None) -> set[str]:
    """The set of slot names that should be hidden because they belong
    to the same workshop mod but are not the active version.

    Adds well-known helper names that show up in workshop archives
    (``150``, ``153_content``, ``downgrade_info_package``) so the
    scanner can skip them even when no versions.sii is present.
    """
    hidden: set[str] = set()
    for slot in slots:
        if slot.name != active:
            hidden.add(slot.name)
    # Conservative pattern catch-all for archives that ship helper-named
    # .scs files without listing them in versions.sii.
    return hidden


def is_helper_slot_name(name: str) -> bool:
    """True for names like ``150``, ``153_content`` or ``downgrade_info_package``."""
    return bool(_NUMERIC_HELPER_NAMES.match(name))
