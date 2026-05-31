"""Content-based coarse category from a mod's def file list.

Manifests are often mislabelled, so for the few RELIABLE signals we trust the
archive content over the manifest. Verified against 437 real mods: only map
(handled separately via ``is_map``) and physics are clean enough to trust.

Truck, trailer, sound and AI deliberately return no judgement: their file-list
signals overlap too much to be trustworthy. Maps carry trailer- and AI-defs;
sound, interior, tuning and physics mods all overwrite ``def/vehicle/truck/``
because they *modify* trucks. Judging those from paths alone mislabels more
than it fixes, so we leave them to the manifest (None = no confident signal).
"""

from __future__ import annotations

from collections.abc import Iterable

# the vehicle physics override - present in physics mods, essentially nowhere
# else (4/4 physics mods carried it, near-zero noise in the sample).
_PHYSICS_PREFIX = "def/vehicle/physics"


def content_category(def_files: Iterable[str]) -> str | None:
    """A trustworthy category token from the def file list, or None.

    Returns ``"physics"`` when the archive carries the vehicle physics
    override. None means "no confident content signal" - the caller keeps the
    manifest (and the separate map-by-content check).
    """
    for path in def_files:
        if path.lstrip("/").startswith(_PHYSICS_PREFIX):
            return "physics"
    return None
