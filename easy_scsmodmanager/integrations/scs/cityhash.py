"""CityHash64 - the hash HashFS uses to address entries by path.

Ported from TruckLib.HashFs (sk-zk), which ports cityhash-c, which ports
Google's original CityHash. Pure Python; 64-bit unsigned arithmetic is
emulated by masking every intermediate to 64 bits.
"""

from __future__ import annotations

import struct

_MASK = 0xFFFFFFFFFFFFFFFF

# Primes between 2^63 and 2^64.
_K0 = 0xC3A5C85C97CB3127
_K1 = 0xB492B66FBE98F273
_K2 = 0x9AE16A3B2F90404F
_K3 = 0xC949D7C7509E6557
_KMUL = 0x9DDFEA08EB382D69


def _rotate(val: int, shift: int) -> int:
    if shift == 0:
        return val
    return ((val >> shift) | (val << (64 - shift))) & _MASK


def _rotate_by_atleast1(val: int, shift: int) -> int:
    return ((val >> shift) | (val << (64 - shift))) & _MASK


def _shift_mix(val: int) -> int:
    return (val ^ (val >> 47)) & _MASK


def _fetch32(data: bytes, pos: int = 0) -> int:
    return struct.unpack_from("<I", data, pos)[0]


def _fetch64(data: bytes, pos: int = 0) -> int:
    return struct.unpack_from("<Q", data, pos)[0]


def _hash128_to_64(first: int, second: int) -> int:
    a = ((first ^ second) * _KMUL) & _MASK
    a = (a ^ (a >> 47)) & _MASK
    b = ((second ^ a) * _KMUL) & _MASK
    b = (b ^ (b >> 47)) & _MASK
    return (b * _KMUL) & _MASK


def _hash_len16(u: int, v: int) -> int:
    return _hash128_to_64(u, v)


def _hash_len0_to16(s: bytes, length: int) -> int:
    if length > 8:
        a = _fetch64(s)
        b = _fetch64(s, length - 8)
        return _hash_len16(a, _rotate_by_atleast1((b + length) & _MASK, length)) ^ b
    if length >= 4:
        a = _fetch32(s)
        return _hash_len16((length + (a << 3)) & _MASK, _fetch32(s, length - 4))
    if length > 0:
        a = s[0]
        b = s[length >> 1]
        c = s[length - 1]
        y = (a + (b << 8)) & _MASK
        z = (length + (c << 2)) & _MASK
        return (_shift_mix(((y * _K2) ^ (z * _K3)) & _MASK) * _K2) & _MASK
    return _K2


def _hash_len17_to32(s: bytes, length: int) -> int:
    a = (_fetch64(s) * _K1) & _MASK
    b = _fetch64(s, 8)
    c = (_fetch64(s, length - 8) * _K2) & _MASK
    d = (_fetch64(s, length - 16) * _K0) & _MASK
    return _hash_len16(
        (_rotate((a - b) & _MASK, 43) + _rotate(c, 30) + d) & _MASK,
        (a + _rotate((b ^ _K3) & _MASK, 20) - c + length) & _MASK,
    )


def _weak_hash_len32_with_seeds_raw(
    w: int, x: int, y: int, z: int, a: int, b: int
) -> tuple[int, int]:
    a = (a + w) & _MASK
    b = _rotate((b + a + z) & _MASK, 21)
    c = a
    a = (a + x) & _MASK
    a = (a + y) & _MASK
    b = (b + _rotate(a, 44)) & _MASK
    return (a + z) & _MASK, (b + c) & _MASK


def _weak_hash_len32_with_seeds(s: bytes, pos: int, a: int, b: int) -> tuple[int, int]:
    return _weak_hash_len32_with_seeds_raw(
        _fetch64(s, pos),
        _fetch64(s, pos + 8),
        _fetch64(s, pos + 16),
        _fetch64(s, pos + 24),
        a,
        b,
    )


def _hash_len33_to64(s: bytes, length: int) -> int:
    z = _fetch64(s, 24)
    a = (_fetch64(s) + (length + _fetch64(s, length - 16)) * _K0) & _MASK
    b = _rotate((a + z) & _MASK, 52)
    c = _rotate(a, 37)
    a = (a + _fetch64(s, 8)) & _MASK
    c = (c + _rotate(a, 7)) & _MASK
    a = (a + _fetch64(s, 16)) & _MASK
    vf = (a + z) & _MASK
    vs = (b + _rotate(a, 31) + c) & _MASK
    a = (_fetch64(s, 16) + _fetch64(s, length - 32)) & _MASK
    z = _fetch64(s, length - 8)
    b = _rotate((a + z) & _MASK, 52)
    c = _rotate(a, 37)
    a = (a + _fetch64(s, length - 24)) & _MASK
    c = (c + _rotate(a, 7)) & _MASK
    a = (a + _fetch64(s, length - 16)) & _MASK
    wf = (a + z) & _MASK
    ws = (b + _rotate(a, 31) + c) & _MASK
    r = _shift_mix(((vf + ws) * _K2 + (wf + vs) * _K0) & _MASK)
    return _shift_mix((r * _K0 + vs) & _MASK) * _K2 & _MASK


def city_hash64(data: bytes) -> int:
    """CityHash64 of a byte string, as a 64-bit unsigned int."""
    length = len(data)
    if length <= 16:
        return _hash_len0_to16(data, length)
    if length <= 32:
        return _hash_len17_to32(data, length)
    if length <= 64:
        return _hash_len33_to64(data, length)

    s = data
    x = _fetch64(s, length - 40)
    y = (_fetch64(s, length - 16) + _fetch64(s, length - 56)) & _MASK
    z = _hash_len16((_fetch64(s, length - 48) + length) & _MASK, _fetch64(s, length - 24))
    v = _weak_hash_len32_with_seeds(s, length - 64, length, z)
    w = _weak_hash_len32_with_seeds(s, length - 32, (y + _K1) & _MASK, x)
    x = (x * _K1 + _fetch64(s)) & _MASK

    pos = 0
    remaining = (length - 1) & ~63
    while True:
        x = (_rotate((x + y + v[0] + _fetch64(s, pos + 8)) & _MASK, 37) * _K1) & _MASK
        y = (_rotate((y + v[1] + _fetch64(s, pos + 48)) & _MASK, 42) * _K1) & _MASK
        x ^= w[1]
        y = (y + v[0] + _fetch64(s, pos + 40)) & _MASK
        z = (_rotate((z + w[0]) & _MASK, 33) * _K1) & _MASK
        v = _weak_hash_len32_with_seeds(s, pos, (v[1] * _K1) & _MASK, (x + w[0]) & _MASK)
        w = _weak_hash_len32_with_seeds(
            s, pos + 32, (z + w[1]) & _MASK, (y + _fetch64(s, pos + 16)) & _MASK
        )
        z, x = x, z
        pos += 64
        remaining -= 64
        if remaining == 0:
            break

    return _hash_len16(
        (_hash_len16(v[0], w[0]) + _shift_mix(y) * _K1 + z) & _MASK,
        (_hash_len16(v[1], w[1]) + x) & _MASK,
    )


def hash_path(path: str, salt: int = 0) -> int:
    """Hash a HashFS entry path the way the game does.

    Drops a leading slash; if salt is non-zero, prepends it as a decimal
    string; then CityHash64 of the UTF-8 bytes.
    """
    if path and path.startswith("/"):
        path = path[1:]
    if salt:
        path = f"{salt}{path}"
    return city_hash64(path.encode("utf-8"))
