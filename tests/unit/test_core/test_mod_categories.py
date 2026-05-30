from __future__ import annotations

from easy_scsmodmanager.core.mod_categories import (
    OFFICIAL_CATEGORIES,
    OTHER,
    canonical_categories,
    i18n_key,
)


def test_official_list_is_fixed_and_ordered() -> None:
    # 18 categories, game order, "other" last.
    assert len(OFFICIAL_CATEGORIES) == 18
    assert OFFICIAL_CATEGORIES[0] == "truck"
    assert OFFICIAL_CATEGORIES[-1] == OTHER
    assert len(set(OFFICIAL_CATEGORIES)) == len(OFFICIAL_CATEGORIES)


def test_exact_tokens_pass_through() -> None:
    assert canonical_categories(["truck"]) == ("truck",)
    assert canonical_categories(["map"]) == ("map",)


def test_unknown_tags_collapse_to_other() -> None:
    # Mod-specific tag, plural and placeholder all fail the strict match.
    assert canonical_categories(["donbass_map"]) == (OTHER,)
    assert canonical_categories(["maps"]) == (OTHER,)
    assert canonical_categories(["economy"]) == (OTHER,)
    assert canonical_categories(["_"]) == (OTHER,)


def test_empty_input_lands_in_other() -> None:
    assert canonical_categories([]) == (OTHER,)


def test_multiple_categories_keep_input_order() -> None:
    assert canonical_categories(["tuning_parts", "interior"]) == (
        "tuning_parts",
        "interior",
    )


def test_duplicates_are_dropped() -> None:
    assert canonical_categories(["map", "map", "maps"]) == ("map", OTHER)


def test_i18n_key_format() -> None:
    assert i18n_key("truck") == "category.truck"
    assert i18n_key(OTHER) == "category.other"
