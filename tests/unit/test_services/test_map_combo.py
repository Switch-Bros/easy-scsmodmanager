from __future__ import annotations

import pytest

from easy_scsmodmanager.services.map_combo import (
    MapComboEntry,
    MapComboError,
    missing,
    parse,
    reorder,
    serialize,
)
from easy_scsmodmanager.services.profile_reader import ActiveMod


def _entries(*names: str) -> list[MapComboEntry]:
    return [MapComboEntry(name=n, display_name=n.title()) for n in names]


def test_round_trip_preserves_order_and_names() -> None:
    combo = _entries("donbass_map", "promods", "rusmap")
    parsed = parse(serialize(combo))
    assert parsed == combo


def test_parse_rejects_foreign_json() -> None:
    with pytest.raises(MapComboError):
        parse('{"format": "something-else", "maps": []}')


def test_parse_rejects_garbage() -> None:
    with pytest.raises(MapComboError):
        parse("not json at all {")


def test_missing_lists_only_absent_maps_in_combo_order() -> None:
    combo = _entries("donbass_map", "promods", "rusmap")
    installed = {"promods", "southern_region"}
    gaps = missing(combo, installed)
    assert [e.name for e in gaps] == ["donbass_map", "rusmap"]


def test_missing_empty_when_all_present() -> None:
    combo = _entries("a", "b")
    assert missing(combo, {"a", "b", "c"}) == []


def test_reorder_follows_combo_order() -> None:
    block = [
        ActiveMod(name="rusmap", display_name="RusMap"),
        ActiveMod(name="donbass_map", display_name="Donbass"),
        ActiveMod(name="promods", display_name="ProMods"),
    ]
    combo = _entries("donbass_map", "promods", "rusmap")
    result = reorder(block, combo)
    assert [m.name for m in result] == ["donbass_map", "promods", "rusmap"]


def test_reorder_keeps_local_extra_maps_after_combo() -> None:
    block = [
        ActiveMod(name="local_only", display_name="Local"),
        ActiveMod(name="promods", display_name="ProMods"),
        ActiveMod(name="donbass_map", display_name="Donbass"),
    ]
    combo = _entries("donbass_map", "promods")
    result = reorder(block, combo)
    # combo maps first in combo order, the unmentioned local map trails
    assert [m.name for m in result] == ["donbass_map", "promods", "local_only"]
