from easy_scsmodmanager.core.map_base_mods import DEFAULT_MAP_BASE_NAMES, is_map_base


def test_matches_fragment_case_insensitive_with_version():
    assert is_map_base("BXPfix007159_1", "", ("BXPfix007",)) is True
    assert (
        is_map_base("whatever", "ETS2 GLOBAL BACKGROUND MAP", ("ETS2 Global Background Map",))
        is True
    )


def test_no_match():
    assert is_map_base("RusMap_Def", "RusMap", DEFAULT_MAP_BASE_NAMES) is False


def test_empty_fragments_ignored():
    assert is_map_base("anything", "", ("",)) is False
