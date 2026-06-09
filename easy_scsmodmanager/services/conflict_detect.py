"""Detect mods that overwrite the same def file.

Two active mods conflict when their archives both carry the same ``def/...``
path: whichever sits higher in the load order wins, the other's version is
shadowed. This is a HINT, never an error - for maps an overlap is often
intentional and the load order resolves it. We only look at ``def/`` paths
(manifest/icon overlap is normal and ignored - those are not in def_files); the
scanner has already normalised the 1.48 ``base/`` package layer, so a
``base/def/...`` mod is compared as ``def/...`` here.

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


@dataclass(frozen=True)
class FrequentShare:
    # def files this mod shares with MORE than the generic limit of mods - a
    # usually-intended overlap (physics, climate ...), shown as neutral info,
    # never as a conflict. Each entry is (file, total owner count). Sorted.
    files: tuple[tuple[str, int], ...]


def _partition_owners(
    active: Mapping[str, Iterable[str]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Split shared def paths into (conflicting 2..LIMIT, frequent >LIMIT).

    One pass over the inverted index. The conflicting set drives red/yellow
    severity; the frequent set drives the neutral grey "frequently shared" tier.
    Directory entries are dropped (an old-cache artefact, never a real overlap).
    """
    owners: dict[str, list[str]] = defaultdict(list)
    for name, defs in active.items():
        for path in set(defs):
            if path.endswith("/"):
                continue  # directory entry from an old cache - never a conflict
            owners[path].append(name)

    shared: dict[str, list[str]] = {}
    frequent: dict[str, list[str]] = {}
    for path, names in owners.items():
        if len(names) < 2:
            continue
        if len(names) > _GENERIC_OWNER_LIMIT:
            frequent[path] = names
        else:
            shared[path] = names

    if frequent:
        log.debug(
            "conflict scan: %d def paths shared by >%d mods (frequent tier)",
            len(frequent),
            _GENERIC_OWNER_LIMIT,
        )
    return shared, frequent


def find_conflicts(active: Mapping[str, Iterable[str]]) -> dict[str, list[ModConflict]]:
    """Map each mod_name to the other active mods it shares a def file with.

    ``active`` maps mod_name -> its def file paths. The result only contains
    mods that actually conflict; a mod with no conflicts is absent.
    """
    pair_shared: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path, names in _partition_owners(active)[0].items():
        for a, b in combinations(sorted(names), 2):
            pair_shared[(a, b)].add(path)

    result: dict[str, list[ModConflict]] = defaultdict(list)
    for (a, b), shared in pair_shared.items():
        files = tuple(sorted(shared)[:_MAX_SHARED_SHOWN])
        result[a].append(ModConflict(other=b, shared=files))
        result[b].append(ModConflict(other=a, shared=files))
    return dict(result)


def _overrides_from_shared(
    shared: dict[str, list[str]], positions: Mapping[str, int]
) -> dict[str, ModOverride]:
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


def _frequent_shares(frequent: dict[str, list[str]]) -> dict[str, FrequentShare]:
    by_mod: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path, names in frequent.items():
        for name in names:
            by_mod[name].append((path, len(names)))
    return {name: FrequentShare(tuple(sorted(files))) for name, files in by_mod.items()}


def analyze_overrides(
    active: Mapping[str, Iterable[str]],
    positions: Mapping[str, int],
) -> dict[str, ModOverride]:
    """Per-mod override severity, keyed by mod_name.

    ``positions`` maps mod_name -> load-order index (higher = visually higher =
    wins). For each shared def path the top owner (highest position) wins; every
    other owner loses that path to it. A mod that loses none is absent (it is
    the winner, no glyph); loses all -> FULL; loses some -> PARTIAL.
    """
    return _overrides_from_shared(_partition_owners(active)[0], positions)


def analyze(
    active: Mapping[str, Iterable[str]],
    positions: Mapping[str, int],
) -> tuple[dict[str, ModOverride], dict[str, FrequentShare]]:
    """Both tiers in ONE pass: (per-mod override severity, per-mod frequent shares).

    The presenter uses this so the 2..8 conflict tier and the >8 frequent tier
    are derived together. A mod can be in both (it has a real conflict AND also
    shares some generic files); precedence is resolved at the glyph.
    """
    shared, frequent = _partition_owners(active)
    return _overrides_from_shared(shared, positions), _frequent_shares(frequent)
