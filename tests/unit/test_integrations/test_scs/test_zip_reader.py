from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.zip_reader import ZipScsReader


def _make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries.items():
            zf.writestr(name, payload)
    return path


def test_read_text_decodes_utf8_entry(tmp_path: Path) -> None:
    scs = _make_zip(tmp_path / "mod.scs", {"manifest.sii": "SiiNunit\n{}\n".encode()})

    with ZipScsReader(scs) as reader:
        assert reader.read_text("manifest.sii") == "SiiNunit\n{}\n"


def test_read_bytes_returns_raw_bytes(tmp_path: Path) -> None:
    payload = b"\xff\xd8\xff\xe0fake-jpeg"
    scs = _make_zip(tmp_path / "mod.scs", {"icon.jpg": payload})

    with ZipScsReader(scs) as reader:
        assert reader.read_bytes("icon.jpg") == payload


def test_has_returns_true_for_existing_entry(tmp_path: Path) -> None:
    scs = _make_zip(tmp_path / "mod.scs", {"manifest.sii": b"x"})

    with ZipScsReader(scs) as reader:
        assert reader.has("manifest.sii") is True


def test_has_returns_false_for_missing_entry(tmp_path: Path) -> None:
    scs = _make_zip(tmp_path / "mod.scs", {"manifest.sii": b"x"})

    with ZipScsReader(scs) as reader:
        assert reader.has("does-not-exist") is False


def test_list_files_without_prefix_returns_all(tmp_path: Path) -> None:
    scs = _make_zip(
        tmp_path / "mod.scs",
        {"manifest.sii": b"x", "def/vehicle.sii": b"y", "icon.jpg": b"z"},
    )

    with ZipScsReader(scs) as reader:
        assert sorted(reader.list_files()) == sorted(
            ["manifest.sii", "def/vehicle.sii", "icon.jpg"]
        )


def test_list_files_filters_by_prefix(tmp_path: Path) -> None:
    scs = _make_zip(
        tmp_path / "mod.scs",
        {"manifest.sii": b"x", "def/vehicle.sii": b"y", "def/sound.sii": b"y2"},
    )

    with ZipScsReader(scs) as reader:
        assert sorted(reader.list_files("def/")) == sorted(
            ["def/vehicle.sii", "def/sound.sii"]
        )


def test_context_manager_closes_handle(tmp_path: Path) -> None:
    scs = _make_zip(tmp_path / "mod.scs", {"manifest.sii": b"x"})

    with ZipScsReader(scs) as reader:
        pass

    # After context exit, further reads must raise
    with pytest.raises((ValueError, OSError)):
        reader.read_bytes("manifest.sii")


def test_raises_for_non_zip_file(tmp_path: Path) -> None:
    not_a_zip = tmp_path / "broken.scs"
    not_a_zip.write_bytes(b"this is not a zip at all")

    with pytest.raises(zipfile.BadZipFile):
        ZipScsReader(not_a_zip)


def test_raises_keyerror_for_missing_read(tmp_path: Path) -> None:
    scs = _make_zip(tmp_path / "mod.scs", {"manifest.sii": b"x"})

    with ZipScsReader(scs) as reader:
        with pytest.raises(KeyError):
            reader.read_bytes("nope.sii")
