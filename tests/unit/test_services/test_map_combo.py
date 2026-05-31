from __future__ import annotations

import json

import pytest

from easy_scsmodmanager.services.map_combo import (
    FORMAT_ID,
    MapComboEntry,
    MapComboError,
    missing,
    outdated,
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


# --- v2: package_version round-trip + outdated check ---------------------


def test_v2_round_trip_keeps_package_version() -> None:
    combo = [MapComboEntry(name="rusmap", display_name="RusMap", package_version="2.4")]
    assert parse(serialize(combo)) == combo


def test_v1_file_loads_with_empty_version() -> None:
    # a v1 file has no per-entry package_version
    v1 = json.dumps(
        {"format": FORMAT_ID, "version": 1, "maps": [{"name": "rusmap", "display_name": "RusMap"}]}
    )
    parsed = parse(v1)
    assert parsed[0].package_version == ""


def test_outdated_flags_newer_combo_version() -> None:
    combo = [MapComboEntry(name="rusmap", display_name="RusMap", package_version="2.4")]
    result = outdated(combo, {"rusmap": "2.2"})
    assert result == [(combo[0], "2.2")]


def test_outdated_ignores_equal_or_newer_local() -> None:
    combo = [MapComboEntry(name="rusmap", display_name="RusMap", package_version="2.2")]
    assert outdated(combo, {"rusmap": "2.2"}) == []
    assert outdated(combo, {"rusmap": "2.4"}) == []


def test_outdated_skips_unparseable_versions() -> None:
    combo = [MapComboEntry(name="m", display_name="M", package_version="1.59.b")]
    assert outdated(combo, {"m": "1.59.1"}) == []


def test_outdated_skips_missing_mods() -> None:
    combo = [MapComboEntry(name="gone", display_name="Gone", package_version="2.4")]
    assert outdated(combo, {}) == []
