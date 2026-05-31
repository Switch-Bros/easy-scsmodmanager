from easy_scsmodmanager.core.mod_categories import effective_categories


def test_override_wins():
    assert effective_categories(("sound",), is_map=True, override="ui") == ("ui",)


def test_is_map_beats_manifest():
    assert effective_categories(("other",), is_map=True, override=None) == ("map",)


def test_falls_back_to_manifest():
    assert effective_categories(("sound",), is_map=False, override=None) == ("sound",)


def test_empty_manifest_is_other():
    assert effective_categories((), is_map=False, override=None) == ("other",)


def test_unknown_override_falls_back_to_other():
    assert effective_categories(("sound",), is_map=False, override="bogus") == ("other",)
