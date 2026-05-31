"""MapCombo serialisation: share the map block of a load order between users.

A MapCombo captures only the mods that sit in the Maps group, in order. The
match key is the mod's internal name from profile.sii (stable); the display
name is carried along purely so a missing-maps message is readable.

This module is pure and free of Qt: it serialises, parses, diffs missing maps,
and reorders a maps block. The dialog layer is a thin shell over it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from easy_scsmodmanager.core.version_compare import compare_versions
from easy_scsmodmanager.services.profile_reader import ActiveMod

FORMAT_ID = "easy-scsmodmanager-mapcombo"
FORMAT_VERSION = 2  # v2 adds per-entry package_version; v1 files still load


@dataclass(frozen=True)
class MapComboEntry:
    name: str
    display_name: str
    package_version: str = ""  # the version the combo was built with (v2)


class MapComboError(ValueError):
    """Raised when a file is not a readable MapCombo."""


def serialize(entries: list[MapComboEntry]) -> str:
    """Render the maps block as pretty JSON suitable for sharing."""
    payload = {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "maps": [
            {
                "name": e.name,
                "display_name": e.display_name,
                "package_version": e.package_version,
            }
            for e in entries
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def parse(text: str) -> list[MapComboEntry]:
    """Parse a MapCombo file (v1 or v2). Raises MapComboError on bad input.

    v1 files have no ``package_version`` per entry; it defaults to empty, so
    the version check simply treats those as "not comparable".
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MapComboError(str(exc)) from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT_ID:
        raise MapComboError("not a MapCombo file")
    raw_maps = data.get("maps")
    if not isinstance(raw_maps, list):
        raise MapComboError("missing maps list")
    entries: list[MapComboEntry] = []
    for item in raw_maps:
        if not isinstance(item, dict) or "name" not in item:
            raise MapComboError("malformed map entry")
        entries.append(
            MapComboEntry(
                name=str(item["name"]),
                display_name=str(item.get("display_name", "")),
                package_version=str(item.get("package_version", "")),
            )
        )
    return entries


def missing(combo: list[MapComboEntry], installed_names: set[str]) -> list[MapComboEntry]:
    """Combo entries whose mod is not installed, in combo order."""
    return [e for e in combo if e.name not in installed_names]


def outdated(
    combo: list[MapComboEntry], installed_versions: Mapping[str, str]
) -> list[tuple[MapComboEntry, str]]:
    """Combo entries whose version is NEWER than the locally installed one.

    ``installed_versions`` maps mod_name -> local package_version. Returns
    ``(entry, local_version)`` only when both versions parse and the combo's
    is strictly newer. Unparseable versions are skipped (no false "update"
    claim). Missing mods are handled by :func:`missing`, not here. A HINT
    only - never blocks the import.
    """
    result: list[tuple[MapComboEntry, str]] = []
    for entry in combo:
        if not entry.package_version:
            continue
        local = installed_versions.get(entry.name)
        if not local:
            continue
        verdict = compare_versions(local, entry.package_version)
        if verdict is not None and verdict < 0:
            result.append((entry, local))
    return result


def reorder(maps_block: list[ActiveMod], combo: list[MapComboEntry]) -> list[ActiveMod]:
    """Reorder a maps block to match the combo.

    Mods named in the combo come first, in combo order. Any maps in the block
    that the combo does not mention keep their relative order and follow after,
    so the operation never drops a local map.
    """
    by_name = {m.name: m for m in maps_block}
    ordered = [by_name[e.name] for e in combo if e.name in by_name]
    placed = {m.name for m in ordered}
    leftovers = [m for m in maps_block if m.name not in placed]
    return ordered + leftovers
