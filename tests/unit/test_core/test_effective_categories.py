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


def test_content_category_beats_manifest():
    assert effective_categories(
        ("other",), is_map=False, override=None, content_category="physics"
    ) == ("physics",)


def test_content_category_beats_map():
    assert effective_categories(
        ("other",), is_map=True, override=None, content_category="physics"
    ) == ("physics",)


def test_override_beats_content_category():
    assert effective_categories(
        ("sound",), is_map=False, override="ui", content_category="physics"
    ) == ("ui",)


def test_no_content_category_keeps_map():
    assert effective_categories(("other",), is_map=True, override=None, content_category=None) == (
        "map",
    )
