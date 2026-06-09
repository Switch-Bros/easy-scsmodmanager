from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from easy_scsmodmanager.services.scs_extractor import (
    UnsupportedArchive,
    extract_scs,
)


def _make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def test_extracts_every_file_to_folder(tmp_path: Path) -> None:
    src = _make_zip(
        tmp_path / "mod.zip",
        {"manifest.sii": b"manifest", "def/city.sii": b"city", "icon.jpg": b"jpg"},
    )
    dest = tmp_path / "out"
    result = extract_scs(src, dest)

    assert (result.extracted, result.failed, result.cancelled) == (3, 0, False)
    assert (dest / "manifest.sii").read_bytes() == b"manifest"
    assert (dest / "def" / "city.sii").read_bytes() == b"city"


def test_progress_reports_done_and_total(tmp_path: Path) -> None:
    src = _make_zip(tmp_path / "m.zip", {"a": b"1", "b": b"2"})
    seen: list[tuple[int, int]] = []
    extract_scs(src, tmp_path / "o", on_progress=lambda d, t: seen.append((d, t)))
    assert seen[-1] == (2, 2)


def test_cancel_stops_early(tmp_path: Path) -> None:
    src = _make_zip(tmp_path / "m.zip", {f"f{i}.txt": b"x" for i in range(10)})
    result = extract_scs(src, tmp_path / "o", should_cancel=lambda: True)
    assert result.cancelled
    assert result.extracted == 0


def test_path_traversal_entry_is_blocked(tmp_path: Path) -> None:
    src = _make_zip(tmp_path / "m.zip", {"../evil.txt": b"bad", "ok.txt": b"good"})
    dest = tmp_path / "out"
    result = extract_scs(src, dest)

    assert (dest / "ok.txt").read_bytes() == b"good"
    assert result.failed == 1
    assert not (tmp_path / "evil.txt").exists()


def test_unsupported_format_raises(tmp_path: Path) -> None:
    aem = tmp_path / "x.scs"
    aem.write_bytes(b"AEM!" + b"\x00" * 32)
    with pytest.raises(UnsupportedArchive):
        extract_scs(aem, tmp_path / "o")


def test_extract_hashfs_writes_dds_for_packed_textures(tmp_path: Path) -> None:
    import sys

    # reuse the v2 reader's builder for a tiny archive with one real packed texture
    sys.path.insert(0, str(Path(__file__).parent.parent / "test_integrations"))
    from test_hashfs_v2_reader import _image_archive

    fx = Path(__file__).parent.parent.parent / "fixtures" / "scs_textures"
    dest = tmp_path / "out"
    res = extract_scs(_image_archive(tmp_path), dest)

    dds = dest / "road.dds"
    assert dds.exists()
    assert dds.read_bytes() == (fx / "tex0.dds").read_bytes()
    assert res.failed == 0
    assert not (dest / "road.tobj").exists()  # rebuilt as .dds, not the raw .tobj
