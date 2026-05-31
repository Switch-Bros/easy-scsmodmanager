"""Tests for default_group_overrides_path and group overrides round-trip."""

from pathlib import Path

from easy_scsmodmanager.core.category_overrides import (
    CategoryOverrides,
    default_group_overrides_path,
)


def test_default_group_overrides_path_has_correct_name() -> None:
    path = default_group_overrides_path()
    assert path.name == "group_overrides.db"
    assert "easy-scsmodmanager" in str(path)


def test_group_overrides_round_trip(tmp_path: Path) -> None:
    ov = CategoryOverrides(tmp_path / "group_overrides.db")
    assert ov.get("bxpfix007") is None
    ov.set("bxpfix007", "map_base")
    assert ov.get("bxpfix007") == "map_base"
    ov.close()


def test_group_overrides_clear(tmp_path: Path) -> None:
    ov = CategoryOverrides(tmp_path / "group_overrides.db")
    ov.set("somemod", "trucks")
    ov.clear("somemod")
    assert ov.get("somemod") is None
    ov.close()
