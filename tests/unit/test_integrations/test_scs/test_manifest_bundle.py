from __future__ import annotations

from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.manifest_bundle import (
    MissingManifest,
    read_bundle,
)
from easy_scsmodmanager.integrations.scs.mod_source import DirectoryModSource


def _write_manifest(tmp_path: Path, body: str) -> None:
    (tmp_path / "manifest.sii").write_text(body, encoding="utf-8")


def _basic_manifest(icon: str = "", description_file: str = "") -> str:
    parts = [
        "SiiNunit",
        "{",
        "mod_package: .pkg",
        "{",
        '    display_name: "Demo Mod"',
        '    author: "Tester"',
        '    category[]: "truck"',
    ]
    if icon:
        parts.append(f'    icon: "{icon}"')
    if description_file:
        parts.append(f'    description_file: "{description_file}"')
    parts += ["}", "}", ""]
    return "\n".join(parts)


def test_read_bundle_returns_manifest_icon_and_description(tmp_path: Path) -> None:
    _write_manifest(tmp_path, _basic_manifest(icon="tandempack.jpg", description_file="fvinge.txt"))
    (tmp_path / "tandempack.jpg").write_bytes(b"\xff\xd8custom-icon")
    (tmp_path / "fvinge.txt").write_text("Custom description text", encoding="utf-8")

    bundle = read_bundle(DirectoryModSource(tmp_path))

    assert bundle.manifest.display_name == "Demo Mod"
    assert bundle.icon_bytes == b"\xff\xd8custom-icon"
    assert bundle.description_text == "Custom description text"


def test_read_bundle_falls_back_to_default_icon_names(tmp_path: Path) -> None:
    _write_manifest(tmp_path, _basic_manifest())
    (tmp_path / "icon.jpg").write_bytes(b"jpg")

    bundle = read_bundle(DirectoryModSource(tmp_path))

    assert bundle.icon_bytes == b"jpg"


def test_read_bundle_picks_mod_icon_jpg_when_manifest_does_not_set_icon(tmp_path: Path) -> None:
    _write_manifest(tmp_path, _basic_manifest())
    (tmp_path / "mod_icon.jpg").write_bytes(b"modicon")

    bundle = read_bundle(DirectoryModSource(tmp_path))

    assert bundle.icon_bytes == b"modicon"


def test_read_bundle_returns_none_icon_when_nothing_present(tmp_path: Path) -> None:
    _write_manifest(tmp_path, _basic_manifest())

    bundle = read_bundle(DirectoryModSource(tmp_path))

    assert bundle.icon_bytes is None


def test_read_bundle_falls_back_to_default_description_names(tmp_path: Path) -> None:
    _write_manifest(tmp_path, _basic_manifest())
    (tmp_path / "mod_description.txt").write_text("Hello desc", encoding="utf-8")

    bundle = read_bundle(DirectoryModSource(tmp_path))

    assert bundle.description_text == "Hello desc"


def test_read_bundle_truncates_oversize_description(tmp_path: Path) -> None:
    _write_manifest(tmp_path, _basic_manifest(description_file="huge.txt"))
    (tmp_path / "huge.txt").write_bytes(b"x" * 200_000)

    bundle = read_bundle(DirectoryModSource(tmp_path))

    assert bundle.description_text is not None
    assert len(bundle.description_text) == 64 * 1024


def test_read_bundle_raises_when_manifest_missing(tmp_path: Path) -> None:
    (tmp_path / "readme.txt").write_text("no manifest here")

    with pytest.raises(MissingManifest):
        read_bundle(DirectoryModSource(tmp_path))
