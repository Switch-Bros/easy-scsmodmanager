"""Mirror the game's mod compatibility check - it never judges on its own.

Researched fact that drives the design: the game only marks a mod red because
of its ``compatible_versions[]``. No key -> treated as compatible (even if it
factually is not). A player on 1.59 who deliberately runs a 1.58 mod must not
see working mods falsely blocked.

Verified against 437 real mods: 307 declare no compatible_versions at all
(UNSPECIFIED), and the ones that do use the ``<major>.<minor>.*`` wildcard
form (e.g. ``1.59.*``). The game version comes from game.log.txt as
``1.59.1.3``; ``1.59.*`` matches it, ``1.58.*`` does not.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum


class CompatStatus(Enum):
    COMPATIBLE = "compatible"  # key present and matches
    INCOMPATIBLE = "incompatible"  # key present, none match (what the game reds)
    UNSPECIFIED = "unspecified"  # key empty/absent -> not red, treated usable
    UNKNOWN_GAME_VERSION = "unknown_game_version"  # game version not determinable


def _matches(game_segments: list[str], pattern: str) -> bool:
    """Segment-wise match. ``*`` is a wildcard for the rest; non-``*`` segments
    must equal the game's segment at the same position. A pattern shorter than
    the game version (``1.59`` vs ``1.59.1.3``) matches as a prefix."""
    for i, seg in enumerate(pattern.split(".")):
        if seg == "*":
            return True
        if i >= len(game_segments) or seg != game_segments[i]:
            return False
    return True


def compat_status(game_version: str | None, compatible_versions: Iterable[str]) -> CompatStatus:
    """The four-state compatibility verdict, mirroring the game exactly."""
    patterns = [p for p in compatible_versions if p]
    if not patterns:
        return CompatStatus.UNSPECIFIED
    if not game_version:
        return CompatStatus.UNKNOWN_GAME_VERSION
    segments = game_version.split(".")
    if any(_matches(segments, p) for p in patterns):
        return CompatStatus.COMPATIBLE
    return CompatStatus.INCOMPATIBLE
