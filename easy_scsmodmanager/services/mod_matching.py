"""Match profile.sii active-mod entries back to scanned mod files.

ETS2 references an active mod by a short ``name`` token in profile.sii
that is not always the same as the file/directory name on disk. We try
a number of strategies until one returns a hit so cross-references in
the UI (icon thumbnails, click-to-scroll) work for Workshop directory
mods, hashed workshop package IDs and the simple ``mod/<stem>.scs``
case at once.

Resolution strategies in order:

1. Direct stem match (``mod/foo.scs`` <-> ``active_mods[]: "foo|..."``).
2. Parent-directory match (``workshop/<id>/universal/`` <->
   ``active_mods[]: "<id>|..."`` - ETS2 strips the slot dir).
3. Workshop-id match (parent of parent for unpacked workshop slots).
4. Display-name equality (case-insensitive).

The first hit wins. Stores a lookup index in :class:`ActiveModMatcher`
so the GUI does not pay O(N) per row.
"""

from __future__ import annotations

from easy_scsmodmanager.services.mod_identity import (
    mod_name_for_path,
    workshop_id_for_path,
    workshop_id_from_active_name,
)
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.services.profile_reader import ActiveMod

# re-exported for callers that have always imported it from here
__all__ = [
    "ActiveModMatcher",
    "active_name_for",
    "mod_name_for_path",
    "resolve_display_name",
    "workshop_id_for_path",
]


class ActiveModMatcher:
    def __init__(self, scanned: list[ScannedMod]) -> None:
        self._by_stem: dict[str, ScannedMod] = {}
        self._by_parent: dict[str, ScannedMod] = {}
        self._by_workshop_id: dict[str, ScannedMod] = {}
        self._by_display_name: dict[str, ScannedMod] = {}

        for mod in scanned:
            stem = mod.path.stem
            self._by_stem.setdefault(stem.lower(), mod)

            parent = mod.path.parent.name
            self._by_parent.setdefault(parent.lower(), mod)

            workshop_id = _workshop_id_for(mod.path)
            if workshop_id is not None:
                self._by_workshop_id.setdefault(workshop_id, mod)

            if mod.manifest is not None and mod.manifest.display_name:
                self._by_display_name.setdefault(mod.manifest.display_name.lower(), mod)

    def lookup(self, active: ActiveMod) -> ScannedMod | None:
        name = active.name.lower()
        if name in self._by_stem:
            return self._by_stem[name]
        if name in self._by_parent:
            return self._by_parent[name]
        # Workshop ids look like "mod_workshop_package.000000003A4B7C12" -
        # the hex tail is the published-file-id with leading zeros.
        ws_id = _extract_workshop_id_from_name(active.name)
        if ws_id is not None and ws_id in self._by_workshop_id:
            return self._by_workshop_id[ws_id]
        if active.display_name:
            hit = self._by_display_name.get(active.display_name.lower())
            if hit is not None:
                return hit
        return None

    def installed_active_names(self, profile_actives: list[ActiveMod]) -> set[str]:
        """Returns the set of ``active.name`` values that have a matching
        mod on disk."""
        return {a.name for a in profile_actives if self.lookup(a) is not None}


# Backwards-compatible alias for the internal helper this module used
# before the public rename. workshop_id_for_path now lives in mod_identity.
_workshop_id_for = workshop_id_for_path


def resolve_display_name(
    mod: ScannedMod,
    active_display_names: dict[str, str],
    workshop_title: str | None = None,
) -> str:
    """Best human name for a mod.

    Many workshop manifests carry no display_name (the real name lives in the
    Steam metadata, which ETS2 mirrors into the profile's active_mods entry).
    Chain: manifest name -> the profile's active display -> a fetched workshop
    title -> the file stem as a last resort.
    """
    if mod.manifest is not None and mod.manifest.display_name:
        return mod.manifest.display_name
    profile_name = active_display_names.get(active_name_for(mod))
    if profile_name:
        return profile_name
    if workshop_title:
        return workshop_title
    return mod.path.stem


def active_name_for(mod: ScannedMod) -> str:
    """The name this mod takes in active_mods[] - inverse of lookup().

    Single source of truth: the mod's own stable identity (computed from its
    path). Kept as a function for the many call sites that already use it.
    """
    return mod.mod_name


# the public helper in mod_identity replaced the old private copy
_extract_workshop_id_from_name = workshop_id_from_active_name
