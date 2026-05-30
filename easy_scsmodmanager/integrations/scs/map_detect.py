"""Detect whether an archive's file list contains a playable map.

A map mod must ship a compiled map descriptor (.mbd) directly under the
top-level map/ directory, so we key on that rather than the (often wrong)
manifest category.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_MAP_MBD = re.compile(r"^/?map/[^/]+\.mbd$", re.IGNORECASE)


def contains_map(paths: Iterable[str]) -> bool:
    """True if any path is a .mbd file directly under map/."""
    return any(_MAP_MBD.match(p) for p in paths)
