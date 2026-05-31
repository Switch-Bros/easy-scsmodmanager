from easy_scsmodmanager.integrations.scs.content_category import content_category


def test_physics_def_yields_physics():
    assert content_category(["def/vehicle/physics.sii", "def/vehicle/truck/x.sii"]) == "physics"


def test_physics_prefix_variants_yield_physics():
    assert content_category(["def/vehicle/physics_interior_camera.sii"]) == "physics"


def test_leading_slash_tolerated():
    assert content_category(["/def/vehicle/physics.sii"]) == "physics"


def test_truck_defs_alone_give_no_judgement():
    # truck/sound/interior all carry def/vehicle/truck - too ambiguous, so None
    assert content_category(["def/vehicle/truck/scania/data.sii"]) is None


def test_empty_is_none():
    assert content_category([]) is None
