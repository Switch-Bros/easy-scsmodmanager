"""Pure-Python GDeflate decompressor.

HashFS v2 stores packed textures (.tobj/.dds) with their pixel data compressed
in GDeflate - NVIDIA's DEFLATE variant whose bitstream is reordered for 32-way
parallelism (used by DirectStorage). zlib cannot read it. This is a port of
sk-zk/GisDeflate (managed C#, itself a port of libdeflate's inflate), verified
byte-for-byte against the original on the full ETS2 texture set.

Only decompression is implemented; that is all the extractor needs.
"""

from __future__ import annotations

import struct

from easy_scsmodmanager.integrations.scs.gdeflate_tables import (
    LITLEN_RESULTS,
    OFFSET_RESULTS,
    PRECODE_RESULTS,
)

NUM_STREAMS = 32  # GDeflate interleaves 32 parallel bit streams
BITS_PER_PACKET = 32
LOW_WATERMARK = 32
TILE_SIZE = 64 * 1024  # each tile decompresses to 64 KiB (last one may be less)

PRECODE_SYMS = 19
LITLEN_SYMS = 288
OFFSET_SYMS = 32
MAX_CW = 15  # longest codeword in any DEFLATE Huffman code
LENS_OVERRUN = 137

PRECODE_TABLEBITS = 7
LITLEN_TABLEBITS = 10
OFFSET_TABLEBITS = 8
MAX_PRE_CW = 7
MAX_LITLEN_CW = 15
MAX_OFFSET_CW = 15

# decode-table entry layout (matches libdeflate)
RESULT_SHIFT = 8
SUBTABLE_PTR = 0x80000000
LENGTH_MASK = 0xFF
LITERAL = 0x40000000
LENGTH_BASE_SHIFT = 8
EXTRA_LENGTH_MASK = 0xFF
EOB_LENGTH = 0
EXTRA_OFFSET_SHIFT = 16
OFFSET_BASE_MASK = (1 << EXTRA_OFFSET_SHIFT) - 1

PRECODE_PERM = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)
MASK64 = (1 << 64) - 1
MASK32 = (1 << 32) - 1

# decode-table sizes (zlib's 'enough' worst case, must match the TABLEBITS above)
PRECODE_ENOUGH = 128
LITLEN_ENOUGH = 1334
OFFSET_ENOUGH = 402

KDEFLATE_ID = 4


class GDeflateError(Exception):
    """Malformed or unsupported GDeflate stream."""


def _result_entry(r: int) -> int:
    return (r << RESULT_SHIFT) & MASK32


def _le32(buf: bytes, off: int) -> int:
    chunk = buf[off : off + 4]
    if len(chunk) < 4:
        chunk = chunk + bytes(4 - len(chunk))  # zero-pad over-read; bits unused
    return chunk[0] | (chunk[1] << 8) | (chunk[2] << 16) | (chunk[3] << 24)


def _build_decode_table(
    table: list[int],
    lens: list[int],
    num_syms: int,
    results: list[int],
    table_bits: int,
    max_cw: int,
    sorted_syms: list[int],
) -> None:
    # Build a fast lookup table for a canonical Huffman code from its codeword
    # lengths. Ported verbatim from libdeflate; assumes bit-reversed codewords.
    len_counts = [0] * (MAX_CW + 1)
    offsets = [0] * (MAX_CW + 1)
    for sym in range(num_syms):
        len_counts[lens[sym]] += 1
    offsets[0] = 0
    offsets[1] = len_counts[0]
    codespace = 0
    for ln in range(1, max_cw):
        offsets[ln + 1] = offsets[ln] + len_counts[ln]
        codespace = (codespace << 1) + len_counts[ln]
    codespace = (codespace << 1) + len_counts[max_cw]
    for sym in range(num_syms):
        sorted_syms[offsets[lens[sym]]] = sym
        offsets[lens[sym]] += 1
    ssi = offsets[0]  # skip the length-0 (unused) symbols

    if codespace > (1 << max_cw):
        raise GDeflateError("overfull huffman code")
    if codespace < (1 << max_cw):
        raise GDeflateError("incomplete huffman code")

    codeword = 0
    ln = 1
    while len_counts[ln] == 0:
        ln += 1
    count = len_counts[ln]
    cur_end = 1 << ln
    while ln <= table_bits:
        while True:
            table[codeword] = results[sorted_syms[ssi]] | ln
            ssi += 1
            if codeword == cur_end - 1:
                while ln < table_bits:
                    table[cur_end : cur_end * 2] = table[0:cur_end]
                    cur_end <<= 1
                    ln += 1
                return
            bit = 1 << (codeword ^ (cur_end - 1)).bit_length() - 1
            codeword &= bit - 1
            codeword |= bit
            count -= 1
            if count == 0:
                break
        while True:
            ln += 1
            if ln <= table_bits:
                table[cur_end : cur_end * 2] = table[0:cur_end]
                cur_end <<= 1
            count = len_counts[ln]
            if count != 0:
                break

    # codewords longer than table_bits need subtables
    cur_end = 1 << table_bits
    subtable_prefix = 0xFFFFFFFF
    subtable_start = 0
    while True:
        if (codeword & ((1 << table_bits) - 1)) != subtable_prefix:
            subtable_prefix = codeword & ((1 << table_bits) - 1)
            subtable_start = cur_end
            subtable_bits = ln - table_bits
            codespace = count
            while codespace < (1 << subtable_bits):
                subtable_bits += 1
                codespace = (codespace << 1) + len_counts[table_bits + subtable_bits]
            cur_end = subtable_start + (1 << subtable_bits)
            table[subtable_prefix] = (
                SUBTABLE_PTR | _result_entry(subtable_start) | subtable_bits
            ) & MASK32
        entry = results[sorted_syms[ssi]] | (ln - table_bits)
        ssi += 1
        i = subtable_start + (codeword >> table_bits)
        stride = 1 << (ln - table_bits)
        while i < cur_end:
            table[i] = entry
            i += stride
        if codeword == (1 << ln) - 1:
            return
        bit = 1 << (codeword ^ ((1 << ln) - 1)).bit_length() - 1
        codeword &= bit - 1
        codeword |= bit
        count -= 1
        while count == 0:
            ln += 1
            count = len_counts[ln]


class _Inflater:
    """Decodes a single 64 KiB GDeflate tile into ``out`` at ``out_idx``."""

    def __init__(self, page: bytes, out: bytearray, out_idx: int, out_avail: int) -> None:
        self.page = page
        self.out = out
        self.in_next = 0
        self.out_next = out_idx
        self.out_end = out_idx + out_avail
        self.bitbuf = [0] * NUM_STREAMS
        self.bitsleft = [0] * NUM_STREAMS
        self.copy_len = [0] * NUM_STREAMS
        self.copy_out = [0] * NUM_STREAMS
        self.idx = 0
        self.is_copy = 0
        self.litlen = [0] * LITLEN_ENOUGH
        self.offset = [0] * OFFSET_ENOUGH
        self.precode = [0] * PRECODE_ENOUGH
        self.lens = [0] * (LITLEN_SYMS + OFFSET_SYMS + LENS_OVERRUN)
        self.precode_lens = [0] * PRECODE_SYMS
        self.sorted_syms = [0] * LITLEN_SYMS

    def _ensure(self, n: int) -> None:
        if self.bitsleft[self.idx] < n:
            self.bitbuf[self.idx] = (
                self.bitbuf[self.idx] | (_le32(self.page, self.in_next) << self.bitsleft[self.idx])
            ) & MASK64
            self.in_next += BITS_PER_PACKET // 8
            self.bitsleft[self.idx] += BITS_PER_PACKET

    def _bits(self, n: int) -> int:
        return self.bitbuf[self.idx] & ((1 << n) - 1)

    def _remove(self, n: int) -> None:
        self.bitbuf[self.idx] >>= n
        self.bitsleft[self.idx] -= n

    def _pop(self, n: int) -> int:
        v = self._bits(n)
        self._remove(n)
        return v

    def _advance(self) -> None:
        self._ensure(LOW_WATERMARK)
        self.idx = (self.idx + 1) % NUM_STREAMS
        self.is_copy = ((self.is_copy >> 1) | (self.is_copy << (NUM_STREAMS - 1))) & MASK32

    def _do_copy(self) -> None:
        length = self.copy_len[self.idx]
        out_next = self.copy_out[self.idx]
        entry = self.offset[self._bits(OFFSET_TABLEBITS)]
        if entry & SUBTABLE_PTR:
            self._remove(OFFSET_TABLEBITS)
            entry = self.offset[
                ((entry >> RESULT_SHIFT) & 0xFFFF) + self._bits(entry & LENGTH_MASK)
            ]
        self._remove(entry & LENGTH_MASK)
        entry >>= RESULT_SHIFT
        offset = (entry & OFFSET_BASE_MASK) + self._pop(entry >> EXTRA_OFFSET_SHIFT)
        src = out_next - offset
        dst = out_next
        end = out_next + length
        out = self.out
        while dst < end:
            out[dst] = out[src]
            dst += 1
            src += 1

    def _build_huffman(self, num_litlen: int, num_offset: int) -> None:
        # offset table first so it does not clobber lens before litlen is built
        _build_decode_table(
            self.offset,
            self.lens[num_litlen:],
            num_offset,
            OFFSET_RESULTS,
            OFFSET_TABLEBITS,
            MAX_OFFSET_CW,
            self.sorted_syms,
        )
        _build_decode_table(
            self.litlen,
            self.lens,
            num_litlen,
            LITLEN_RESULTS,
            LITLEN_TABLEBITS,
            MAX_LITLEN_CW,
            self.sorted_syms,
        )

    def _main_loop(self) -> None:
        self.idx = 0
        while True:
            if (self.is_copy & 1) == 0:
                entry = self.litlen[self._bits(LITLEN_TABLEBITS)]
                if entry & SUBTABLE_PTR:
                    self._remove(LITLEN_TABLEBITS)
                    entry = self.litlen[
                        ((entry >> RESULT_SHIFT) & 0xFFFF) + self._bits(entry & LENGTH_MASK)
                    ]
                self._remove(entry & LENGTH_MASK)
                if entry & LITERAL:
                    if self.out_next == self.out_end:
                        raise GDeflateError("output overrun")
                    self.out[self.out_next] = (entry >> RESULT_SHIFT) & 0xFF
                    self.out_next += 1
                    self._advance()
                    continue
                entry >>= RESULT_SHIFT
                length = (entry >> LENGTH_BASE_SHIFT) + self._pop(entry & EXTRA_LENGTH_MASK)
                # length 0 is end-of-block; (length - 1) wraps to a huge value
                if ((length - 1) & MASK32) >= self.out_end - self.out_next:
                    if length != EOB_LENGTH:
                        raise GDeflateError("output overrun")
                    return
                self.copy_len[self.idx] = length
                self.copy_out[self.idx] = self.out_next
                self.is_copy |= 1
                self.out_next += length
            else:
                self._do_copy()
                self.is_copy &= ~1
            self._advance()

    def _block_done(self) -> None:
        # flush any copies still pending in the other 31 streams
        for _ in range(NUM_STREAMS):
            if self.is_copy & 1:
                self._do_copy()
                self.is_copy &= ~1
            self._advance()

    def run(self) -> None:
        self.idx = 0
        for _ in range(NUM_STREAMS):
            self._advance()

        while True:
            self.idx = 0
            is_final = self._pop(1)
            block_type = self._pop(2)
            self._ensure(LOW_WATERMARK)

            if block_type == 2:  # dynamic Huffman
                num_litlen = self._pop(5) + 257
                num_offset = self._pop(5) + 1
                num_explicit = self._pop(4) + 4
                self._ensure(LOW_WATERMARK)
                i = 0
                while i < num_explicit:
                    self.precode_lens[PRECODE_PERM[i]] = self._pop(3)
                    self._advance()
                    i += 1
                while i < PRECODE_SYMS:
                    self.precode_lens[PRECODE_PERM[i]] = 0
                    i += 1
                _build_decode_table(
                    self.precode,
                    self.precode_lens,
                    PRECODE_SYMS,
                    PRECODE_RESULTS,
                    PRECODE_TABLEBITS,
                    MAX_PRE_CW,
                    self.sorted_syms,
                )
                self.idx = 0
                i = 0
                total = num_litlen + num_offset
                while i < total:
                    entry = self.precode[self._bits(MAX_PRE_CW)]
                    self._remove(entry & LENGTH_MASK)
                    presym = entry >> RESULT_SHIFT
                    if presym < 16:
                        self.lens[i] = presym
                        i += 1
                        self._advance()
                        continue
                    if presym == 16:
                        rep = self.lens[i - 1]
                        cnt = 3 + self._pop(2)
                        for j in range(6):
                            self.lens[i + j] = rep
                        i += cnt
                    elif presym == 17:
                        cnt = 3 + self._pop(3)
                        for j in range(10):
                            self.lens[i + j] = 0
                        i += cnt
                    else:
                        cnt = 11 + self._pop(7)
                        for j in range(i, i + cnt):
                            self.lens[j] = 0
                        i += cnt
                    self._advance()
                self._build_huffman(num_litlen, num_offset)
            elif block_type == 0:  # uncompressed
                ln = self._pop(16)
                if ln > self.out_end - self.out_next:
                    raise GDeflateError("output overrun")
                while ln > 0:
                    self.out[self.out_next] = self._pop(8)
                    self.out_next += 1
                    ln -= 1
                    self._advance()
                self._block_done()
                if is_final:
                    return
                continue
            elif block_type == 1:  # static Huffman
                i = 0
                while i < 144:
                    self.lens[i] = 8
                    i += 1
                while i < 256:
                    self.lens[i] = 9
                    i += 1
                while i < 280:
                    self.lens[i] = 7
                    i += 1
                while i < 288:
                    self.lens[i] = 8
                    i += 1
                while i < 288 + 32:
                    self.lens[i] = 5
                    i += 1
                self._build_huffman(288, 32)
            else:
                raise GDeflateError("reserved block type")

            self._main_loop()
            self._block_done()
            if is_final:
                return


def decompress(data: bytes) -> bytes:
    """Decompress a complete GDeflate stream and return the raw bytes."""
    if len(data) < 8:
        raise GDeflateError("truncated gdeflate stream")
    id_, magic = data[0], data[1]
    if magic != (id_ ^ 0xFF):
        raise GDeflateError("malformed gdeflate stream")
    if id_ != KDEFLATE_ID:
        raise GDeflateError(f"unknown gdeflate id {id_}")
    num_tiles = data[2] | (data[3] << 8)
    bitfield = struct.unpack_from("<I", data, 4)[0]
    last_tile_size = (bitfield >> 2) & 0x3FFFF
    uncompressed = num_tiles * TILE_SIZE - (
        0 if last_tile_size == 0 else TILE_SIZE - last_tile_size
    )
    out = bytearray(uncompressed)
    tile_offsets = [struct.unpack_from("<I", data, 8 + 4 * i)[0] for i in range(num_tiles)]
    in_data = data[8 + num_tiles * 4 :]
    for ti in range(num_tiles):
        # tile 0 starts at 0; offsets[0] doubles as the last tile's length
        off = tile_offsets[ti] if ti > 0 else 0
        length = (tile_offsets[ti + 1] - off) if ti < num_tiles - 1 else tile_offsets[0]
        page = in_data[off : off + length]
        _Inflater(page, out, ti * TILE_SIZE, TILE_SIZE).run()
    return bytes(out)
