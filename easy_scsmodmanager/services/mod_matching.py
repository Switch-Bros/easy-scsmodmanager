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

from pathlib import Path

from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.services.profile_reader import ActiveMod


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


def _workshop_id_for(path: Path) -> str | None:
    """Detect the workshop published-file-id from a scanned mod path."""
    # Layouts we care about:
    #   .../workshop/content/<appid>/<workshop_id>/<file>.scs
    #   .../workshop/content/<appid>/<workshop_id>/<slot>/manifest.sii
    parts = path.parts
    if "workshop" not in parts or "content" not in parts:
        return None
    try:
        content_idx = parts.index("content")
    except ValueError:
        return None
    # appid sits at content_idx + 1, workshop_id at content_idx + 2.
    if content_idx + 2 >= len(parts):
        return None
    workshop_id = parts[content_idx + 2]
    if workshop_id.isdigit():
        return workshop_id
    return None


def _extract_workshop_id_from_name(name: str) -> str | None:
    """``mod_workshop_package.000000003A4B7C12`` -> ``"977853202"``.

    ETS2 stores workshop ids as a 16-char zero-padded hex string after
    a dot. Returns the decimal id if the input matches that shape,
    otherwise None.
    """
    if "." not in name:
        return None
    head, tail = name.rsplit(".", 1)
    if head != "mod_workshop_package":
        return None
    try:
        return str(int(tail, 16))
    except ValueError:
        return None
