"""Reads ZIP-based .scs entries by scanning local file headers directly.

A few .scs files carry an unusual compression-method label and a set
encryption flag in the central directory, so Python's stdlib zipfile refuses
them even though the entry payload is ordinary raw-deflate. This reader scans
the local file headers itself and inflates each entry, which lets the scanner
read them. Used as a fallback after ZipScsReader.

Implements the ModSource surface (has / read_text / read_bytes / close).
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from types import TracebackType

ZIP_LOCAL = b"PK\x03\x04"
LOCAL_HEADER_FIXED = 30  # bytes before the variable-length name/extra fields
STORED = 0


class RawZipReader:
    """Tolerant ZIP reader that scans local headers and raw-inflates."""

    def __init__(self, scs_path: Path) -> None:
        self._raw = Path(scs_path).read_bytes()
        self._index = self._scan_local_headers(self._raw)

    @staticmethod
    def _scan_local_headers(raw: bytes) -> dict[str, tuple[int, int, int, int]]:
        # name -> (data_offset, comp_size, uncomp_size, method)
        out: dict[str, tuple[int, int, int, int]] = {}
        n = len(raw)
        pos = 0
        while True:
            i = raw.find(ZIP_LOCAL, pos)
            if i == -1 or i + LOCAL_HEADER_FIXED > n:
                break
            method = struct.unpack_from("<H", raw, i + 8)[0]
            comp, uncomp = struct.unpack_from("<II", raw, i + 18)
            name_len, extra_len = struct.unpack_from("<HH", raw, i + 26)
            name = raw[i + LOCAL_HEADER_FIXED : i + LOCAL_HEADER_FIXED + name_len]
            data_off = i + LOCAL_HEADER_FIXED + name_len + extra_len
            key = name.decode("utf-8", "replace")
            # first header wins; later duplicates are usually data descriptors
            out.setdefault(key, (data_off, comp, uncomp, method))
            pos = i + 4
        return out

    def has(self, path: str) -> bool:
        return path in self._index

    def read_bytes(self, path: str) -> bytes:
        entry = self._index.get(path)
        if entry is None:
            raise KeyError(path)
        off, comp, uncomp, method = entry
        if comp <= 0:
            # streamed entry (data descriptor) - we can't slice it reliably
            raise ValueError(f"no usable compressed size for {path}")
        blob = self._raw[off : off + comp]
        if method == STORED:
            return blob[:uncomp] if uncomp else blob
        try:
            return zlib.decompress(blob, -15)
        except zlib.error:
            # genuinely encrypted, or actually stored but mislabelled
            if comp == uncomp:
                return blob[:uncomp] if uncomp else blob
            raise

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding, errors="replace")

    def list_files(self, prefix: str = "") -> list[str]:
        if not prefix:
            return list(self._index)
        return [name for name in self._index if name.startswith(prefix)]

    def close(self) -> None:
        # bytes are held in memory, nothing to release
        self._raw = b""

    def __enter__(self) -> RawZipReader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
