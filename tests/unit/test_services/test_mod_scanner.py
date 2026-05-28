from __future__ import annotations

import zipfile
from pathlib import Path

from easy_scsmodmanager.core.game_paths import Game, GameInstall, InstallKind
from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_scanner import (
    scan_game_install,
    scan_mod_directory,
    scan_workshop_directory,
)


def _zip_mod(path: Path, manifest_text: str | None = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if manifest_text is not None:
            zf.writestr("manifest.sii", manifest_text)
        else:
            # Empty zips have only the EOCD header so detect_format would
            # return UNKNOWN. Insert a dummy entry so we still test the
            # "valid zip without manifest" branch.
            zf.writestr("readme.txt", "intentionally missing manifest")
    return path


def _hashfs_mod(path: Path, version: int = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SCS#" + version.to_bytes(2, "little") + b"\x00" * 26)
    return path


def _full_manifest(display_name: str = "Test Mod", author: str = "Tester") -> str:
    return (
        "SiiNunit\n"
        "{\n"
        "mod_package: .pkg\n"
        "{\n"
        f'    display_name: "{display_name}"\n'
        f'    author: "{author}"\n'
        '    category[]: "sound"\n'
        "}\n"
        "}\n"
    )


def test_scan_mod_directory_returns_empty_for_empty_dir(tmp_path: Path) -> None:
    assert scan_mod_directory(tmp_path) == []


def test_scan_mod_directory_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    assert scan_mod_directory(tmp_path / "does-not-exist") == []


def test_scan_mod_directory_ignores_files_with_unrelated_extensions(tmp_path: Path) -> None:
    # Non-archive files (.txt, .png, ...) are skipped even when they live
    # next to mod files. .scs and .zip get picked up; this test guards
    # everything else.
    (tmp_path / "readme.txt").write_text("hi")
    (tmp_path / "preview.png").write_bytes(b"\x89PNG")
    (tmp_path / "_metadata.json").write_text("{}")

    assert scan_mod_directory(tmp_path) == []


def test_scan_mod_directory_parses_zip_with_manifest(tmp_path: Path) -> None:
    scs = _zip_mod(tmp_path / "mod_a.scs", _full_manifest("Mod Alpha", "Alice"))

    mods = scan_mod_directory(tmp_path)

    assert len(mods) == 1
    assert mods[0].path == scs
    assert mods[0].format == ScsFormat.ZIP
    assert mods[0].error is None
    assert mods[0].manifest is not None
    assert mods[0].manifest.display_name == "Mod Alpha"
    assert mods[0].manifest.author == "Alice"
    assert mods[0].manifest.categories == ("sound",)


def test_scan_mod_directory_zip_without_manifest_marks_error(tmp_path: Path) -> None:
    scs = _zip_mod(tmp_path / "no_manifest.scs", manifest_text=None)

    mods = scan_mod_directory(tmp_path)

    assert len(mods) == 1
    assert mods[0].path == scs
    assert mods[0].format == ScsFormat.ZIP
    assert mods[0].manifest is None
    assert mods[0].error is not None
    assert "manifest" in mods[0].error.lower()


def test_scan_mod_directory_hashfs_mod_records_format_without_manifest(tmp_path: Path) -> None:
    _hashfs_mod(tmp_path / "modern.scs", version=2)

    mods = scan_mod_directory(tmp_path)

    assert len(mods) == 1
    assert mods[0].format == ScsFormat.HASHFS_V2
    assert mods[0].manifest is None
    assert mods[0].error is not None
    assert "hashfs" in mods[0].error.lower()


def test_scan_mod_directory_unknown_format_records_error(tmp_path: Path) -> None:
    scs = tmp_path / "junk.scs"
    scs.write_bytes(b"GARBAGE_HEADER")

    mods = scan_mod_directory(tmp_path)

    assert len(mods) == 1
    assert mods[0].format == ScsFormat.UNKNOWN
    assert mods[0].manifest is None
    assert mods[0].error is not None


def test_scan_mod_directory_handles_multiple_files_sorted_by_name(tmp_path: Path) -> None:
    _zip_mod(tmp_path / "b_mod.scs", _full_manifest("B"))
    _zip_mod(tmp_path / "a_mod.scs", _full_manifest("A"))

    mods = scan_mod_directory(tmp_path)

    assert [m.path.name for m in mods] == ["a_mod.scs", "b_mod.scs"]


def test_scan_workshop_directory_descends_one_level_into_workshop_id_dirs(
    tmp_path: Path,
) -> None:
    _zip_mod(tmp_path / "12345" / "first.scs", _full_manifest("First"))
    _zip_mod(tmp_path / "67890" / "second.scs", _full_manifest("Second"))
    # files directly under workshop dir should be ignored
    (tmp_path / "stray.scs").write_bytes(b"PK\x03\x04")

    mods = scan_workshop_directory(tmp_path)

    names = {m.manifest.display_name for m in mods if m.manifest}
    assert names == {"First", "Second"}


def test_scan_workshop_directory_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert scan_workshop_directory(tmp_path / "no_workshop") == []


def test_scan_game_install_combines_mod_and_workshop(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    workshop = tmp_path / "workshop"
    _zip_mod(docs / "mod" / "local.scs", _full_manifest("Local Mod"))
    _zip_mod(workshop / "111" / "wsm.scs", _full_manifest("Workshop Mod"))

    install = GameInstall(
        game=Game.ETS2,
        kind=InstallKind.PROTON,
        documents_dir=docs,
        workshop_dir=workshop,
    )

    mods = scan_game_install(install)

    display_names = {m.manifest.display_name for m in mods if m.manifest}
    assert display_names == {"Local Mod", "Workshop Mod"}


def test_scan_game_install_skips_workshop_when_install_has_no_workshop_dir(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    _zip_mod(docs / "mod" / "local.scs", _full_manifest("Only Local"))

    install = GameInstall(
        game=Game.ETS2,
        kind=InstallKind.LINUX_NATIVE,
        documents_dir=docs,
        workshop_dir=None,
    )

    mods = scan_game_install(install)

    assert len(mods) == 1
    assert mods[0].manifest is not None
    assert mods[0].manifest.display_name == "Only Local"
