from easy_scsmodmanager.core.version_compat import CompatStatus, compat_status


def test_exact_match_is_compatible():
    assert compat_status("1.59.1.3", ["1.59.1.3"]) is CompatStatus.COMPATIBLE


def test_wildcard_matches_current_game():
    assert compat_status("1.59.1.3", ["1.59.*"]) is CompatStatus.COMPATIBLE


def test_wildcard_for_other_minor_is_incompatible():
    assert compat_status("1.59.1.3", ["1.58.*"]) is CompatStatus.INCOMPATIBLE


def test_one_of_several_matching_is_compatible():
    assert compat_status("1.59.1.3", ["1.58.*", "1.59.*"]) is CompatStatus.COMPATIBLE


def test_empty_is_unspecified_not_incompatible():
    # the central fallstrick: no key must never read as INCOMPATIBLE
    assert compat_status("1.59.1.3", []) is CompatStatus.UNSPECIFIED


def test_blank_entries_count_as_empty():
    assert compat_status("1.59.1.3", ["", ""]) is CompatStatus.UNSPECIFIED


def test_unknown_game_version_never_reds():
    assert compat_status(None, ["1.58.*"]) is CompatStatus.UNKNOWN_GAME_VERSION


def test_shorter_pattern_matches_as_prefix():
    assert compat_status("1.59.1.3", ["1.59"]) is CompatStatus.COMPATIBLE


def test_prefix_does_not_match_different_minor():
    # 1.5 must not match 1.59 segment-wise (not a string prefix)
    assert compat_status("1.59.1.3", ["1.5"]) is CompatStatus.INCOMPATIBLE
