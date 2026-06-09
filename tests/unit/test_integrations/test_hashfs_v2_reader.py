from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.cityhash import hash_path
from easy_scsmodmanager.integrations.scs.hashfs_reader import (
    HashFsError,
    HashFsV2Reader,
    open_hashfs,
)

_MAGIC = 0x23534353
_DATA_START = 64  # 16-aligned, past the 49-byte header


def _pack_main(offset: int, size: int, csize: int, compressed: bool) -> bytes:
    b = bytearray(16)
    b[0], b[1], b[2] = csize & 0xFF, (csize >> 8) & 0xFF, (csize >> 16) & 0xFF
    b[3] = ((csize >> 24) & 0x0F) | (0x10 if compressed else 0)
    b[4], b[5], b[6] = size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF
    b[7] = (size >> 24) & 0x0F
    struct.pack_into("<I", b, 12, offset // 16)
    return bytes(b)


def _build_v2(items: list[tuple], salt: int = 0) -> bytes:
    """items: (path, content, compress, chunk_type[, tobj_meta]).

    chunk_type 128=file/129=dir/1=image. For image entries the content is the
    raw GDeflate payload (stored verbatim, never zlib'd) and ``compress`` only
    sets the GDeflate flag; ``tobj_meta`` is the optional 12-byte metadata.
    """
    blobs = bytearray()
    placed = []
    for item in items:
        path, content, compress, chunk_type = item[:4]
        tobj_meta = item[4] if len(item) > 4 else bytes(12)
        stored = content if chunk_type == 1 else (zlib.compress(content) if compress else content)
        while (_DATA_START + len(blobs)) % 16:
            blobs.append(0)
        offset = _DATA_START + len(blobs)
        blobs += stored
        placed.append(
            (
                hash_path(path, salt),
                offset,
                len(content),
                len(stored),
                compress,
                chunk_type,
                tobj_meta,
            )
        )

    meta = bytearray()
    entry_records = []
    for h, offset, size, csize, compress, chunk_type, tobj_meta in placed:
        meta_index = len(meta) // 4
        meta += bytes([0, 0, 0, chunk_type])
        if chunk_type == 1:  # image: 12-byte packed tobj/dds metadata first
            meta += bytes(tobj_meta)
        meta += _pack_main(offset, size, csize, compress)
        entry_records.append((h, meta_index, 1))

    entry_table = bytearray()
    for h, mi, mc in entry_records:
        entry_table += struct.pack("<QIHH", h, mi, mc, 0)
    entry_c = zlib.compress(bytes(entry_table))
    meta_c = zlib.compress(bytes(meta))

    data = bytes(blobs)
    entry_start = _DATA_START + len(data)
    meta_start = entry_start + len(entry_c)

    header = bytearray()
    header += struct.pack("<IHH", _MAGIC, 2, salt)
    header += b"CITY"
    header += struct.pack("<I", len(entry_records))
    header += struct.pack("<I", len(entry_c))
    header += struct.pack("<I", len(entry_records))
    header += struct.pack("<I", len(meta_c))
    header += struct.pack("<Q", entry_start)
    header += struct.pack("<Q", meta_start)
    header += struct.pack("<I", 0)
    header += struct.pack("<B", 0)

    out = bytearray(header)
    out += b"\x00" * (_DATA_START - len(header))
    out += data
    out += entry_c
    out += meta_c
    return bytes(out)


_ROOT_LISTING = struct.pack("<I", 3) + bytes([4, 12, 8]) + b"/def" + b"manifest.sii" + b"icon.jpg"
_DEF_LISTING = struct.pack("<I", 1) + bytes([8]) + b"city.sii"


def _sample(tmp_path: Path, salt: int = 0) -> Path:
    items = [
        ("", _ROOT_LISTING, True, 129),
        ("def", _DEF_LISTING, True, 129),
        ("manifest.sii", b'display_name: "V2 Mod"', True, 128),
        ("icon.jpg", b"\xff\xd8\xff\xe0jpegbytes", False, 128),
        ("def/city.sii", b"nested city content", True, 128),
        ("road.dds", b"GDEFLATE-compressed-pixels", True, 1),  # packed texture
    ]
    path = tmp_path / "v2.scs"
    path.write_bytes(_build_v2(items, salt=salt))
    return path


def test_reads_manifest_text(tmp_path: Path) -> None:
    with HashFsV2Reader(_sample(tmp_path)) as r:
        assert r.has("manifest.sii")
        assert 'display_name: "V2 Mod"' in r.read_text("manifest.sii")


def test_reads_uncompressed_and_nested(tmp_path: Path) -> None:
    with HashFsV2Reader(_sample(tmp_path)) as r:
        assert r.read_bytes("icon.jpg") == b"\xff\xd8\xff\xe0jpegbytes"
        assert r.read_bytes("def/city.sii") == b"nested city content"


def test_binary_directory_listing(tmp_path: Path) -> None:
    with HashFsV2Reader(_sample(tmp_path)) as r:
        subdirs, files = r.list_dir("/")
        assert subdirs == ["def"]
        assert files == ["manifest.sii", "icon.jpg"]


def test_iter_files_walks_tree(tmp_path: Path) -> None:
    with HashFsV2Reader(_sample(tmp_path)) as r:
        assert set(r.iter_files()) == {
            "/manifest.sii",
            "/icon.jpg",
            "/def/city.sii",
        }


def test_packed_texture_entry_is_not_readable(tmp_path: Path) -> None:
    with HashFsV2Reader(_sample(tmp_path)) as r:
        assert not r.has("road.dds")
        with pytest.raises(HashFsError):
            r.read_bytes("road.dds")


def test_salt_is_honoured(tmp_path: Path) -> None:
    with HashFsV2Reader(_sample(tmp_path, salt=42)) as r:
        assert r.has("manifest.sii")


def test_open_hashfs_dispatches_to_v2(tmp_path: Path) -> None:
    r = open_hashfs(_sample(tmp_path))
    try:
        assert isinstance(r, HashFsV2Reader)
        assert r.has("manifest.sii")
    finally:
        r.close()


_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "scs_textures"


# a root listing naming exactly the two entries below (12 + 9 byte names)
_IMG_ROOT_LISTING = struct.pack("<I", 2) + bytes([12, 9]) + b"manifest.sii" + b"road.tobj"


def _image_archive(tmp_path: Path) -> Path:
    tobj = (_FIXTURES / "tex0.tobj12").read_bytes()
    payload = (_FIXTURES / "tex0.gdeflate").read_bytes()
    items = [
        ("", _IMG_ROOT_LISTING, True, 129),
        ("manifest.sii", b'display_name: "Tex Mod"', True, 128),
        ("road.tobj", payload, True, 1, tobj),  # real packed texture, GDeflate flag set
    ]
    path = tmp_path / "tex.scs"
    path.write_bytes(_build_v2(items))
    return path


def test_read_image_dds_rebuilds_texture(tmp_path: Path) -> None:
    want = (_FIXTURES / "tex0.dds").read_bytes()
    with HashFsV2Reader(_image_archive(tmp_path)) as r:
        assert r.is_image_entry("road.tobj")
        assert not r.is_image_entry("manifest.sii")
        assert r.read_image_dds("road.tobj") == want


def test_read_image_dds_rejects_plain_entry(tmp_path: Path) -> None:
    with HashFsV2Reader(_image_archive(tmp_path)) as r, pytest.raises(HashFsError):
        r.read_image_dds("manifest.sii")
