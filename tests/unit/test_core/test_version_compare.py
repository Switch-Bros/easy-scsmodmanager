from easy_scsmodmanager.core.version_compare import compare_versions


def test_lower_minor_is_less():
    assert compare_versions("2.2", "2.4") == -1


def test_numeric_not_string_compare():
    # 2.10 > 2.2 numerically (string compare would get this wrong)
    assert compare_versions("2.10", "2.2") == 1


def test_equal_versions():
    assert compare_versions("2.2", "2.2") == 0


def test_zero_padding_makes_shorter_equal():
    assert compare_versions("2.0", "2.0.0") == 0


def test_extra_patch_segment_is_greater():
    assert compare_versions("1.0.1", "1.0") == 1


def test_empty_is_not_comparable():
    assert compare_versions("", "1.0") is None


def test_non_numeric_segment_is_not_comparable():
    # real sample: "1.59.b"
    assert compare_versions("1.59.b", "1.59.1") is None


def test_prefixed_version_is_not_comparable():
    assert compare_versions("v2.4", "2.4") is None
