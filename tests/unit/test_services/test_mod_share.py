"""ModShare format: serialize/parse and payload mapping."""

import pytest

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.services.mod_share import (
    FORMAT_ID,
    ModShareError,
    ModShareVersionError,
    ShareEntry,
    ShareList,
    build_from_profile,
    diff,
    normalize_code,
    parse,
    serialize,
    to_active_mods,
)
from easy_scsmodmanager.services.profile_reader import ActiveMod, Profile


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


def _profile() -> Profile:
    return Profile(
        dir_name="abcd",
        profile_name="Sender",
        active_mods=(
            ActiveMod(name="mod_workshop_package.000000003A4B7C12", display_name="ProMods"),
            ActiveMod(name="local_mod", display_name="Local Mod"),
        ),
    )


def test_build_from_profile_carries_versions_and_groups() -> None:
    share = build_from_profile(
        _profile(),
        Game.ETS2,
        versions={"local_mod": "1.2"},
        groups={"mod_workshop_package.000000003A4B7C12": "maps"},
    )
    assert share.game is Game.ETS2
    assert len(share.entries) == 2
    assert share.profile_name == "Sender"
    assert share.entries[0].group == "maps"
    assert share.entries[0].package_version == ""
    assert share.entries[1].package_version == "1.2"
    assert share.entries[1].group == ""


def test_to_active_mods_preserves_order() -> None:
    share = build_from_profile(_profile(), Game.ETS2, versions={}, groups={})
    mods = to_active_mods(share)
    assert [m.name for m in mods] == ["mod_workshop_package.000000003A4B7C12", "local_mod"]
    assert mods[0].display_name == "ProMods"


def test_to_active_mods_can_skip_missing() -> None:
    share = build_from_profile(_profile(), Game.ETS2, versions={}, groups={})
    mods = to_active_mods(share, skip={"local_mod"})
    assert [m.name for m in mods] == ["mod_workshop_package.000000003A4B7C12"]


def test_normalize_code_uppercases_and_strips() -> None:
    assert normalize_code(" ab-cd3z ") == "ABCD3Z"
    assert normalize_code("abcd3zXX") == "ABCD3Z"  # capped at CODE_LENGTH
    assert normalize_code("i1o0") == ""  # lookalikes are not in the alphabet


def test_diff_buckets_found_missing_workshop_missing_local() -> None:
    share = ShareList(
        game=Game.ETS2,
        profile_name="x",
        entries=(
            ShareEntry(name="have_it", display_name="Have"),
            ShareEntry(name="mod_workshop_package.000000003A4B7C12", display_name="WsMissing"),
            ShareEntry(name="local_missing", display_name="LocalMissing"),
        ),
    )
    result = diff(share, installed={"have_it": "1.0"})
    assert [e.name for e in result.found] == ["have_it"]
    assert [(e.name, url) for e, url in result.missing_workshop] == [
        (
            "mod_workshop_package.000000003A4B7C12",
            "https://steamcommunity.com/sharedfiles/filedetails/?id=978025490",
        )
    ]
    assert [e.name for e in result.missing_local] == ["local_missing"]


def test_diff_flags_outdated_local_versions() -> None:
    share = ShareList(
        game=Game.ETS2,
        profile_name="x",
        entries=(
            ShareEntry(name="older_here", package_version="2.0"),
            ShareEntry(name="same_here", package_version="1.0"),
            ShareEntry(name="no_versions"),
        ),
    )
    result = diff(share, installed={"older_here": "1.0", "same_here": "1.0", "no_versions": ""})
    assert [(e.name, local) for e, local in result.outdated] == [("older_here", "1.0")]


def test_diff_missing_names() -> None:
    share = ShareList(
        game=Game.ETS2,
        profile_name="x",
        entries=(ShareEntry(name="a"), ShareEntry(name="b")),
    )
    result = diff(share, installed={"a": ""})
    assert result.missing_names() == {"b"}
