"""Extract a whole .scs archive to a folder.

For modders who want to look inside the game's own archives (base.scs,
def.scs, ...) or any mod. Uses our own HashFS reader (v1/v2) and the stdlib
zip reader - no external tool. Per-file failures are collected rather than
aborting the run (some archives carry a corrupt or packed entry), and a
cancel callback lets the UI stop a long extraction (base.scs is ~9 GB).
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from easy_scsmodmanager.integrations.scs.detector import ScsFormat, detect_format
from easy_scsmodmanager.integrations.scs.hashfs_reader import open_hashfs

ProgressFn = Callable[[int, int], None]  # (done, total)
CancelFn = Callable[[], bool]


class UnsupportedArchive(Exception):
    """The archive format cannot be extracted (e.g. AEM, unknown)."""


@dataclass(frozen=True)
class ExtractResult:
    total: int
    extracted: int
    failed: int
    cancelled: bool
    failures: list[tuple[str, str]] = field(default_factory=list)


def extract_scs(
    scs_path: Path,
    dest_dir: Path,
    *,
    on_progress: ProgressFn | None = None,
    should_cancel: CancelFn | None = None,
) -> ExtractResult:
    """Extract every file in ``scs_path`` into ``dest_dir``.

    Dispatches on the container format. Raises :class:`UnsupportedArchive`
    for formats we cannot walk (AEM, unknown).
    """
    fmt = detect_format(scs_path)
    if fmt in (ScsFormat.HASHFS_V1, ScsFormat.HASHFS_V2):
        return _extract_hashfs(scs_path, dest_dir, on_progress, should_cancel)
    if fmt == ScsFormat.ZIP:
        return _extract_zip(scs_path, dest_dir, on_progress, should_cancel)
    raise UnsupportedArchive(f"cannot extract a {fmt.value} archive")


def _extract_hashfs(
    scs_path: Path,
    dest_dir: Path,
    on_progress: ProgressFn | None,
    should_cancel: CancelFn | None,
) -> ExtractResult:
    reader = open_hashfs(scs_path)
    try:
        paths = reader.iter_files()
        total = len(paths)
        extracted = failed = 0
        failures: list[tuple[str, str]] = []
        for done, entry in enumerate(paths, start=1):
            if should_cancel is not None and should_cancel():
                return ExtractResult(total, extracted, failed, True, failures)
            try:
                data = reader.read_bytes(entry)
                _write_file(dest_dir, entry.lstrip("/"), data)
                extracted += 1
            except Exception as exc:  # noqa: BLE001 - record and keep going
                failed += 1
                failures.append((entry, str(exc)))
            if on_progress is not None:
                on_progress(done, total)
        return ExtractResult(total, extracted, failed, False, failures)
    finally:
        reader.close()


def _extract_zip(
    scs_path: Path,
    dest_dir: Path,
    on_progress: ProgressFn | None,
    should_cancel: CancelFn | None,
) -> ExtractResult:
    with zipfile.ZipFile(scs_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        total = len(names)
        extracted = failed = 0
        failures: list[tuple[str, str]] = []
        for done, name in enumerate(names, start=1):
            if should_cancel is not None and should_cancel():
                return ExtractResult(total, extracted, failed, True, failures)
            try:
                _write_file(dest_dir, name, zf.read(name))
                extracted += 1
            except Exception as exc:  # noqa: BLE001 - record and keep going
                failed += 1
                failures.append((name, str(exc)))
            if on_progress is not None:
                on_progress(done, total)
        return ExtractResult(total, extracted, failed, False, failures)


def _write_file(dest_dir: Path, relative: str, data: bytes) -> None:
    target = (dest_dir / relative).resolve()
    root = dest_dir.resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"refusing path outside destination: {relative}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
