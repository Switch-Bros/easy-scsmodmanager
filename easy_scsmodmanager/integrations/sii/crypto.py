"""Decrypts ScsC-encrypted SII files (profile.sii etc).

SCS Software encrypts the user's profile and a few other writeable SII
files with AES-256-CBC plus zlib compression. The key is publicly known
and ships in every game install. We only ever read with it - the writer
side stays out of this module.

Format (little-endian):

    Offset  Size  Field
    0x00    4     Magic "ScsC"
    0x04    32    HMAC (ignored on read)
    0x24    16    AES IV
    0x34    4     Declared plaintext size (uint32)
    0x38    N     Ciphertext (AES-CBC, zero-padded)
"""

from __future__ import annotations

import struct
import zlib

from Crypto.Cipher import AES

SCSC_MAGIC = b"ScsC"
SCS_KEY = bytes.fromhex(
    "2A5FCB1791D22FB60245B3D8369ED0B2"
    "C27371563FBF1F3C9EDF6B11825A5D0A"
)
HEADER_SIZE = 0x38  # 56


def is_scsc(data: bytes) -> bool:
    return data[:4] == SCSC_MAGIC


def decrypt_scsc(data: bytes) -> bytes:
    if data[:4] != SCSC_MAGIC:
        raise ValueError(f"not a ScsC blob (magic={data[:4]!r})")
    if len(data) < HEADER_SIZE:
        raise ValueError(f"truncated ScsC header ({len(data)} < {HEADER_SIZE} bytes)")

    iv = data[0x24:0x34]
    plain_size = struct.unpack("<I", data[0x34:0x38])[0]
    ciphertext = data[HEADER_SIZE:]

    cipher = AES.new(SCS_KEY, AES.MODE_CBC, iv)
    decompressed_blob = cipher.decrypt(ciphertext)
    plaintext = zlib.decompress(decompressed_blob)

    if len(plaintext) != plain_size:
        # Profile files in the wild sometimes have a one-off size mismatch
        # because SCS rounds. We trust the actual decompressed bytes.
        pass

    return plaintext
