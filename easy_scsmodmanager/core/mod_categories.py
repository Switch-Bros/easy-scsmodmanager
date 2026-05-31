"""Canonical ETS2/ATS mod categories.

The in-game mod manager only knows a fixed set of category tokens. They live
in ``locale.scs/locale/<lang>/localization.sui`` under the keys
``mod_category_*``; the names shown to the player are the translations of
those keys. A mod's ``manifest.sii`` may carry any free-form ``category[]``
string, but the game files it under one of these tokens - or, when nothing
matches, under ``other``.

We mirror that exactly: a fixed, game-ordered list, strict token matching,
unknown tags collapse to ``other``.
"""

from __future__ import annotations

from collections.abc import Iterable

OTHER = "other"

# Fixed order as the in-game mod manager presents them. Keep in sync with the
# ``category.*`` keys in resources/i18n/*.json.
OFFICIAL_CATEGORIES: tuple[str, ...] = (
    "truck",
    "trailer",
    "interior",
    "tuning_parts",
    "ai_traffic",
    "sound",
    "paint_job",
    "cargo_pack",
    "map",
    "ui",
    "weather_setup",
    "physics",
    "graphics",
    "models",
    "movers",
    "walkers",
    "prefabs",
    OTHER,
)

_KNOWN = frozenset(OFFICIAL_CATEGORIES)


def i18n_key(token: str) -> str:
    """Translation key for a category token, e.g. ``category.truck``."""
    return f"category.{token}"


def canonical_categories(raw: Iterable[str]) -> tuple[str, ...]:
    """Map a mod's raw ``category[]`` tags onto official tokens.

    Strict matching: a tag only counts when it equals an official token.
    Anything else - mod-specific tags (``donbass_map``), plurals (``maps``),
    placeholders (``_``), empties - collapses to ``other``. Order follows the
    first appearance of each token in the input; duplicates drop out. A mod
    with no usable tag lands in ``other``.
    """
    result: list[str] = []
    for tag in raw:
        token = tag if tag in _KNOWN else OTHER
        if token not in result:
            result.append(token)
    return tuple(result) if result else (OTHER,)


def effective_categories(
    manifest_categories: tuple[str, ...],
    *,
    is_map: bool,
    override: str | None,
) -> tuple[str, ...]:
    """Trustworthy category: override > map-by-content > manifest."""
    if override is not None:
        return (override,) if override in _KNOWN else (OTHER,)
    if is_map:
        return ("map",)
    return canonical_categories(manifest_categories)
