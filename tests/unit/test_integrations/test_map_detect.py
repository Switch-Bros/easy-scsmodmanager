from easy_scsmodmanager.integrations.scs.map_detect import contains_map


def test_detects_mbd_directly_under_map():
    assert contains_map(["manifest.sii", "map/europe.mbd", "map/europe/0.base"]) is True


def test_leading_slash_and_case_tolerant():
    assert contains_map(["/MAP/Germany.MBD"]) is True


def test_mbd_outside_map_dir_does_not_count():
    assert contains_map(["def/foo.mbd", "ui/map/preview.mbd"]) is False


def test_no_map_returns_false():
    assert contains_map(["manifest.sii", "def/city.sii", "model/x.pmg"]) is False


def test_empty_returns_false():
    assert contains_map([]) is False
