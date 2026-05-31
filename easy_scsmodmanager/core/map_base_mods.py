"""Known "top of load order" mods that belong in the map_base block.

These (BXP/GMC map-base mods, background map, loading screen, ...) are
technically category `map` or `ui` but must load last (= top of the list).
We match an active mod's name or display name against these fragments
(case-insensitive substring), so version suffixes still match. The list is
a starting point; the user can edit it in Settings.
"""

from __future__ import annotations

DEFAULT_MAP_BASE_NAMES: tuple[str, ...] = (
    "BXPfix007",
    "ETS2 Global Background Map",
    "FullScreen Maps",
    "Loading Screen",
    "Small HUD Mirrors",
    "Tutorial Hints",
)


def is_map_base(mod_name: str, display_name: str, names: tuple[str, ...]) -> bool:
    """True if the mod's name or display name contains a known fragment."""
    haystack = f"{mod_name}\n{display_name}".lower()
    return any(frag.lower() in haystack for frag in names if frag)
