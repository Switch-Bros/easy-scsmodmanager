"""Rebuild a .dds file from a HashFS v2 packed-texture entry.

A v2 texture entry carries 12 bytes of tobj/dds metadata (dimensions, DXGI
format, mip/face counts, row/image alignment) plus the surface pixel data,
GDeflate-compressed. The game strips the DDS header and pads each row/mip to an
alignment; to get a usable .dds back we rebuild the header and undo that
padding. Ported from TruckLib.HashFs and verified byte-for-byte against it on
the full ETS2 texture set (dlc_north + base_vehicle, ~600 textures, all formats).
"""

from __future__ import annotations

import struct

from easy_scsmodmanager.integrations.scs.gdeflate import decompress

DDS_MAGIC = 0x20534444  # "DDS "
DX10_FOURCC = 808540228  # "DX10" - we always emit the extended header

# DDS_HEADER.dwFlags
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
# DDS_HEADER.dwCaps
DDSCAPS_COMPLEX = 0x8
DDSCAPS_MIPMAP = 0x400000
DDSCAPS_TEXTURE = 0x1000
# DDS_HEADER.dwCaps2
DDSCAPS2_CUBEMAP = 0x200
_CUBE_FACES = 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000
DDPF_FOURCC = 0x4

# DXGI formats by block size (4x4 block compression)
_BC_BLOCK8 = frozenset({70, 71, 72, 79, 80, 81})  # BC1, BC4
_BC_BLOCK16 = frozenset({73, 74, 75, 76, 77, 78, 82, 83, 84, 94, 95, 96, 97, 98, 99})
_PACKED4 = frozenset({68, 69, 107})
_PACKED8 = frozenset({108, 109})
_PLANAR2 = frozenset({103, 106})
_PLANAR4 = frozenset({104, 105})
_NV11 = 110

# bits per pixel for the non-block, non-packed DXGI formats (libdirectxtex table)
_BPP: dict[int, int] = {}
for _f in (1, 2, 3, 4):
    _BPP[_f] = 128
for _f in (5, 6, 7, 8):
    _BPP[_f] = 96
for _f in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 102, 108, 109):
    _BPP[_f] = 64
for _f in (
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    38,
    39,
    40,
    41,
    42,
    43,
    44,
    45,
    46,
    47,
    67,
    68,
    69,
    87,
    88,
    89,
    90,
    91,
    92,
    93,
    100,
    101,
    107,
):
    _BPP[_f] = 32
for _f in (104, 105):
    _BPP[_f] = 24
for _f in (48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 85, 86, 114, 115):
    _BPP[_f] = 16
for _f in (103, 106, 110):
    _BPP[_f] = 12
for _f in (60, 61, 62, 63, 64, 65, 111, 112, 113):
    _BPP[_f] = 8
_BPP[66] = 1


class TobjMeta:
    """The 12-byte tobj/dds metadata that precedes a v2 image entry."""

    __slots__ = (
        "width",
        "height",
        "mip",
        "format",
        "is_cube",
        "face",
        "pitch_align",
        "image_align",
    )

    def __init__(self, raw: bytes) -> None:
        if len(raw) < 12:
            raise ValueError("tobj metadata must be 12 bytes")
        self.width = struct.unpack_from("<H", raw, 0)[0] + 1
        self.height = struct.unpack_from("<H", raw, 2)[0] + 1
        img = struct.unpack_from("<I", raw, 4)[0]
        self.mip = (img & 0xF) + 1
        self.format = (img >> 4) & 0xFF
        self.is_cube = ((img >> 12) & 0x3) != 0
        self.face = ((img >> 14) & 0x3F) + 1
        self.pitch_align = 1 << ((img >> 20) & 0xF)
        self.image_align = 1 << ((img >> 24) & 0xF)


def _nearest(x: int, n: int) -> int:
    return (x + n - 1) // n * n if n else x


def _surface_info(w: int, h: int, fmt: int) -> tuple[int, int]:
    # returns (row_pitch, slice_pitch) for one mip level
    if fmt in _BC_BLOCK8 or fmt in _BC_BLOCK16:
        block = 8 if fmt in _BC_BLOCK8 else 16
        row = max(1, (w + 3) // 4) * block
        return row, row * max(1, (h + 3) // 4)
    if fmt in _PACKED4 or fmt in _PACKED8:
        num = 4 if fmt in _PACKED4 else 8
        row = ((w + 1) >> 1) * num
        return row, row * h
    if fmt == _NV11:
        row = ((w + 3) >> 2) * 4
        return row, row * (h * 2)
    if fmt in _PLANAR2 or fmt in _PLANAR4:
        num = 2 if fmt in _PLANAR2 else 4
        row = ((w + 1) >> 1) * num
        return row, row * h + ((row * h + 1) >> 1)
    bpp = _BPP.get(fmt, 0)
    if bpp == 0:
        raise ValueError(f"unsupported dxgi format {fmt}")
    row = (w * bpp + 7) // 8
    return row, row * h


def _subresources(meta: TobjMeta) -> list[tuple[int, int]]:
    subs = []
    w, h = meta.width, meta.height
    for _ in range(meta.mip):
        subs.append(_surface_info(w, h, meta.format))
        w = max(w // 2, 1)
        h = max(h // 2, 1)
    return subs


def _unpad_surface(meta: TobjMeta, surface: bytes) -> bytes:
    # the stored surface pads each mip to image_align and each row to
    # pitch_align; DDS wants it tightly packed, so copy row by row
    subs = _subresources(meta)
    out = bytearray()
    x = 0
    for _face in range(meta.face):
        for level in range(meta.mip):
            x = _nearest(x, meta.image_align)
            row_pitch, slice_pitch = subs[level]
            for _ in range(0, slice_pitch, row_pitch):
                x = _nearest(x, meta.pitch_align)
                out += surface[x : x + row_pitch]
                x += row_pitch
    return bytes(out)


def _dds_header(meta: TobjMeta) -> bytes:
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT
    caps = DDSCAPS_TEXTURE
    if meta.mip > 1:
        caps |= DDSCAPS_MIPMAP | DDSCAPS_COMPLEX
    caps2 = 0
    if meta.is_cube:
        caps |= DDSCAPS_COMPLEX
        caps2 = DDSCAPS2_CUBEMAP | _CUBE_FACES

    h = bytearray()
    h += struct.pack("<II", DDS_MAGIC, 124)
    h += struct.pack("<I", flags)
    h += struct.pack("<II", meta.height, meta.width)
    h += struct.pack("<III", 0, 0, meta.mip)  # pitch, depth, mipmapcount
    h += b"\x00" * 44  # 11 reserved dwords
    # DDS_PIXELFORMAT (32 bytes) - always DX10 four-cc, masks unused
    h += struct.pack("<III", 32, DDPF_FOURCC, DX10_FOURCC)
    h += struct.pack("<IIIII", 0, 0, 0, 0, 0)
    h += struct.pack("<II", caps, caps2)
    h += struct.pack("<III", 0, 0, 0)
    # DDS_HEADER_DXT10 (20 bytes)
    h += struct.pack("<iii", meta.format, 3, 4 if meta.is_cube else 0)  # fmt, Texture2D, cubeflag
    h += struct.pack("<II", 1, 0)  # array size, misc flags 2
    return bytes(h)


def reconstruct_dds(tobj_meta: bytes, payload: bytes, *, compressed: bool) -> bytes:
    """Rebuild a complete .dds file from a packed v2 image entry."""
    meta = TobjMeta(tobj_meta)
    surface = decompress(payload) if compressed else payload
    return _dds_header(meta) + _unpad_surface(meta, surface)
