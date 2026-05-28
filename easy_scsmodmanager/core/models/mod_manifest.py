"""Strongly-typed view of a mod's manifest.sii content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from easy_scsmodmanager.integrations.sii.parser import SiiUnit

MOD_PACKAGE_CLASS = "mod_package"


@dataclass(frozen=True)
class ModManifest:
    display_name: str
    package_version: str = ""
    author: str = ""
    categories: tuple[str, ...] = ()
    description_file: str = ""
    icon: str = ""
    compatible_versions: tuple[str, ...] = ()

    @classmethod
    def from_sii_unit(cls, unit: SiiUnit) -> ModManifest:
        if unit.unit_class != MOD_PACKAGE_CLASS:
            raise ValueError(
                f"Expected unit_class '{MOD_PACKAGE_CLASS}', got '{unit.unit_class}'"
            )
        props = unit.properties
        return cls(
            display_name=str(props.get("display_name", "")),
            package_version=str(props.get("package_version", "")),
            author=str(props.get("author", "")),
            categories=_to_tuple_of_str(props.get("category", ())),
            description_file=str(props.get("description_file", "")),
            icon=str(props.get("icon", "")),
            compatible_versions=_to_tuple_of_str(props.get("compatible_versions", ())),
        )

    @classmethod
    def from_sii_units(cls, units: Iterable[SiiUnit]) -> ModManifest:
        for unit in units:
            if unit.unit_class == MOD_PACKAGE_CLASS:
                return cls.from_sii_unit(unit)
        raise ValueError(f"No '{MOD_PACKAGE_CLASS}' unit found in manifest")


def _to_tuple_of_str(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    return ()
