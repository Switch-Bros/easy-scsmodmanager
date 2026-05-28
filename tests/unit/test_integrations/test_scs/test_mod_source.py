from __future__ import annotations

from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.mod_source import DirectoryModSource


def test_directory_source_reads_existing_file(tmp_path: Path) -> None:
    (tmp_path / "manifest.sii").write_text("SiiNunit\n")
    with DirectoryModSource(tmp_path) as src:
        assert src.has("manifest.sii") is True
        assert src.read_text("manifest.sii") == "SiiNunit\n"


def test_directory_source_handles_nested_paths(tmp_path: Path) -> None:
    (tmp_path / "def").mkdir()
    (tmp_path / "def" / "cargo.sii").write_text("foo")
    with DirectoryModSource(tmp_path) as src:
        assert src.has("def/cargo.sii") is True
        assert src.read_text("def/cargo.sii") == "foo"


def test_directory_source_has_returns_false_for_missing(tmp_path: Path) -> None:
    with DirectoryModSource(tmp_path) as src:
        assert src.has("absent.sii") is False


def test_directory_source_read_bytes_returns_raw(tmp_path: Path) -> None:
    (tmp_path / "icon.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    with DirectoryModSource(tmp_path) as src:
        assert src.read_bytes("icon.jpg") == b"\xff\xd8\xff\xe0"


def test_directory_source_read_bytes_raises_for_missing(tmp_path: Path) -> None:
    with DirectoryModSource(tmp_path) as src, pytest.raises(FileNotFoundError):
        src.read_bytes("nope.sii")


def test_directory_source_rejects_non_directory(tmp_path: Path) -> None:
    target = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        DirectoryModSource(target)
