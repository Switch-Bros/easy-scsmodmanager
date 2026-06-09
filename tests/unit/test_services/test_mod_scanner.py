from __future__ import annotations

import struct
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


def _mangle_fake_lock(path: Path) -> Path:
    # flip the central encryption bit + relabel local method as 1, like the
    # "protected" map mods do, leaving the deflate payload untouched
    raw = bytearray(path.read_bytes())
    pos = 0
    while (i := raw.find(b"PK\x03\x04", pos)) != -1:
        struct.pack_into("<H", raw, i + 8, 1)
        pos = i + 4
    pos = 0
    while (i := raw.find(b"PK\x01\x02", pos)) != -1:
        raw[i + 8] |= 0x01
        pos = i + 4
    path.write_bytes(bytes(raw))
    return path


def _aem_mod(path: Path, manifest_text: str) -> Path:
    # build a minimal AEM! container: manifest.sii raw-deflate, icon stored
    import zlib

    def rawdef(d: bytes) -> bytes:
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        return co.compress(d) + co.flush()

    path.parent.mkdir(parents=True, exist_ok=True)
    buf = bytearray()
    for name, content, comp in (
        ("manifest.sii", manifest_text.encode(), True),
        ("icon.jpg", b"\xff\xd8\xff\xe0img\xff\xd9", False),
    ):
        nb = name.encode("ascii")
        buf += b"AEM!" + b"\x00" * 8 + struct.pack("<I", len(nb)) + nb
        buf += rawdef(content) if comp else content
    path.write_bytes(bytes(buf))
    return path


def test_scan_mod_directory_reads_aem_container(tmp_path: Path) -> None:
    _aem_mod(tmp_path / "protected_map.scs", _full_manifest("AEM Map", "RuMapper"))

    mods = scan_mod_directory(tmp_path)

    assert len(mods) == 1
    assert mods[0].format == ScsFormat.AEM
    assert mods[0].error is None
    assert mods[0].manifest is not None
    assert mods[0].manifest.display_name == "AEM Map"
    assert mods[0].manifest.author == "RuMapper"


def test_scan_mod_directory_recovers_fake_locked_zip(tmp_path: Path) -> None:
    scs = tmp_path / "locked_map.scs"
    with zipfile.ZipFile(scs, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.sii", _full_manifest("Locked Map", "Mapper"))
        zf.writestr("icon.jpg", b"\xff\xd8\xfffake\xff\xd9")
    _mangle_fake_lock(scs)

    mods = scan_mod_directory(tmp_path)

    assert len(mods) == 1
    assert mods[0].format == ScsFormat.ZIP
    assert mods[0].error is None
    assert mods[0].manifest is not None
    assert mods[0].manifest.display_name == "Locked Map"
    assert mods[0].manifest.author == "Mapper"


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


def test_scan_mod_directory_calls_on_scan_per_mod(tmp_path: Path) -> None:
    _zip_mod(tmp_path / "mod_a.scs", _full_manifest("A", "x"))
    _zip_mod(tmp_path / "mod_b.scs", _full_manifest("B", "y"))

    seen: list[str] = []
    scan_mod_directory(tmp_path, on_scan=lambda p: seen.append(p.name))

    assert sorted(seen) == ["mod_a.scs", "mod_b.scs"]


def test_scan_game_install_threads_on_scan(tmp_path: Path) -> None:
    mod_dir = tmp_path / "mod"
    _zip_mod(mod_dir / "one.scs", _full_manifest("One", "x"))
    install = GameInstall(
        game=Game.ETS2,
        kind=InstallKind.LINUX_NATIVE,
        documents_dir=tmp_path,
        workshop_dir=None,
    )

    ticks: list[str] = []
    scan_game_install(install, on_scan=lambda p: ticks.append(p.name))

    assert ticks == ["one.scs"]


def test_map_and_defs_drops_directory_entries() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    files = ["def/", "def/vehicle/", "def/vehicle/truck.sii", "manifest.sii"]
    is_map, def_files = _map_and_defs(files)

    assert def_files == ("def/vehicle/truck.sii",)  # folders dropped, file kept
    assert is_map is False


def test_map_and_defs_keeps_physics_file_for_content_category() -> None:
    from easy_scsmodmanager.integrations.scs.content_category import content_category
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    files = ["def/", "def/vehicle/", "def/vehicle/physics/truck.sii"]
    _, def_files = _map_and_defs(files)

    # regression: filtering folders must not break physics detection
    assert content_category(def_files) == "physics"


def test_map_and_defs_strips_base_prefix_for_defs() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    _, def_files = _map_and_defs(["base/def/vehicle/x.sii", "manifest.sii"])
    assert def_files == ("def/vehicle/x.sii",)  # base/ stripped, seen as def/


def test_map_and_defs_base_map_is_detected_as_map() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    is_map, _ = _map_and_defs(["base/map/foo.mbd"])
    assert is_map is True


def test_map_and_defs_base_physics_classifies_as_physics() -> None:
    from easy_scsmodmanager.integrations.scs.content_category import content_category
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    _, def_files = _map_and_defs(["base/def/vehicle/physics/p.sii"])
    assert content_category(def_files) == "physics"


def test_map_and_defs_segment_guard_keeps_base_underscore() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs, _strip_base_prefix

    # only an exact "base" first segment is stripped, never "base_*"
    assert _strip_base_prefix("base_vehicle/def/z.sii") == "base_vehicle/def/z.sii"
    _, def_files = _map_and_defs(["base_vehicle/def/z.sii"])
    assert def_files == ()  # lives under base_vehicle/, not def/ -> not a def file


def test_map_and_defs_dedupes_root_and_base_collision() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    _, def_files = _map_and_defs(["def/a.sii", "base/def/a.sii"])
    assert def_files == ("def/a.sii",)  # same file once, no tooltip duplicate


def test_map_and_defs_drops_base_directory_entries() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    _, def_files = _map_and_defs(["base/", "base/def/", "def/", "base/def/x.sii"])
    assert def_files == ("def/x.sii",)  # directory entries dropped (#33)


def test_map_and_defs_plain_root_def_unchanged() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    is_map, def_files = _map_and_defs(["def/vehicle/truck.sii", "manifest.sii"])
    assert def_files == ("def/vehicle/truck.sii",)
    assert is_map is False


# --- §A dlc_ package gating (v1.4.0) ------------------------------------- #


def test_map_and_defs_strips_owned_dlc_prefix() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    files = ["dlc_toys/def/vehicle/x.sii", "manifest.sii"]
    _, owned = _map_and_defs(files, frozenset({"dlc_toys"}))
    assert owned == ("def/vehicle/x.sii",)  # owned -> mounts at root


def test_map_and_defs_keeps_unowned_dlc_out() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    _, def_files = _map_and_defs(["dlc_toys/def/vehicle/x.sii"], frozenset())
    assert def_files == ()  # not owned -> not mounted -> not a def file


def test_map_and_defs_dlc_fallback_ungated_when_owned_none() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    _, def_files = _map_and_defs(["dlc_toys/def/vehicle/x.sii"], None)
    assert def_files == ("def/vehicle/x.sii",)  # install unknown -> ungated


def test_map_and_defs_dlc_segment_guard() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs, _strip_dlc_prefix

    # "dlcfoo" has no underscore -> never treated as a dlc_ segment
    assert _strip_dlc_prefix("dlcfoo/def/x.sii", None) == "dlcfoo/def/x.sii"
    _, def_files = _map_and_defs(["dlcfoo/def/x.sii"], None)
    assert def_files == ()


def test_map_and_defs_base_and_dlc_dedupe() -> None:
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    # base/def/a and dlc_toys/def/a both normalise to def/a -> once
    files = ["base/def/a.sii", "dlc_toys/def/a.sii"]
    _, def_files = _map_and_defs(files, frozenset({"dlc_toys"}))
    assert def_files == ("def/a.sii",)


def test_owned_dlc_tokens_reads_dlc_scs_stems(tmp_path) -> None:
    from easy_scsmodmanager.services.mod_scanner import owned_dlc_tokens

    (tmp_path / "dlc_toys.scs").write_bytes(b"x")
    (tmp_path / "dlc_north.scs").write_bytes(b"x")
    (tmp_path / "base.scs").write_bytes(b"x")
    assert owned_dlc_tokens(tmp_path) == frozenset({"dlc_toys", "dlc_north"})
    assert owned_dlc_tokens(None) is None


def test_dlc_fingerprint_stable_and_sensitive() -> None:
    from easy_scsmodmanager.services.mod_scanner import dlc_fingerprint

    a = dlc_fingerprint(frozenset({"dlc_toys", "dlc_north"}))
    b = dlc_fingerprint(frozenset({"dlc_north", "dlc_toys"}))  # order irrelevant
    assert a == b
    assert dlc_fingerprint(frozenset({"dlc_toys"})) != a  # a purchase changes it
    assert dlc_fingerprint(None) == "none"


def test_pgrs_repro_conflict_only_when_dlc_owned() -> None:
    from easy_scsmodmanager.services.conflict_detect import find_conflicts
    from easy_scsmodmanager.services.mod_scanner import _map_and_defs

    listing = ["dlc_toys/def/vehicle/truck/accessory/curtain_f.dlc_toys.sii"]
    _, a_owned = _map_and_defs(listing, frozenset({"dlc_toys"}))
    _, b_owned = _map_and_defs(listing, frozenset({"dlc_toys"}))
    assert find_conflicts({"a": a_owned, "b": b_owned})  # owned -> conflict seen

    _, a_un = _map_and_defs(listing, frozenset())
    _, b_un = _map_and_defs(listing, frozenset())
    assert find_conflicts({"a": a_un, "b": b_un}) == {}  # unowned -> invisible


def test_scan_directory_threads_owned_dlc(tmp_path) -> None:
    from easy_scsmodmanager.services.mod_scanner import _scan_directory

    mod = tmp_path / "pgrs"
    (mod / "dlc_toys" / "def" / "vehicle").mkdir(parents=True)
    (mod / "manifest.sii").write_text(
        'SiiNunit\n{\nmod_package: .pgrs {\n display_name: "PGRS"\n}\n}\n'
    )
    (mod / "dlc_toys" / "def" / "vehicle" / "x.sii").write_text("x")

    result, _, _ = _scan_directory(mod, frozenset({"dlc_toys"}))
    assert "def/vehicle/x.sii" in result.def_files
    result_un, _, _ = _scan_directory(mod, frozenset())
    assert result_un.def_files == ()
