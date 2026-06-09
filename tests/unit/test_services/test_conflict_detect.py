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


def test_shared_directory_entries_are_not_a_conflict():
    # forum #33: two zip mods with the same folder structure but disjoint files
    result = find_conflicts(
        {
            "mod_a": ["def/", "def/vehicle/", "def/vehicle/a.sii"],
            "mod_b": ["def/", "def/vehicle/", "def/vehicle/b.sii"],
        }
    )
    assert result == {}  # only the directory entries overlap


def test_shared_directory_plus_shared_file_still_conflicts():
    result = find_conflicts(
        {
            "mod_a": ["def/", "def/vehicle/", "def/vehicle/shared.sii"],
            "mod_b": ["def/", "def/vehicle/", "def/vehicle/shared.sii"],
        }
    )
    assert set(result) == {"mod_a", "mod_b"}
    assert result["mod_a"][0].shared == ("def/vehicle/shared.sii",)


# --- severity (analyze_overrides) ----------------------------------------- #

from easy_scsmodmanager.services.conflict_detect import Severity, analyze_overrides  # noqa: E402


def test_direction_rule_higher_position_wins():
    # THE foundation: the mod visually higher (greater position) overrides the
    # one below. Invert this and red/yellow are mirror-imaged.
    ov = analyze_overrides(
        {"low": ["def/x.sii"], "high": ["def/x.sii"]},
        {"low": 0, "high": 1},
    )
    assert ov["low"].severity is Severity.FULL  # the lower one loses
    assert "high" not in ov  # the winner gets no mark
    assert ov["low"].lost == (("def/x.sii", "high"),)


def test_severity_is_one_value_per_mod():
    # M wins file1 against X (below), loses file2 to Y (above) -> exactly PARTIAL
    active = {
        "M": ["def/1.sii", "def/2.sii"],
        "X": ["def/1.sii"],
        "Y": ["def/2.sii"],
    }
    positions = {"X": 0, "M": 1, "Y": 2}
    ov = analyze_overrides(active, positions)

    assert ov["M"].severity is Severity.PARTIAL
    assert ov["M"].lost == (("def/2.sii", "Y"),)
    assert ov["X"].severity is Severity.FULL
    assert "Y" not in ov  # Y wins everything


def test_wins_all_gets_no_mark_loses_all_is_full():
    ov = analyze_overrides(
        {"top": ["def/a.sii", "def/b.sii"], "bot": ["def/a.sii", "def/b.sii"]},
        {"bot": 0, "top": 1},
    )
    assert "top" not in ov
    assert ov["bot"].severity is Severity.FULL


def test_generic_paths_not_counted_in_severity():
    # a path owned by >8 mods is generic and must not push anyone to red
    names = [f"m{i}" for i in range(9)]
    active = {n: ["def/generic.sii"] for n in names}
    positions = {n: i for i, n in enumerate(names)}
    assert analyze_overrides(active, positions) == {}


def test_llbbc_43_two_base_packaged_mods_conflict():
    # forum #43: both mods carry the same file under base/def/ - invisible before
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    _, defs_a = _map_and_defs(["base/def/vehicle/shared.sii"])
    _, defs_b = _map_and_defs(["base/def/vehicle/shared.sii"])
    result = find_conflicts({"mod_a": defs_a, "mod_b": defs_b})
    assert set(result) == {"mod_a", "mod_b"}
    assert result["mod_a"][0].shared == ("def/vehicle/shared.sii",)


def test_base_packaged_physics_conflicts_and_classifies():
    # covers #42 IF that mod is base/-packaged: shared physics def + physics tag
    from easy_scsmodmanager.integrations.scs.content_category import content_category
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    listing = ["base/def/vehicle/physics/physics.sii"]
    _, defs_a = _map_and_defs(listing)
    _, defs_b = _map_and_defs(listing)
    result = find_conflicts({"a": defs_a, "b": defs_b})
    assert set(result) == {"a", "b"}
    assert content_category(defs_a) == "physics"


# --- §B frequent tier (>8 owners) ---------------------------------------- #

from easy_scsmodmanager.services.conflict_detect import FrequentShare, analyze  # noqa: E402


def _many_sharers(n: int, path: str) -> dict[str, list[str]]:
    return {f"m{i}": [path] for i in range(n)}


def test_analyze_splits_conflict_and_frequent_tiers():
    # 2 mods share def/x -> conflict; 9 mods share def/y -> frequent (>8)
    active = {"a": ["def/x.sii"], "b": ["def/x.sii"]}
    active.update({f"m{i}": ["def/y.sii"] for i in range(9)})
    positions = {name: i for i, name in enumerate(active)}
    overrides, frequent = analyze(active, positions)

    assert set(overrides) <= {"a", "b"}  # only the 2-mod overlap is a conflict
    assert all(name in frequent for name in (f"m{i}" for i in range(9)))
    # frequent carries the owner count, no names
    share = frequent["m0"]
    assert isinstance(share, FrequentShare)
    assert share.files == (("def/y.sii", 9),)


def test_frequent_does_not_create_overrides():
    active = _many_sharers(10, "def/physics/physics.sii")
    positions = {name: i for i, name in enumerate(active)}
    overrides, frequent = analyze(active, positions)
    assert overrides == {}  # >8 is never a red/yellow conflict
    assert len(frequent) == 10


def test_eight_owners_is_still_a_conflict_not_frequent():
    active = _many_sharers(8, "def/x.sii")
    positions = {name: i for i, name in enumerate(active)}
    overrides, frequent = analyze(active, positions)
    assert frequent == {}  # exactly 8 stays in the conflict tier
    assert overrides  # the lower 7 lose to the top one
