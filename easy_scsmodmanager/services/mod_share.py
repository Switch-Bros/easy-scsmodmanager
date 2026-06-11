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
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.core.version_compare import compare_versions
from easy_scsmodmanager.services.mod_identity import workshop_url_from_active_name
from easy_scsmodmanager.services.profile_reader import ActiveMod, Profile

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


def build_from_profile(
    profile: Profile,
    game: Game,
    *,
    versions: Mapping[str, str],
    groups: Mapping[str, str],
) -> ShareList:
    """Snapshot the profile's active list into a shareable ShareList.

    versions/groups are keyed by active name; missing keys mean "unknown"
    and end up as empty strings (optional fields in the format).
    """
    entries = tuple(
        ShareEntry(
            name=m.name,
            display_name=m.display_name,
            package_version=versions.get(m.name, ""),
            group=groups.get(m.name, ""),
        )
        for m in profile.active_mods
    )
    return ShareList(game=game, profile_name=profile.profile_name, entries=entries)


def to_active_mods(share: ShareList, skip: AbstractSet[str] = frozenset()) -> list[ActiveMod]:
    """The writer-ready list, share order preserved, ``skip`` names dropped."""
    return [
        ActiveMod(name=e.name, display_name=e.display_name)
        for e in share.entries
        if e.name not in skip
    ]


def normalize_code(raw: str) -> str:
    """Uppercase, drop everything outside the code alphabet, cap the length."""
    cleaned = "".join(ch for ch in raw.upper() if ch in CODE_ALPHABET)
    return cleaned[:CODE_LENGTH]


@dataclass(frozen=True)
class ShareDiff:
    """Receiver-side view of a share: what is here, what is not."""

    found: tuple[ShareEntry, ...]
    missing_workshop: tuple[tuple[ShareEntry, str], ...]  # (entry, subscribe url)
    missing_local: tuple[ShareEntry, ...]
    outdated: tuple[tuple[ShareEntry, str], ...]  # (entry, local version)

    def missing_names(self) -> set[str]:
        return {e.name for e, _ in self.missing_workshop} | {e.name for e in self.missing_local}


def diff(share: ShareList, installed: Mapping[str, str | None]) -> ShareDiff:
    """Bucket the share against the receiver's mods.

    ``installed`` maps entry.name -> local package_version; "" means
    installed with unknown version, a missing key or None means the mod
    is not installed. The caller builds this via ActiveModMatcher so all
    its matching strategies apply (see mod_share_controller).
    """
    found: list[ShareEntry] = []
    missing_ws: list[tuple[ShareEntry, str]] = []
    missing_local: list[ShareEntry] = []
    outdated: list[tuple[ShareEntry, str]] = []
    for entry in share.entries:
        local_version = installed.get(entry.name)
        if local_version is None:
            url = workshop_url_from_active_name(entry.name)
            if url is not None:
                missing_ws.append((entry, url))
            else:
                missing_local.append(entry)
            continue
        found.append(entry)
        if (
            entry.package_version
            and local_version
            and compare_versions(local_version, entry.package_version) == -1
        ):
            outdated.append((entry, local_version))
    return ShareDiff(
        found=tuple(found),
        missing_workshop=tuple(missing_ws),
        missing_local=tuple(missing_local),
        outdated=tuple(outdated),
    )
