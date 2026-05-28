"""Reads ETS2 / ATS user profiles from disk.

A profile lives either in ``Documents/<game>/profiles/<hex>/`` (local
only) or in ``Documents/<game>/steam_profiles/<hex>/`` (Steam Cloud
mirror). The directory name is the profile's display name encoded as
UTF-8 hex. The actual ``profile.sii`` may be plaintext (SiiN header)
or ScsC-encrypted - this module handles both transparently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from easy_scsmodmanager.core.game_paths import GameInstall
from easy_scsmodmanager.integrations.sii.crypto import decrypt_scsc, is_scsc
from easy_scsmodmanager.integrations.sii.parser import SiiUnit, parse_sii

PROFILE_UNIT_CLASS = "user_profile"
PROFILE_DIRECTORY_NAMES = ("profiles", "steam_profiles")
PROFILE_FILE_NAME = "profile.sii"


@dataclass(frozen=True)
class ActiveMod:
    name: str
    display_name: str

    @classmethod
    def parse(cls, raw: str) -> ActiveMod:
        # active_mods entries are stored as "<mod_name>|<display name>".
        # Display names may contain pipes themselves so we only split on
        # the first one.
        if "|" not in raw:
            return cls(name=raw, display_name="")
        name, display = raw.split("|", 1)
        return cls(name=name, display_name=display)


@dataclass(frozen=True)
class Profile:
    dir_name: str
    profile_name: str
    active_mods: tuple[ActiveMod, ...] = field(default_factory=tuple)

    @classmethod
    def from_sii_units(cls, units: Iterable[SiiUnit], dir_name: str) -> Profile:
        for unit in units:
            if unit.unit_class == PROFILE_UNIT_CLASS:
                return cls._from_unit(unit, dir_name)
        raise ValueError(f"No '{PROFILE_UNIT_CLASS}' unit found in profile")

    @classmethod
    def _from_unit(cls, unit: SiiUnit, dir_name: str) -> Profile:
        props = unit.properties
        profile_name = str(props.get("profile_name", dir_name))
        raw_mods = props.get("active_mods", [])
        # active_mods can be the count scalar if there are zero entries.
        if not isinstance(raw_mods, list):
            raw_mods = []
        return cls(
            dir_name=dir_name,
            profile_name=profile_name,
            active_mods=tuple(ActiveMod.parse(str(entry)) for entry in raw_mods),
        )


def decode_profile_dir_name(hex_name: str) -> str:
    """SCS encodes the profile display name as hex(utf-8). Falls back to
    the raw string if it does not decode."""
    try:
        return bytes.fromhex(hex_name).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return hex_name


def read_profile(profile_sii_path: Path) -> Profile:
    data = profile_sii_path.read_bytes()
    text = decrypt_scsc(data).decode("utf-8", errors="replace") if is_scsc(data) else data.decode(
        "utf-8", errors="replace"
    )
    units = parse_sii(text)
    return Profile.from_sii_units(units, dir_name=decode_profile_dir_name(profile_sii_path.parent.name))


def discover_profiles(install: GameInstall) -> list[Path]:
    """Returns every profile.sii under the install's profile directories.

    Looks in both ``profiles/`` (local-only) and ``steam_profiles/``
    (Steam Cloud mirror). Backup directories like ``steam_profiles(1.58.x).bak``
    are excluded.
    """
    results: list[Path] = []
    for sub in PROFILE_DIRECTORY_NAMES:
        parent = install.documents_dir / sub
        if not parent.is_dir():
            continue
        for profile_dir in sorted(p for p in parent.iterdir() if p.is_dir()):
            sii = profile_dir / PROFILE_FILE_NAME
            if sii.is_file():
                results.append(sii)
    return results
