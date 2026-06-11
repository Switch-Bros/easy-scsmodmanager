"""ModShare serialisation: share the FULL active mod list between users.

The same JSON payload travels as a file on disk and as the jsonb body of
an online share code (see integrations/supabase/share_api.py). MapCombo
(maps-only, services/map_combo.py) stays untouched; this module is its
big sibling for whole load orders.

Pure and Qt-free: serialises, parses, builds from a Profile, diffs against
the receiver's installed mods and emits the ActiveMod list for the writer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from easy_scsmodmanager.core.game_paths import Game

FORMAT_ID = "easy-scsmodmanager-modshare"
FORMAT_VERSION = 1
FILE_SUFFIX = ".modshare.json"

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1 lookalikes
CODE_LENGTH = 6


class ModShareError(ValueError):
    """Raised when a payload is not a readable ModShare."""


class ModShareVersionError(ModShareError):
    """Raised when the payload was written by a newer app version."""


@dataclass(frozen=True)
class ShareEntry:
    name: str
    display_name: str = ""
    package_version: str = ""  # version on the SENDER's machine
    group: str = ""  # ESCSMM group token; foreign readers ignore it


@dataclass(frozen=True)
class ShareList:
    game: Game
    profile_name: str
    entries: tuple[ShareEntry, ...]


def to_payload(share: ShareList) -> dict:
    """The wire/file dict - identical for *.modshare.json and Supabase."""
    return {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "game": share.game.value,
        "profile_name": share.profile_name,
        "mods": [
            {
                "name": e.name,
                "display_name": e.display_name,
                "package_version": e.package_version,
                "group": e.group,
            }
            for e in share.entries
        ],
    }


def from_payload(data: object) -> ShareList:
    """Validate a decoded payload. Raises ModShareError on bad input."""
    if not isinstance(data, dict):
        raise ModShareError("payload is not an object")
    if data.get("format") != FORMAT_ID:
        raise ModShareError(f"not a ModShare payload (format={data.get('format')!r})")
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        raise ModShareError(f"bad version field: {version!r}")
    if version > FORMAT_VERSION:
        raise ModShareVersionError(f"payload version {version} > supported {FORMAT_VERSION}")
    try:
        game = Game(data.get("game"))
    except ValueError as exc:
        raise ModShareError(f"unknown game: {data.get('game')!r}") from exc
    mods = data.get("mods")
    if not isinstance(mods, list):
        raise ModShareError("mods is not a list")
    entries = []
    for raw in mods:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str) or not raw["name"]:
            raise ModShareError(f"bad mod entry: {raw!r}")
        entries.append(
            ShareEntry(
                name=raw["name"],
                display_name=str(raw.get("display_name", "")),
                package_version=str(raw.get("package_version", "")),
                group=str(raw.get("group", "")),
            )
        )
    raw_profile = data.get("profile_name")
    if raw_profile is not None and not isinstance(raw_profile, str):
        raise ModShareError(f"profile_name must be a string, got {type(raw_profile).__name__}")
    return ShareList(
        game=game,
        profile_name=raw_profile or "",
        entries=tuple(entries),
    )


def serialize(share: ShareList) -> str:
    """Pretty JSON suitable for a shareable file."""
    return json.dumps(to_payload(share), indent=2, ensure_ascii=False)


def parse(text: str) -> ShareList:
    """Parse a ModShare file. Raises ModShareError on bad input."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModShareError(f"not JSON: {exc}") from exc
    return from_payload(data)
