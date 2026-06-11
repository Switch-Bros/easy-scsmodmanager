"""End-to-end: sender profile -> share -> receiver profile, plaintext and ScsC."""

from pathlib import Path

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.integrations.sii.crypto import encrypt_scsc
from easy_scsmodmanager.services.mod_share import (
    build_from_profile,
    diff,
    parse,
    serialize,
    to_active_mods,
)
from easy_scsmodmanager.services.profile_reader import read_profile
from easy_scsmodmanager.services.profile_writer import save_active_mods

SENDER_TEXT = (
    "SiiNunit\n"
    "{\n"
    "user_profile : _nameless.1ad.dead {\n"
    ' profile_name: "Sender"\n'
    " active_mods: 2\n"
    ' active_mods[0]: "mod_workshop_package.000000003A4B7C12|ProMods"\n'
    ' active_mods[1]: "local_mod|Local Mod"\n'
    "}\n"
    "}\n"
)

RECEIVER_TEXT = (
    "SiiNunit\n"
    "{\n"
    "user_profile : _nameless.2bc.beef {\n"
    ' profile_name: "Receiver"\n'
    " active_mods: 1\n"
    ' active_mods[0]: "something_old|Old"\n'
    "}\n"
    "}\n"
)


def _roundtrip(tmp_path: Path, receiver_bytes: bytes) -> None:
    sender = tmp_path / "sender.sii"
    sender.write_text(SENDER_TEXT, encoding="utf-8")
    receiver = tmp_path / "profile.sii"
    receiver.write_bytes(receiver_bytes)

    # sender side: build + export
    share = build_from_profile(read_profile(sender), Game.ETS2, versions={}, groups={})
    text = serialize(share)

    # receiver side: parse + diff + apply (skip nothing)
    parsed = parse(text)
    result = diff(parsed, installed={})
    assert len(result.missing_workshop) == 1
    assert len(result.missing_local) == 1
    save_active_mods(receiver, to_active_mods(parsed), backup=False)

    written = read_profile(receiver)
    assert [m.name for m in written.active_mods] == [
        "mod_workshop_package.000000003A4B7C12",
        "local_mod",
    ]
    assert written.active_mods[0].display_name == "ProMods"
    assert written.profile_name == "Receiver"  # everything else untouched


def test_roundtrip_into_plaintext_profile(tmp_path: Path) -> None:
    _roundtrip(tmp_path, RECEIVER_TEXT.encode("utf-8"))


def test_roundtrip_into_scsc_encrypted_profile(tmp_path: Path) -> None:
    _roundtrip(tmp_path, encrypt_scsc(RECEIVER_TEXT.encode("utf-8")))
