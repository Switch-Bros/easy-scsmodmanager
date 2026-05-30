"""Pure-Python reader for HashFS (.scs) archives - the ``SCS#`` container.

Replaces the external sk-zk/Extractor binary for HashFS reads so the app is
self-contained on every platform (AppImage, deb, AUR, exe, ...). Ported from
TruckLib.HashFs (sk-zk). Covers HashFS v1 and v2.

A reader offers two things:

* the :class:`ModSource` interface (``has`` / ``read_text`` / ``read_bytes``)
  the scanner uses to pull ``manifest.sii`` + icon, and
* ``list_dir`` / ``iter_files`` to walk the whole archive, which is what a
  full "extract this .scs to a folder" feature needs.

v2 texture entries (packed .tobj/.dds) are GDeflate-compressed and need DDS
reconstruction; we record them but raise on read. Everything else - the SII,
text, jpg/png and other plain files plus directory listings - reads normally.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from easy_scsmodmanager.integrations.scs.cityhash import hash_path

MAGIC = 0x23534353  # "SCS#"
CITY_METHOD = "CITY"
ROOT = "/"

# Standard SCS top-level directories, used to seed iter_files for archives
# that omit the root listing (e.g. locale.scs).
_KNOWN_TOP_DIRS = (
    "automat",
    "def",
    "dlc",
    "effect",
    "font",
    "locale",
    "map",
    "material",
    "model",
    "model2",
    "prefab",
    "prefab2",
    "sound",
    "system",
    "ui",
    "unit",
    "vehicle",
)
_KNOWN_ROOT_FILES = (
    "manifest.sii",
    "version.sii",
    "version.txt",
    "description.txt",
    "mod_description.txt",
    "icon.jpg",
    "mod_workshop_icon.jpg",
)

_V2_BLOCK_SIZE = 16
_V2_META_BLOCK = 4
_CHUNK_IMAGE = 1
_CHUNK_PLAIN = 128
_CHUNK_DIRECTORY = 129


class HashFsError(Exception):
    """The file is not a HashFS archive we can read."""


class UnsupportedHashFsVersion(HashFsError):
    def __init__(self, version: int) -> None:
        super().__init__(f"Unsupported HashFS version {version}")
        self.version = version


@dataclass(frozen=True)
class _Entry:
    offset: int
    size: int
    compressed_size: int
    is_directory: bool
    is_compressed: bool
    is_image: bool = False  # v2 packed .tobj/.dds - content not decodable yet


def peek_version(fh: object) -> int:
    """Read the HashFS version from an open binary file (validates magic)."""
    head = fh.read(6)  # type: ignore[attr-defined]
    fh.seek(0)  # type: ignore[attr-defined]
    if len(head) < 6 or struct.unpack_from("<I", head, 0)[0] != MAGIC:
        raise HashFsError("not a HashFS archive")
    return struct.unpack_from("<H", head, 4)[0]


class _HashFsReaderBase:
    """Shared file access for both HashFS versions; subclasses parse + list."""

    _DIR_MARKER = "*"

    def __init__(self, path: Path | str) -> None:
        self._fh = open(path, "rb")  # noqa: SIM115 - closed in close()/__exit__
        try:
            self._salt, self._entries = self._parse()
        except Exception:
            self._fh.close()
            raise

    def _parse(self) -> tuple[int, dict[int, _Entry]]:  # pragma: no cover
        raise NotImplementedError

    # -- ModSource interface ------------------------------------------- #

    def has(self, path: str) -> bool:
        entry = self._entries.get(hash_path(path, self._salt))
        return entry is not None and not entry.is_directory and not entry.is_image

    def read_bytes(self, path: str) -> bytes:
        entry = self._entries.get(hash_path(path, self._salt))
        if entry is None or entry.is_directory:
            raise FileNotFoundError(path)
        if entry.is_image:
            raise HashFsError(f"packed texture entry not supported: {path}")
        return self._content(entry)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding, errors="replace")

    def close(self) -> None:
        self._fh.close()

    # -- archive walking (for full extraction) ------------------------- #

    def list_dir(self, path: str = ROOT) -> tuple[list[str], list[str]]:
        """Return (subdirectories, files) named in a directory listing entry."""
        entry = self._entries.get(hash_path(path, self._salt))
        if entry is None or not entry.is_directory:
            raise FileNotFoundError(path)
        return self._parse_listing(self._content(entry))

    def _parse_listing(self, blob: bytes) -> tuple[list[str], list[str]]:  # pragma: no cover
        raise NotImplementedError

    def iter_files(self) -> list[str]:
        """Every file path in the archive, walked from directory listings.

        Normally we walk from the root listing ``/``. Some archives omit it
        (locale.scs has listings for ``locale/...`` but none for ``/``), so we
        also seed the walk with the well-known SCS top-level directories and
        probe a few well-known root files. Listings that fail to read (a
        corrupt or manipulated entry) are skipped, not fatal.

        This is a pragmatic seed list, not a full deep scan: an archive that
        omits its root listing AND uses a non-standard top-level name would
        still be missed.
        """
        found: list[str] = []
        seen: set[str] = set()
        stack = [ROOT, *(f"/{name}" for name in _KNOWN_TOP_DIRS)]
        while stack:
            canon = "/" + stack.pop().strip("/")
            if canon in seen:
                continue
            seen.add(canon)
            try:
                subdirs, files = self.list_dir(canon)
            except (FileNotFoundError, HashFsError, zlib.error):
                continue
            base = "" if canon == ROOT else canon
            found.extend(f"{base}/{name}" for name in files)
            stack.extend(f"{base}/{name}" for name in subdirs)
        found.extend(f"/{name}" for name in _KNOWN_ROOT_FILES if self.has(name))
        return sorted(set(found))

    # -- internals ----------------------------------------------------- #

    def _content(self, entry: _Entry) -> bytes:
        self._fh.seek(entry.offset)
        if entry.is_compressed:
            return zlib.decompress(self._fh.read(entry.compressed_size))
        return self._fh.read(entry.size)

    def __enter__(self) -> _HashFsReaderBase:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class HashFsV1Reader(_HashFsReaderBase):
    """HashFS v1: flat 32-byte entry table, text directory listings."""

    _DIR_MARKER = "*"

    def _parse(self) -> tuple[int, dict[int, _Entry]]:
        header = self._fh.read(24)
        if len(header) < 24 or struct.unpack_from("<I", header, 0)[0] != MAGIC:
            raise HashFsError("not a HashFS archive")
        version = struct.unpack_from("<H", header, 4)[0]
        if version != 1:
            raise UnsupportedHashFsVersion(version)
        salt = struct.unpack_from("<H", header, 6)[0]
        if header[8:12].decode("ascii", errors="replace") != CITY_METHOD:
            raise HashFsError("unsupported hash method")
        num_entries = struct.unpack_from("<I", header, 12)[0]
        start_offset = struct.unpack_from("<Q", header, 16)[0]

        self._fh.seek(start_offset)
        table = self._fh.read(num_entries * 32)
        entries: dict[int, _Entry] = {}
        for i in range(num_entries):
            h, offset, flags, _crc, size, csize = struct.unpack_from("<QQIIII", table, i * 32)
            entries.setdefault(
                h,
                _Entry(
                    offset=offset,
                    size=size,
                    compressed_size=csize,
                    is_directory=bool(flags & 0x1),
                    is_compressed=bool(flags & 0x2),
                ),
            )
        return salt, entries

    def _parse_listing(self, blob: bytes) -> tuple[list[str], list[str]]:
        subdirs: list[str] = []
        files: list[str] = []
        text = blob.decode("utf-8", errors="replace")
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if not line:
                continue
            if line.startswith(self._DIR_MARKER):
                subdirs.append(line[1:])
            else:
                files.append(line)
        return subdirs, files


class HashFsV2Reader(_HashFsReaderBase):
    """HashFS v2: zlib entry + metadata tables, binary directory listings."""

    _DIR_MARKER = "/"

    def _parse(self) -> tuple[int, dict[int, _Entry]]:
        header = self._fh.read(49)
        if len(header) < 49 or struct.unpack_from("<I", header, 0)[0] != MAGIC:
            raise HashFsError("not a HashFS archive")
        version = struct.unpack_from("<H", header, 4)[0]
        if version != 2:
            raise UnsupportedHashFsVersion(version)
        salt = struct.unpack_from("<H", header, 6)[0]
        if header[8:12].decode("ascii", errors="replace") != CITY_METHOD:
            raise HashFsError("unsupported hash method")
        entry_table_len = struct.unpack_from("<I", header, 16)[0]
        metadata_table_len = struct.unpack_from("<I", header, 24)[0]
        entry_table_start = struct.unpack_from("<Q", header, 28)[0]
        metadata_table_start = struct.unpack_from("<Q", header, 36)[0]

        self._fh.seek(entry_table_start)
        entry_table = zlib.decompress(self._fh.read(entry_table_len))
        self._fh.seek(metadata_table_start)
        meta = zlib.decompress(self._fh.read(metadata_table_len))

        entries: dict[int, _Entry] = {}
        count = len(entry_table) // 16
        for i in range(count):
            h, meta_index, meta_count, _flags = struct.unpack_from("<QIHH", entry_table, i * 16)
            entry = _decode_v2_metadata(meta, meta_index, meta_count)
            if entry is not None:
                entries.setdefault(h, entry)
        return salt, entries

    def _parse_listing(self, blob: bytes) -> tuple[list[str], list[str]]:
        count = struct.unpack_from("<I", blob, 0)[0]
        lengths = blob[4 : 4 + count]
        pos = 4 + count
        subdirs: list[str] = []
        files: list[str] = []
        for length in lengths:
            name = blob[pos : pos + length].decode("utf-8", errors="replace")
            pos += length
            if name.startswith(self._DIR_MARKER):
                subdirs.append(name[1:])
            else:
                files.append(name)
        return subdirs, files


def _decode_v2_metadata(meta: bytes, meta_index: int, meta_count: int) -> _Entry | None:
    pos = meta_index * _V2_META_BLOCK
    chunk_type = meta[pos + 3]  # first chunk header: 3 index bytes + 1 type byte
    body = pos + meta_count * 4

    if chunk_type in (_CHUNK_PLAIN, _CHUNK_DIRECTORY):
        offset, size, csize, compressed = _decode_main_metadata(meta, body)
        return _Entry(offset, size, csize, chunk_type == _CHUNK_DIRECTORY, compressed)
    if chunk_type == _CHUNK_IMAGE:
        # 12-byte packed tobj/dds metadata precedes the main metadata.
        offset, size, csize, compressed = _decode_main_metadata(meta, body + 12)
        return _Entry(offset, size, csize, False, compressed, is_image=True)
    return None  # unimplemented chunk type - skip


def _decode_main_metadata(meta: bytes, pos: int) -> tuple[int, int, int, bool]:
    csize = (
        meta[pos] | (meta[pos + 1] << 8) | (meta[pos + 2] << 16) | ((meta[pos + 3] & 0x0F) << 24)
    )
    compressed = bool(meta[pos + 3] & 0x10)  # flags nibble, bit 4
    size = (
        meta[pos + 4]
        | (meta[pos + 5] << 8)
        | (meta[pos + 6] << 16)
        | ((meta[pos + 7] & 0x0F) << 24)
    )
    offset_block = struct.unpack_from("<I", meta, pos + 12)[0]
    return offset_block * _V2_BLOCK_SIZE, size, csize, compressed


def open_hashfs(path: Path | str) -> _HashFsReaderBase:
    """Open a HashFS archive, dispatching to the v1 or v2 reader."""
    with open(path, "rb") as fh:
        version = peek_version(fh)
    if version == 1:
        return HashFsV1Reader(path)
    if version == 2:
        return HashFsV2Reader(path)
    raise UnsupportedHashFsVersion(version)
