"""Reads the AEM! .scs container layout.

A sequential format that generic parsers miss (no SCS#, no ZIP header).
Layout, repeated to EOF:

    [AEM!][zero padding][uint32 name_len LE][name][content]

AEM! is a separator, so an entry's content runs to the next valid header.
Textures/images are stored verbatim; .sii files (incl. manifest.sii) are
raw-deflate. We index by name once and inflate on read.

Implements the ModSource surface (has / read_text / read_bytes / close).
"""

from __future__ import annotations

import zlib
from pathlib import Path
from types import TracebackType

AEM_MAGIC = b"AEM!"
MAX_NAME_LEN = 512


class AemReader:
    """Sequential reader for the AEM! mod container."""

    def __init__(self, scs_path: Path) -> None:
        self._raw = Path(scs_path).read_bytes()
        self._index = self._build_index(self._raw)

    @staticmethod
    def _build_index(raw: bytes) -> dict[str, bytes]:
        # Only an AEM! that is followed by the zero pad + a plausible name_len +
        # an ASCII path counts as an entry boundary. A stray 41 45 4D 21 inside
        # a texture won't match, so it can't truncate the real entry's content.
        headers = []
        pos = 0
        while True:
            i = raw.find(AEM_MAGIC, pos)
            if i == -1:
                break
            parsed = AemReader._parse_header(raw, i)
            if parsed is not None:
                headers.append((i, *parsed))  # (mark, name, content_start)
            pos = i + 4

        out: dict[str, bytes] = {}
        for idx, (_, name, content_start) in enumerate(headers):
            content_end = headers[idx + 1][0] if idx + 1 < len(headers) else len(raw)
            out.setdefault(name, raw[content_start:content_end])
        return out

    @staticmethod
    def _parse_header(raw: bytes, mark: int) -> tuple[str, int] | None:
        n = len(raw)
        j = mark + 4
        while j < n and raw[j] == 0:  # skip the reserved zero pad
            j += 1
        if j + 4 > n:
            return None
        name_len = int.from_bytes(raw[j : j + 4], "little")
        if not 1 <= name_len <= MAX_NAME_LEN or j + 4 + name_len > n:
            return None
        try:
            name = raw[j + 4 : j + 4 + name_len].decode("ascii")
        except UnicodeDecodeError:
            return None
        if not name.isprintable():
            return None
        return name, j + 4 + name_len

    def has(self, path: str) -> bool:
        return path in self._index

    def read_bytes(self, path: str) -> bytes:
        content = self._index.get(path)
        if content is None:
            raise KeyError(path)
        # .sii are raw-deflate, images/textures are stored. Try inflate and
        # fall back to the raw bytes (a stored jpeg errors out immediately).
        try:
            out = zlib.decompressobj(-15).decompress(content)
            if out:
                return out
        except zlib.error:
            pass
        return content

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding, errors="replace")

    def list_files(self, prefix: str = "") -> list[str]:
        if not prefix:
            return list(self._index)
        return [name for name in self._index if name.startswith(prefix)]

    def close(self) -> None:
        self._raw = b""

    def __enter__(self) -> AemReader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
