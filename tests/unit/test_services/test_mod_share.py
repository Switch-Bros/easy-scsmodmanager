"""ModShare format: serialize/parse and payload mapping."""

import pytest

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.services.mod_share import (
    FORMAT_ID,
    ModShareError,
    ModShareVersionError,
    ShareEntry,
    ShareList,
    parse,
    serialize,
)


def _share() -> ShareList:
    return ShareList(
        game=Game.ETS2,
        profile_name="Sender",
        entries=(
            ShareEntry(
                name="mod_workshop_package.000000003A4B7C12",
                display_name="ProMods",
                package_version="2.68",
                group="maps",
            ),
            ShareEntry(name="local_mod", display_name="Local Mod"),
        ),
    )


def test_roundtrip_preserves_everything() -> None:
    assert parse(serialize(_share())) == _share()


def test_serialized_form_is_stable_json() -> None:
    text = serialize(_share())
    assert f'"format": "{FORMAT_ID}"' in text
    assert '"game": "ets2"' in text
    assert '"version": 1' in text


def test_optional_fields_default_empty() -> None:
    text = (
        '{"format": "easy-scsmodmanager-modshare", "version": 1, "game": "ats",'
        ' "profile_name": "", "mods": [{"name": "a"}]}'
    )
    share = parse(text)
    assert share.game is Game.ATS
    assert share.entries[0] == ShareEntry(name="a")


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "{}",
        '{"format": "something-else", "version": 1, "game": "ets2", "mods": []}',
        '{"format": "easy-scsmodmanager-modshare", "version": 1, "game": "fs25", "mods": []}',
        '{"format": "easy-scsmodmanager-modshare", "version": 1, "game": "ets2", "mods": [{}]}',
        '{"format": "easy-scsmodmanager-modshare", "version": 1, "game": "ets2", "profile_name": [1], "mods": []}',
    ],
)
def test_bad_payloads_raise(text: str) -> None:
    with pytest.raises(ModShareError):
        parse(text)


def test_profile_name_null_or_missing_is_tolerated() -> None:
    base = '{"format": "easy-scsmodmanager-modshare", "version": 1, "game": "ets2", "mods": []}'
    assert parse(base).profile_name == ""
    with_null = (
        '{"format": "easy-scsmodmanager-modshare", "version": 1, "game": "ets2",'
        ' "profile_name": null, "mods": []}'
    )
    assert parse(with_null).profile_name == ""


def test_future_version_raises_distinct_error() -> None:
    text = (
        '{"format": "easy-scsmodmanager-modshare", "version": 99, "game": "ets2",'
        ' "profile_name": "", "mods": []}'
    )
    with pytest.raises(ModShareVersionError):
        parse(text)
