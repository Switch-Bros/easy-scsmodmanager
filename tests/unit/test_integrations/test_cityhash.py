from __future__ import annotations

from easy_scsmodmanager.integrations.scs.cityhash import city_hash64, hash_path


def test_empty_string_is_k2() -> None:
    # CityHash64("") == K2. HashFS uses this hash for the root directory.
    assert city_hash64(b"") == 0x9AE16A3B2F90404F


def test_hash_path_matches_real_archive_entry() -> None:
    # Verified against a real HashFS v1 mod (51ROEXcore.scs): the entry for
    # "manifest.sii" with salt 0 hashes to this value.
    assert hash_path("manifest.sii", 0) == 0xB97FFF7CE7377C95


def test_root_path_variants_hash_equal() -> None:
    assert hash_path("", 0) == hash_path("/", 0) == city_hash64(b"")


def test_hash_path_strips_leading_slash() -> None:
    assert hash_path("/def/world", 0) == hash_path("def/world", 0)


def test_hash_path_applies_decimal_salt_prefix() -> None:
    assert hash_path("manifest.sii", 7) == city_hash64(b"7manifest.sii")
    assert hash_path("manifest.sii", 7) != hash_path("manifest.sii", 0)


def test_long_input_uses_main_loop() -> None:
    # >64 bytes exercises the 64-byte chunk loop; just assert it is stable and
    # masked to 64 bits (no crash, no overflow past 2**64).
    value = city_hash64(b"a/very/long/path/that/exceeds/sixty-four/bytes/" * 3)
    assert 0 <= value < 2**64
