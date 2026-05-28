from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest
from Crypto.Cipher import AES

from easy_scsmodmanager.core.game_paths import Game, GameInstall, InstallKind
from easy_scsmodmanager.integrations.sii.crypto import SCS_KEY, SCSC_MAGIC
from easy_scsmodmanager.services.profile_reader import (
    ActiveMod,
    Profile,
    decode_profile_dir_name,
    discover_profiles,
    read_profile,
)


def _encrypt_plain(plaintext: bytes) -> bytes:
    compressed = zlib.compress(plaintext)
    pad = (-len(compressed)) % 16
    padded = compressed + b"\x00" * pad
    iv = b"\x11" * 16
    cipher = AES.new(SCS_KEY, AES.MODE_CBC, iv)
    return (
        SCSC_MAGIC
        + b"\x00" * 32
        + iv
        + struct.pack("<I", len(plaintext))
        + cipher.encrypt(padded)
    )


def _profile_sii(
    profile_name: str = "Cip",
    active_mods: tuple[str, ...] = (),
) -> str:
    body = [
        "SiiNunit",
        "{",
        "user_profile : .profile",
        "{",
        f' profile_name: "{profile_name}"',
        f" active_mods: {len(active_mods)}",
    ]
    for i, mod in enumerate(active_mods):
        body.append(f' active_mods[{i}]: "{mod}"')
    body += ["}", "}", ""]
    return "\n".join(body)


# ---------------------------------------------------------------------------
# ActiveMod
# ---------------------------------------------------------------------------


def test_active_mod_parse_extracts_name_and_display() -> None:
    assert ActiveMod.parse("mod_name|Display Name") == ActiveMod(
        name="mod_name", display_name="Display Name"
    )


def test_active_mod_parse_handles_missing_display_name() -> None:
    assert ActiveMod.parse("mod_no_display") == ActiveMod(
        name="mod_no_display", display_name=""
    )


def test_active_mod_parse_keeps_extra_pipes_in_display() -> None:
    assert ActiveMod.parse("name|Display | with | pipes") == ActiveMod(
        name="name", display_name="Display | with | pipes"
    )


# ---------------------------------------------------------------------------
# decode_profile_dir_name
# ---------------------------------------------------------------------------


def test_decode_profile_dir_name_decodes_hex_utf8() -> None:
    # "Cip" in hex UTF-8
    assert decode_profile_dir_name("436970") == "Cip"


def test_decode_profile_dir_name_handles_emoji() -> None:
    # "★HeikeFootSlave" approximation - just verify utf-8 multi-byte works
    decoded = decode_profile_dir_name("E298864865696B65")
    assert decoded == "☆Heike"


def test_decode_profile_dir_name_returns_raw_on_invalid_hex() -> None:
    assert decode_profile_dir_name("not-hex") == "not-hex"


def test_decode_profile_dir_name_returns_raw_on_invalid_utf8() -> None:
    # ff is not valid utf-8 leading byte
    assert decode_profile_dir_name("ff") == "ff"


# ---------------------------------------------------------------------------
# Profile.from_sii_units
# ---------------------------------------------------------------------------


def test_profile_from_sii_units_extracts_name_and_active_mods() -> None:
    from easy_scsmodmanager.integrations.sii.parser import parse_sii

    text = _profile_sii("Oliver", ("a_mod|A Mod", "b_mod|B Mod"))
    units = parse_sii(text)

    profile = Profile.from_sii_units(units, dir_name="Oliver")

    assert profile.dir_name == "Oliver"
    assert profile.profile_name == "Oliver"
    assert profile.active_mods == (
        ActiveMod(name="a_mod", display_name="A Mod"),
        ActiveMod(name="b_mod", display_name="B Mod"),
    )


def test_profile_from_sii_units_handles_zero_active_mods() -> None:
    from easy_scsmodmanager.integrations.sii.parser import parse_sii

    text = _profile_sii("X", ())
    units = parse_sii(text)

    profile = Profile.from_sii_units(units, dir_name="X")

    assert profile.active_mods == ()


def test_profile_from_sii_units_raises_when_no_profile_unit() -> None:
    from easy_scsmodmanager.integrations.sii.parser import parse_sii

    text = "SiiNunit\n{\nother: .x\n{\nname: \"x\"\n}\n}\n"
    units = parse_sii(text)

    with pytest.raises(ValueError, match="profile"):
        Profile.from_sii_units(units, dir_name="x")


# ---------------------------------------------------------------------------
# read_profile
# ---------------------------------------------------------------------------


def test_read_profile_reads_plaintext(tmp_path: Path) -> None:
    profile_dir = tmp_path / "436970"  # hex for "Cip"
    profile_dir.mkdir()
    sii = profile_dir / "profile.sii"
    sii.write_text(_profile_sii("Cip", ("m1|Mod 1",)), encoding="utf-8")

    profile = read_profile(sii)

    assert profile.profile_name == "Cip"
    assert profile.dir_name == "Cip"
    assert profile.active_mods == (ActiveMod(name="m1", display_name="Mod 1"),)


def test_read_profile_reads_encrypted_scsc(tmp_path: Path) -> None:
    profile_dir = tmp_path / "436970"
    profile_dir.mkdir()
    plain = _profile_sii("Cip", ("m1|Mod 1", "m2|Mod 2")).encode("utf-8")
    (profile_dir / "profile.sii").write_bytes(_encrypt_plain(plain))

    profile = read_profile(profile_dir / "profile.sii")

    assert profile.profile_name == "Cip"
    assert len(profile.active_mods) == 2


def test_read_profile_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_profile(tmp_path / "nope" / "profile.sii")


# ---------------------------------------------------------------------------
# discover_profiles
# ---------------------------------------------------------------------------


def _install(tmp_path: Path) -> GameInstall:
    return GameInstall(
        game=Game.ETS2,
        kind=InstallKind.LINUX_NATIVE,
        documents_dir=tmp_path,
        workshop_dir=None,
    )


def test_discover_profiles_finds_local_profiles(tmp_path: Path) -> None:
    p = tmp_path / "profiles" / "436970"
    p.mkdir(parents=True)
    (p / "profile.sii").write_text("dummy")

    paths = discover_profiles(_install(tmp_path))

    assert paths == [p / "profile.sii"]


def test_discover_profiles_finds_steam_cloud_profiles(tmp_path: Path) -> None:
    p = tmp_path / "steam_profiles" / "436970"
    p.mkdir(parents=True)
    (p / "profile.sii").write_text("dummy")

    paths = discover_profiles(_install(tmp_path))

    assert paths == [p / "profile.sii"]


def test_discover_profiles_finds_both_local_and_cloud(tmp_path: Path) -> None:
    (tmp_path / "profiles" / "abc").mkdir(parents=True)
    (tmp_path / "profiles" / "abc" / "profile.sii").write_text("x")
    (tmp_path / "steam_profiles" / "def").mkdir(parents=True)
    (tmp_path / "steam_profiles" / "def" / "profile.sii").write_text("x")

    paths = discover_profiles(_install(tmp_path))

    assert len(paths) == 2


def test_discover_profiles_ignores_backup_dirs(tmp_path: Path) -> None:
    real = tmp_path / "steam_profiles" / "live"
    backup = tmp_path / "steam_profiles(1.58.1.4s).bak" / "live"
    real.mkdir(parents=True)
    backup.mkdir(parents=True)
    (real / "profile.sii").write_text("x")
    (backup / "profile.sii").write_text("x")

    paths = discover_profiles(_install(tmp_path))

    assert len(paths) == 1
    assert paths[0] == real / "profile.sii"


def test_discover_profiles_skips_dirs_without_profile_sii(tmp_path: Path) -> None:
    (tmp_path / "profiles" / "no-file").mkdir(parents=True)

    assert discover_profiles(_install(tmp_path)) == []
