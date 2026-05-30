from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.cityhash import hash_path
from easy_scsmodmanager.integrations.scs.hashfs_reader import (
    HashFsError,
    HashFsV1Reader,
    UnsupportedHashFsVersion,
    peek_version,
)


def _build_v1(items: list[tuple[str, bytes, bool, bool]], salt: int = 0) -> bytes:
    """Build a minimal HashFS v1 archive. items: (path, content, is_dir, compress)."""
    blobs = bytearray()
    meta: list[tuple[int, int, int, int, int]] = []
    for path, content, is_dir, compress in items:
        stored = zlib.compress(content) if compress else content
        flags = (0x1 if is_dir else 0) | (0x2 if compress else 0)
        offset = 24 + len(blobs)
        meta.append((hash_path(path, salt), offset, flags, len(content), len(stored)))
        blobs += stored
    start_offset = 24 + len(blobs)

    out = bytearray()
    out += struct.pack("<IHH", 0x23534353, 1, salt)
    out += b"CITY"
    out += struct.pack("<I", len(meta))
    out += struct.pack("<Q", start_offset)
    out += blobs
    for h, offset, flags, size, csize in meta:
        out += struct.pack("<QQIIII", h, offset, flags, 0, size, csize)
    return bytes(out)


def _sample(tmp_path: Path, salt: int = 0) -> Path:
    items = [
        ("", b"*def\r\nmanifest.sii\r\nicon.jpg", True, True),
        ("def", b"city.sii", True, True),
        (
            "manifest.sii",
            b'SiiNunit{\nmod_package: .pkg {\ndisplay_name: "Test Mod"\n}\n}',
            False,
            True,
        ),
        ("icon.jpg", b"\xff\xd8\xff\xe0rawjpeg", False, False),
        ("def/city.sii", b"city def content", False, True),
    ]
    data = _build_v1(items, salt=salt)
    path = tmp_path / "sample.scs"
    path.write_bytes(data)
    return path


def test_reads_manifest_text(tmp_path: Path) -> None:
    with HashFsV1Reader(_sample(tmp_path)) as r:
        assert r.has("manifest.sii")
        assert 'display_name: "Test Mod"' in r.read_text("manifest.sii")


def test_reads_uncompressed_entry(tmp_path: Path) -> None:
    with HashFsV1Reader(_sample(tmp_path)) as r:
        assert r.read_bytes("icon.jpg") == b"\xff\xd8\xff\xe0rawjpeg"


def test_reads_nested_compressed_file(tmp_path: Path) -> None:
    with HashFsV1Reader(_sample(tmp_path)) as r:
        assert r.read_bytes("def/city.sii") == b"city def content"


def test_has_is_false_for_missing_and_directories(tmp_path: Path) -> None:
    with HashFsV1Reader(_sample(tmp_path)) as r:
        assert not r.has("nope.sii")
        assert not r.has("def")  # a directory is not a readable file


def test_missing_file_raises(tmp_path: Path) -> None:
    with HashFsV1Reader(_sample(tmp_path)) as r, pytest.raises(FileNotFoundError):
        r.read_bytes("does/not/exist")


def test_list_dir_splits_subdirs_and_files(tmp_path: Path) -> None:
    with HashFsV1Reader(_sample(tmp_path)) as r:
        subdirs, files = r.list_dir("/")
        assert subdirs == ["def"]
        assert files == ["manifest.sii", "icon.jpg"]


def test_iter_files_walks_the_whole_tree(tmp_path: Path) -> None:
    with HashFsV1Reader(_sample(tmp_path)) as r:
        assert set(r.iter_files()) == {
            "/manifest.sii",
            "/icon.jpg",
            "/def/city.sii",
        }


def test_salt_is_honoured(tmp_path: Path) -> None:
    with HashFsV1Reader(_sample(tmp_path, salt=123)) as r:
        assert r.has("manifest.sii")


def test_peek_version_and_rejects_non_hashfs(tmp_path: Path) -> None:
    path = _sample(tmp_path)
    with open(path, "rb") as fh:
        assert peek_version(fh) == 1
    bad = tmp_path / "bad.scs"
    bad.write_bytes(b"PK\x03\x04 this is a zip")
    with pytest.raises(HashFsError):
        HashFsV1Reader(bad)


def test_iter_files_seeds_known_dirs_without_root_listing(tmp_path: Path) -> None:
    # No root ("") listing - like locale.scs. iter_files must still find files
    # via the known-top-dir seeds and known root files.
    items = [
        ("locale", b"english.sii", True, True),  # listing for /locale
        ("locale/english.sii", b"hello", False, True),
        ("manifest.sii", b"mod_package", False, True),  # a known root file
    ]
    path = tmp_path / "noroot.scs"
    path.write_bytes(_build_v1(items))
    with HashFsV1Reader(path) as r:
        assert set(r.iter_files()) == {"/locale/english.sii", "/manifest.sii"}


def test_v2_header_rejected_by_v1_reader(tmp_path: Path) -> None:
    # Magic + version 2 -> the v1 reader must refuse it clearly.
    data = struct.pack("<IHH", 0x23534353, 2, 0) + b"CITY" + b"\x00" * 40
    path = tmp_path / "v2.scs"
    path.write_bytes(data)
    with pytest.raises(UnsupportedHashFsVersion):
        HashFsV1Reader(path)
