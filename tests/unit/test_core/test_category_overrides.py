from pathlib import Path

from easy_scsmodmanager.core.category_overrides import CategoryOverrides


def test_round_trip(tmp_path: Path):
    ov = CategoryOverrides(tmp_path / "ov.db")
    assert ov.get("donbass_map") is None
    ov.set("donbass_map", "map")
    assert ov.get("donbass_map") == "map"


def test_clear(tmp_path: Path):
    ov = CategoryOverrides(tmp_path / "ov.db")
    ov.set("x", "map")
    ov.clear("x")
    assert ov.get("x") is None
