from easy_scsmodmanager.services.conflict_detect import find_conflicts


def test_shared_def_is_a_conflict():
    result = find_conflicts(
        {
            "map_a": ["def/climate.sii", "def/city/a.sii"],
            "map_b": ["def/climate.sii", "def/city/b.sii"],
        }
    )
    assert set(result) == {"map_a", "map_b"}
    assert result["map_a"][0].other == "map_b"
    assert result["map_a"][0].shared == ("def/climate.sii",)


def test_disjoint_defs_no_conflict():
    result = find_conflicts(
        {
            "truck_a": ["def/vehicle/truck/a.sii"],
            "truck_b": ["def/vehicle/truck/b.sii"],
        }
    )
    assert result == {}


def test_no_defs_no_conflict():
    # a sound/graphics mod with no def files cannot conflict here
    assert find_conflicts({"sound_a": [], "gfx_b": []}) == {}


def test_generic_override_shared_by_many_is_dropped():
    # def/economy.sii owned by 10 mods is a generic override, not a real hint
    many = {f"map_{i}": ["def/economy.sii"] for i in range(10)}
    assert find_conflicts(many) == {}


def test_specific_overlap_kept_even_with_a_generic_path():
    mods = {
        "a": ["def/economy.sii", "def/special.sii"],
        "b": ["def/economy.sii", "def/special.sii"],
        **{f"filler_{i}": ["def/economy.sii"] for i in range(9)},
    }
    result = find_conflicts(mods)
    # economy.sii is generic (11 owners) -> dropped; special.sii (2) -> kept
    assert result["a"][0].other == "b"
    assert result["a"][0].shared == ("def/special.sii",)
    assert "filler_0" not in result


def test_conflict_is_symmetric():
    result = find_conflicts({"a": ["def/x.sii"], "b": ["def/x.sii"]})
    assert result["a"][0].other == "b"
    assert result["b"][0].other == "a"
