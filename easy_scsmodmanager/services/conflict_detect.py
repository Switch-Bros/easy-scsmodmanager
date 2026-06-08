"""Detect mods that overwrite the same def file.

Two active mods conflict when their archives both carry the same ``def/...``
path: whichever sits higher in the load order wins, the other's version is
shadowed. This is a HINT, never an error - for maps an overlap is often
intentional and the load order resolves it. We only look at ``def/`` paths
(manifest/icon overlap is normal and ignored - those are not in def_files).

Pure set logic over the already-cached def file lists; no archive I/O here.
The detection uses an inverted index (def path -> owners) so it scales with
the number of shared files, not the square of the mod count.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from itertools import combinations

log = logging.getLogger(__name__)

# A def path owned by more than this many active mods is a generic override
# (climate, economy, traffic rules ...) that nearly every map touches. Pairing
# all of them would drown the real hints in noise and blow up combinatorially,
# so such paths are dropped from conflict reporting (logged, never silent).
_GENERIC_OWNER_LIMIT = 8

# Cap the shared-file list kept per pair so a tooltip stays readable.
_MAX_SHARED_SHOWN = 20


@dataclass(frozen=True)
class ModConflict:
    other: str  # mod_name of the conflicting mod
    shared: tuple[str, ...]  # shared def paths (capped for display)


class Severity(Enum):
    PARTIAL = "partial"  # M wins some shared files, loses others
    FULL = "full"  # M loses all its shared files - effectively dead


@dataclass(frozen=True)
class ModOverride:
    severity: Severity
    # the files this mod loses, each with the mod that wins it (the top owner
    # above it). Sorted; powers both the glyph and the tooltip.
    lost: tuple[tuple[str, str], ...]


def _shared_owners(active: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
    """path -> owning mod names, for paths shared by 2..LIMIT mods.

    The single place the directory-entry and generic-path (>8 owners) filters
    live, so conflict pairing AND severity read the same set (no double filter).
    """
    owners: dict[str, list[str]] = defaultdict(list)
    for name, defs in active.items():
        for path in set(defs):
            if path.endswith("/"):
                continue  # directory entry from an old cache - never a conflict
            owners[path].append(name)

    shared: dict[str, list[str]] = {}
    dropped_generic = 0
    for path, names in owners.items():
        if len(names) < 2:
            continue
        if len(names) > _GENERIC_OWNER_LIMIT:
            dropped_generic += 1
            continue
        shared[path] = names

    if dropped_generic:
        log.debug(
            "conflict scan skipped %d generic def paths (>%d owners)",
            dropped_generic,
            _GENERIC_OWNER_LIMIT,
        )
    return shared


def find_conflicts(active: Mapping[str, Iterable[str]]) -> dict[str, list[ModConflict]]:
    """Map each mod_name to the other active mods it shares a def file with.

    ``active`` maps mod_name -> its def file paths. The result only contains
    mods that actually conflict; a mod with no conflicts is absent.
    """
    pair_shared: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path, names in _shared_owners(active).items():
        for a, b in combinations(sorted(names), 2):
            pair_shared[(a, b)].add(path)

    result: dict[str, list[ModConflict]] = defaultdict(list)
    for (a, b), shared in pair_shared.items():
        files = tuple(sorted(shared)[:_MAX_SHARED_SHOWN])
        result[a].append(ModConflict(other=b, shared=files))
        result[b].append(ModConflict(other=a, shared=files))
    return dict(result)


def analyze_overrides(
    active: Mapping[str, Iterable[str]],
    positions: Mapping[str, int],
) -> dict[str, ModOverride]:
    """Per-mod override severity, keyed by mod_name.

    ``positions`` maps mod_name -> load-order index (higher = visually higher =
    wins). For each shared def path the top owner (highest position) wins; every
    other owner loses that path to it. A mod that loses none is absent (it is
    the winner, no glyph); loses all -> FULL; loses some -> PARTIAL. Only the
    non-generic shared paths count, from the same _shared_owners set.
    """
    shared = _shared_owners(active)
    top_of: dict[str, str] = {}
    by_mod: dict[str, list[str]] = defaultdict(list)
    for path, names in shared.items():
        top_of[path] = max(names, key=lambda n: positions.get(n, -1))
        for name in names:
            by_mod[name].append(path)

    result: dict[str, ModOverride] = {}
    for name, paths in by_mod.items():
        lost = sorted((p, top_of[p]) for p in paths if top_of[p] != name)
        if not lost:
            continue  # wins all of its shared files - no mark
        severity = Severity.FULL if len(lost) == len(paths) else Severity.PARTIAL
        result[name] = ModOverride(severity=severity, lost=tuple(lost))
    return result
