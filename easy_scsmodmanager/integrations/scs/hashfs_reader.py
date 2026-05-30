"""Pure-Python reader for HashFS (.scs) archives - the ``SCS#`` container.

Replaces the external sk-zk/Extractor binary for HashFS reads so the app is
self-contained on every platform (AppImage, deb, AUR, exe, ...). Ported from
TruckLib.HashFs (sk-zk).

This module covers HashFS **v1**; v2 has a different entry/metadata layout and
lives separately. Both expose the same reader interface.

A reader offers two things:

* the :class:`ModSource` interface (``has`` / ``read_text`` / ``read_bytes``)
  the scanner uses to pull ``manifest.sii`` + icon, and
* ``list_dir`` / ``iter_files`` to walk the whole archive, which is what a
  full "extract this .scs to a folder" feature needs.
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

_HEADER_V1_SIZE = 24
_ENTRY_V1_SIZE = 32

_FLAG_DIRECTORY = 0x1
_FLAG_COMPRESSED = 0x2


class HashFsError(Exception):
    """The file is not a HashFS archive we can read."""


class UnsupportedHashFsVersion(HashFsError):
    def __init__(self, version: int) -> None:
        super().__init__(f"Unsupported HashFS version {version}")
        self.version = version


@dataclass(frozen=True)
class _EntryV1:
    hash: int
    offset: int
    flags: int
    size: int
    compressed_size: int

    @property
    def is_directory(self) -> bool:
        return bool(self.flags & _FLAG_DIRECTORY)

    @property
    def is_compressed(self) -> bool:
        return bool(self.flags & _FLAG_COMPRESSED)


def peek_version(fh: object) -> int:
    """Read the HashFS version from an open binary file (validates magic)."""
    head = fh.read(6)  # type: ignore[attr-defined]
    fh.seek(0)  # type: ignore[attr-defined]
    if len(head) < 6 or struct.unpack_from("<I", head, 0)[0] != MAGIC:
        raise HashFsError("not a HashFS archive")
    return struct.unpack_from("<H", head, 4)[0]


class HashFsV1Reader:
    """Reads files from a HashFS v1 archive, addressed by path."""

    def __init__(self, path: Path | str) -> None:
        self._fh = open(path, "rb")  # noqa: SIM115 - closed in close()/__exit__
        try:
            self._salt, self._entries = _parse_v1(self._fh)
        except Exception:
            self._fh.close()
            raise

    # -- ModSource interface ------------------------------------------- #

    def has(self, path: str) -> bool:
        entry = self._entries.get(hash_path(path, self._salt))
        return entry is not None and not entry.is_directory

    def read_bytes(self, path: str) -> bytes:
        entry = self._entries.get(hash_path(path, self._salt))
        if entry is None or entry.is_directory:
            raise FileNotFoundError(path)
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
        subdirs: list[str] = []
        files: list[str] = []
        text = self._content(entry).decode("utf-8", errors="replace")
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if not line:
                continue
            if line.startswith("*"):
                subdirs.append(line[1:])
            else:
                files.append(line)
        return subdirs, files

    def iter_files(self) -> list[str]:
        """Every file path in the archive, walked from the root listing."""
        found: list[str] = []
        stack = [ROOT]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            try:
                subdirs, files = self.list_dir(current)
            except FileNotFoundError:
                continue
            base = "" if current == ROOT else current
            found.extend(f"{base}/{name}" for name in files)
            stack.extend(f"{base}/{name}" for name in subdirs)
        return found

    # -- internals ----------------------------------------------------- #

    def _content(self, entry: _EntryV1) -> bytes:
        self._fh.seek(entry.offset)
        if entry.is_compressed:
            return zlib.decompress(self._fh.read(entry.compressed_size))
        return self._fh.read(entry.size)

    def __enter__(self) -> HashFsV1Reader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def _parse_v1(fh: object) -> tuple[int, dict[int, _EntryV1]]:
    header = fh.read(_HEADER_V1_SIZE)  # type: ignore[attr-defined]
    if len(header) < _HEADER_V1_SIZE or struct.unpack_from("<I", header, 0)[0] != MAGIC:
        raise HashFsError("not a HashFS archive")
    version = struct.unpack_from("<H", header, 4)[0]
    if version != 1:
        raise UnsupportedHashFsVersion(version)
    salt = struct.unpack_from("<H", header, 6)[0]
    method = header[8:12].decode("ascii", errors="replace")
    if method != CITY_METHOD:
        raise HashFsError(f"unsupported hash method {method!r}")
    num_entries = struct.unpack_from("<I", header, 12)[0]
    start_offset = struct.unpack_from("<Q", header, 16)[0]

    fh.seek(start_offset)  # type: ignore[attr-defined]
    table = fh.read(num_entries * _ENTRY_V1_SIZE)  # type: ignore[attr-defined]
    entries: dict[int, _EntryV1] = {}
    for i in range(num_entries):
        h, offset, flags, _crc, size, csize = struct.unpack_from(
            "<QQIIII", table, i * _ENTRY_V1_SIZE
        )
        # First entry wins on hash collisions (matches TruckLib).
        entries.setdefault(h, _EntryV1(h, offset, flags, size, csize))
    return salt, entries
