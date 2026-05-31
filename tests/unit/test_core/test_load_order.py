from easy_scsmodmanager.core.load_order import (
    GROUPS,
    MAP_BASE,
    group_index_for_token,
    group_label_keys,
)


def test_groups_ordered_and_map_base_first():
    assert GROUPS[0].id == MAP_BASE
    ids = [g.id for g in GROUPS]
    assert ids == [
        "map_base",
        "graphics_weather",
        "sound",
        "physics",
        "ui_other",
        "tuning_interior",
        "ai_traffic",
        "cargo",
        "paint_jobs",
        "trailers",
        "trucks",
        "maps",
    ]


def test_token_maps_to_group_index():
    trucks = next(i for i, g in enumerate(GROUPS) if g.id == "trucks")
    assert group_index_for_token("truck") == trucks
    assert group_index_for_token("graphics") == group_index_for_token("weather_setup")
    assert group_index_for_token("ui") == group_index_for_token("other")
    assert group_index_for_token("map") == len(GROUPS) - 1


def test_unknown_token_maps_to_ui_other():
    ui_other = next(i for i, g in enumerate(GROUPS) if g.id == "ui_other")
    assert group_index_for_token("models") == ui_other
    assert group_index_for_token("bogus") == ui_other


def test_label_keys_present_for_every_group():
    for g in GROUPS:
        assert g.label_keys


def test_group_label_keys_lookup():
    assert group_label_keys("trucks") == ("load_order.trucks",)
    assert len(group_label_keys("map_base")) == 3
