from __future__ import annotations

import struct
import zlib

import pytest
from Crypto.Cipher import AES

from easy_scsmodmanager.integrations.sii.crypto import (
    SCSC_MAGIC,
    SCS_KEY,
    decrypt_scsc,
    is_scsc,
)


def _encrypt_for_test(plaintext: bytes) -> bytes:
    """Build a ScsC blob the way SCS Software does. Used to drive decrypt tests."""
    compressed = zlib.compress(plaintext)
    # AES-CBC needs padding; SCS pads with zeros to block boundary.
    pad = (-len(compressed)) % 16
    padded = compressed + b"\x00" * pad
    iv = b"\x11" * 16
    cipher = AES.new(SCS_KEY, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padded)
    hmac = b"\x00" * 32
    return (
        SCSC_MAGIC
        + hmac
        + iv
        + struct.pack("<I", len(plaintext))
        + ciphertext
    )


def test_is_scsc_detects_magic_bytes() -> None:
    assert is_scsc(b"ScsC" + b"\x00" * 60) is True


def test_is_scsc_returns_false_for_other_magic() -> None:
    assert is_scsc(b"SiiN" + b"\x00" * 60) is False
    assert is_scsc(b"PK\x03\x04") is False
    assert is_scsc(b"") is False


def test_decrypt_scsc_roundtrip_recovers_original_plaintext() -> None:
    original = (
        b"SiiNunit\n{\nprofile: .x\n{\nname: \"test\"\nactive_mods: 0\n}\n}\n"
    )
    blob = _encrypt_for_test(original)

    assert decrypt_scsc(blob) == original


def test_decrypt_scsc_raises_for_wrong_magic() -> None:
    with pytest.raises(ValueError, match="ScsC"):
        decrypt_scsc(b"SiiN" + b"\x00" * 60)


def test_decrypt_scsc_raises_for_truncated_header() -> None:
    with pytest.raises(ValueError):
        decrypt_scsc(b"ScsC" + b"\x00" * 4)
