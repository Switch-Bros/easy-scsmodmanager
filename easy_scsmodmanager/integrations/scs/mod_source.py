"""Uniform read interface for the three mod-container layouts SCS uses.

ETS2 and ATS accept three different mod payload formats:

1. A ``.scs`` archive (ZIP or HashFS) sitting in ``mod/`` or in a
   workshop content directory.
2. A ``.zip`` archive with the same internal layout as a ZIP-based
   ``.scs`` (some workshop authors upload as ``.zip`` and SCS picks
   it up regardless of the extension).
3. An *unpacked* directory containing ``manifest.sii`` plus the
   internal tree (``def/``, ``material/``, ...) directly on disk.

Rather than scatter format checks throughout the scanner we route
every payload through the :class:`ModSource` protocol with read_text /
read_bytes / has so the rest of the code stays format-agnostic.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Protocol, runtime_checkable


@runtime_checkable
class ModSource(Protocol):
    """Minimal file-system-like interface a scanner needs."""

    def has(self, path: str) -> bool: ...
    def read_text(self, path: str, encoding: str = "utf-8") -> str: ...
    def read_bytes(self, path: str) -> bytes: ...
    def close(self) -> None: ...


class DirectoryModSource:
    """Reads from a directory that was extracted from a mod container.

    The constructor accepts the directory that contains ``manifest.sii``
    at its root. Mirrors the public methods of ZipScsReader so the
    scanner can treat both the same way.
    """

    def __init__(self, directory: Path) -> None:
        if not directory.is_dir():
            raise FileNotFoundError(f"not a directory: {directory}")
        self._root = directory

    def has(self, path: str) -> bool:
        return (self._root / path).is_file()

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding, errors="replace")

    def read_bytes(self, path: str) -> bytes:
        target = self._root / path
        if not target.is_file():
            raise FileNotFoundError(path)
        return target.read_bytes()

    def list_files(self, prefix: str = "") -> list[str]:
        out: list[str] = []
        for p in self._root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self._root).as_posix()
                if rel.startswith(prefix):
                    out.append(rel)
        return out

    def close(self) -> None:
        # No handle held - nothing to release.
        return None

    def __enter__(self) -> DirectoryModSource:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
