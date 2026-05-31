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


def find_conflicts(active: Mapping[str, Iterable[str]]) -> dict[str, list[ModConflict]]:
    """Map each mod_name to the other active mods it shares a def file with.

    ``active`` maps mod_name -> its def file paths. The result only contains
    mods that actually conflict; a mod with no conflicts is absent.
    """
    owners: dict[str, list[str]] = defaultdict(list)
    for name, defs in active.items():
        for path in set(defs):
            owners[path].append(name)

    pair_shared: dict[tuple[str, str], set[str]] = defaultdict(set)
    dropped_generic = 0
    for path, names in owners.items():
        if len(names) < 2:
            continue
        if len(names) > _GENERIC_OWNER_LIMIT:
            dropped_generic += 1
            continue
        for a, b in combinations(sorted(names), 2):
            pair_shared[(a, b)].add(path)

    if dropped_generic:
        log.debug(
            "conflict scan skipped %d generic def paths (>%d owners)",
            dropped_generic,
            _GENERIC_OWNER_LIMIT,
        )

    result: dict[str, list[ModConflict]] = defaultdict(list)
    for (a, b), shared in pair_shared.items():
        files = tuple(sorted(shared)[:_MAX_SHARED_SHOWN])
        result[a].append(ModConflict(other=b, shared=files))
        result[b].append(ModConflict(other=a, shared=files))
    return dict(result)
