from __future__ import annotations

import pytest

from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.sii.parser import SiiUnit


def _unit(props: dict) -> SiiUnit:
    return SiiUnit(unit_class="mod_package", unit_name=".package", properties=props)


def test_from_sii_extracts_known_fields() -> None:
    unit = _unit({
        "package_version": "1.2.3",
        "display_name": "Real Train Sounds",
        "author": "Cip",
        "category": ["sound", "ai_traffic"],
        "description_file": "description.txt",
        "icon": "icon.jpg",
        "compatible_versions": ["1.59.*", "1.60.*"],
    })

    manifest = ModManifest.from_sii_unit(unit)

    assert manifest.package_version == "1.2.3"
    assert manifest.display_name == "Real Train Sounds"
    assert manifest.author == "Cip"
    assert manifest.categories == ("sound", "ai_traffic")
    assert manifest.description_file == "description.txt"
    assert manifest.icon == "icon.jpg"
    assert manifest.compatible_versions == ("1.59.*", "1.60.*")


def test_from_sii_unit_provides_defaults_for_missing_optional_fields() -> None:
    unit = _unit({"display_name": "Minimal Mod"})

    manifest = ModManifest.from_sii_unit(unit)

    assert manifest.display_name == "Minimal Mod"
    assert manifest.package_version == ""
    assert manifest.author == ""
    assert manifest.categories == ()
    assert manifest.description_file == ""
    assert manifest.icon == ""
    assert manifest.compatible_versions == ()


def test_from_sii_unit_normalises_single_category_to_tuple() -> None:
    unit = _unit({"display_name": "x", "category": ["sound"]})

    manifest = ModManifest.from_sii_unit(unit)

    assert manifest.categories == ("sound",)


def test_from_sii_unit_rejects_non_mod_package_class() -> None:
    unit = SiiUnit(unit_class="other", unit_name=".other", properties={"display_name": "x"})

    with pytest.raises(ValueError):
        ModManifest.from_sii_unit(unit)


def test_from_sii_units_finds_mod_package_among_many() -> None:
    units = [
        SiiUnit(unit_class="foo", unit_name=".foo", properties={}),
        _unit({"display_name": "Pick Me"}),
        SiiUnit(unit_class="bar", unit_name=".bar", properties={}),
    ]

    manifest = ModManifest.from_sii_units(units)

    assert manifest.display_name == "Pick Me"


def test_from_sii_units_raises_when_no_mod_package() -> None:
    units = [SiiUnit(unit_class="something_else", unit_name=".x", properties={})]

    with pytest.raises(ValueError, match="mod_package"):
        ModManifest.from_sii_units(units)
