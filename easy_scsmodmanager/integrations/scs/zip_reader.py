from __future__ import annotations

import zipfile
from pathlib import Path
from types import TracebackType


class ZipScsReader:
    def __init__(self, scs_path: Path) -> None:
        self._zip = zipfile.ZipFile(scs_path, "r")

    def __enter__(self) -> ZipScsReader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def read_bytes(self, path: str) -> bytes:
        return self._zip.read(path)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding)

    def has(self, path: str) -> bool:
        try:
            self._zip.getinfo(path)
        except KeyError:
            return False
        return True

    def list_files(self, prefix: str = "") -> list[str]:
        names = self._zip.namelist()
        if not prefix:
            return list(names)
        return [n for n in names if n.startswith(prefix)]

    def close(self) -> None:
        self._zip.close()
