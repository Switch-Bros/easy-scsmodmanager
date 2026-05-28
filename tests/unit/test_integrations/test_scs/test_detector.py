from __future__ import annotations

from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.detector import ScsFormat, detect_format


def _write(tmp_path: Path, name: str, payload: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def test_detects_zip_by_local_file_header_magic(tmp_path: Path) -> None:
    scs = _write(tmp_path, "mod.scs", b"PK\x03\x04" + b"\x00" * 60)

    assert detect_format(scs) == ScsFormat.ZIP


def test_detects_hashfs_v1_by_magic_and_version(tmp_path: Path) -> None:
    payload = b"SCS#" + (1).to_bytes(2, "little") + b"\x00" * 26
    scs = _write(tmp_path, "mod.scs", payload)

    assert detect_format(scs) == ScsFormat.HASHFS_V1


def test_detects_hashfs_v2_by_magic_and_version(tmp_path: Path) -> None:
    payload = b"SCS#" + (2).to_bytes(2, "little") + b"\x00" * 26
    scs = _write(tmp_path, "mod.scs", payload)

    assert detect_format(scs) == ScsFormat.HASHFS_V2


def test_returns_unknown_for_unrecognised_magic(tmp_path: Path) -> None:
    scs = _write(tmp_path, "mod.scs", b"NOPE" + b"\x00" * 60)

    assert detect_format(scs) == ScsFormat.UNKNOWN


def test_returns_unknown_for_truncated_file(tmp_path: Path) -> None:
    scs = _write(tmp_path, "mod.scs", b"PK")

    assert detect_format(scs) == ScsFormat.UNKNOWN


def test_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        detect_format(tmp_path / "does-not-exist.scs")
