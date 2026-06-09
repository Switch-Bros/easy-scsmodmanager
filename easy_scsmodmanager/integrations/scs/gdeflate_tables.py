"""Static DEFLATE decode-result tables for the GDeflate decoder.

Split out of :mod:`gdeflate` so the decoder module stays focused on the inflate
loop. These map each Huffman symbol to its precomputed decode-table payload
(literal value, length base + extra bits, or offset base + extra bits), in the
bit-layout libdeflate expects. Built once at import.
"""

from __future__ import annotations

_RESULT_SHIFT = 8
_LITERAL = 0x40000000
_EXTRA_OFFSET_SHIFT = 16
_MASK32 = (1 << 32) - 1
_PRECODE_SYMS = 19
_LITLEN_SYMS = 288


def _entry(value: int) -> int:
    return (value << _RESULT_SHIFT) & _MASK32


def _gen_offset_results() -> list[int]:
    pairs = [
        (1, 0), (2, 0), (3, 0), (4, 0), (5, 1), (7, 1), (9, 2), (13, 2),
        (17, 3), (25, 3), (33, 4), (49, 4), (65, 5), (97, 5), (129, 6), (193, 6),
        (257, 7), (385, 7), (513, 8), (769, 8), (1025, 9), (1537, 9), (2049, 10),
        (3073, 10), (4097, 11), (6145, 11), (8193, 12), (12289, 12), (16385, 13),
        (24577, 13), (32769, 14), (49153, 14),
    ]  # fmt: skip
    return [_entry((extra << _EXTRA_OFFSET_SHIFT) | base) for base, extra in pairs]


def _gen_litlen_results() -> list[int]:
    r = [0] * _LITLEN_SYMS
    for i in range(256):
        r[i] = (i << 8) | _LITERAL
    length_pairs = [
        (0, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (8, 0), (9, 0), (10, 0),
        (11, 1), (13, 1), (15, 1), (17, 1), (19, 2), (23, 2), (27, 2), (31, 2),
        (35, 3), (43, 3), (51, 3), (59, 3), (67, 4), (83, 4), (99, 4), (115, 4),
        (131, 5), (163, 5), (195, 5), (227, 5), (3, 16), (3, 16), (3, 16),
    ]  # fmt: skip
    for k, (base, extra) in enumerate(length_pairs):
        r[256 + k] = (((base << 8) | extra) << 8) & _MASK32
    return r


def _gen_precode_results() -> list[int]:
    return [_entry(i) for i in range(_PRECODE_SYMS)]


PRECODE_RESULTS = _gen_precode_results()
LITLEN_RESULTS = _gen_litlen_results()
OFFSET_RESULTS = _gen_offset_results()
