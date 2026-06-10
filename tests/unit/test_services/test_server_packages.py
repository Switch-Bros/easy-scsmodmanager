from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from easy_scsmodmanager.services.server_packages import (
    ServerPackagesError,
    read_server_packages,
    write_optional_flags,
)

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "server_packages"
_RPM = _FIXTURES / "rpm_server_packages.sii"
_PROMODS = _FIXTURES / "promods_server_packages.sii"


def _writable_copy(tmp_path: Path, fixture: Path, with_dat: bytes | None = None) -> Path:
    target = tmp_path / "server_packages.sii"
    shutil.copy2(fixture, target)
    if with_dat is not None:
        (tmp_path / "server_packages.dat").write_bytes(with_dat)
    return target


# --- reading (Sikay's real files) ---------------------------------------- #


def test_read_rpm_has_nine_mods_none_optional() -> None:
    pkg = read_server_packages(_RPM)
    assert len(pkg.mods) == 9
    assert all(not m.optional for m in pkg.mods)


def test_read_promods_has_one_optional() -> None:
    pkg = read_server_packages(_PROMODS)
    assert len(pkg.mods) == 23
    optional = [m.package_name for m in pkg.mods if m.optional]
    assert optional == ["promods-america-background-v15"]


def test_read_rejects_non_server_packages(tmp_path: Path) -> None:
    bad = tmp_path / "manifest.sii"
    bad.write_text('SiiNunit\n{\nmod_package: .m {\n display_name: "x"\n}\n}\n')
    with pytest.raises(ServerPackagesError):
        read_server_packages(bad)


# --- surgical writing ---------------------------------------------------- #


def test_surgical_flip_changes_only_one_token(tmp_path: Path) -> None:
    target = _writable_copy(tmp_path, _RPM)
    pkg = read_server_packages(target)
    before = target.read_bytes()
    first = pkg.mods[0]

    write_optional_flags(target, pkg.text, {first.nameless_id: True})

    after = target.read_bytes()
    assert read_server_packages(target).mods[0].optional is True
    assert after.count(b"\r\n") == before.count(b"\r\n")  # CRLF preserved
    # exactly one line differs, and only the bool token
    diffs = [
        (b, a) for b, a in zip(before.split(b"\r\n"), after.split(b"\r\n"), strict=True) if b != a
    ]
    assert diffs == [(b" optional_mod: false", b" optional_mod: true")]


def test_round_trip_promods_keeps_existing_optional(tmp_path: Path) -> None:
    target = _writable_copy(tmp_path, _PROMODS)
    pkg = read_server_packages(target)
    already = next(m for m in pkg.mods if m.optional)
    another = next(m for m in pkg.mods if not m.optional)

    write_optional_flags(target, pkg.text, {another.nameless_id: True})

    optional = {m.package_name for m in read_server_packages(target).mods if m.optional}
    assert optional == {already.package_name, another.package_name}


def test_blocker2_inserts_missing_optional_line(tmp_path: Path) -> None:
    # a block with no optional_mod line at all
    text = (
        "SiiNunit\r\n{\r\nserver_packages_info : _n.0 {\r\n version: 1\r\n}\r\n\r\n"
        'server_mod_detail : _n.1 {\r\n package_name: "X"\r\n mod_name: "Mod X"\r\n'
        " workshop_mod: false\r\n full_name: true\r\n}\r\n}\r\n"
    )
    target = tmp_path / "server_packages.sii"
    target.write_bytes(text.encode("utf-8"))
    pkg = read_server_packages(target)
    assert pkg.mods[0].optional is False

    write_optional_flags(target, pkg.text, {pkg.mods[0].nameless_id: True})
    out = target.read_bytes()
    # inserted right before full_name, same one-space indent, CRLF preserved
    assert b" optional_mod: true\r\n full_name: true" in out
    assert read_server_packages(target).mods[0].optional is True


def test_blocker2_false_on_missing_is_noop(tmp_path: Path) -> None:
    text = (
        "SiiNunit\r\n{\r\nserver_packages_info : _n.0 {\r\n version: 1\r\n}\r\n\r\n"
        'server_mod_detail : _n.1 {\r\n package_name: "X"\r\n full_name: true\r\n}\r\n}\r\n'
    )
    target = tmp_path / "server_packages.sii"
    target.write_bytes(text.encode("utf-8"))
    pkg = read_server_packages(target)

    write_optional_flags(target, pkg.text, {pkg.mods[0].nameless_id: False})
    assert "optional_mod" not in target.read_text()  # no spurious line added


def test_write_no_change_is_byte_identical(tmp_path: Path) -> None:
    target = _writable_copy(tmp_path, _RPM)
    pkg = read_server_packages(target)
    before = target.read_bytes()
    # ask for the values that are already there
    write_optional_flags(target, pkg.text, {m.nameless_id: m.optional for m in pkg.mods})
    assert target.read_bytes() == before


# --- blocker 1: single-file backup, .dat untouched ----------------------- #


def test_backup_is_single_file_and_dat_untouched(tmp_path: Path) -> None:
    dat_bytes = b"OPAQUE-BINARY-MAP-DATA"
    target = _writable_copy(tmp_path, _RPM, with_dat=dat_bytes)
    pkg = read_server_packages(target)

    write_optional_flags(target, pkg.text, {pkg.mods[0].nameless_id: True})

    backups = [
        p
        for p in tmp_path.iterdir()
        if p.name.startswith("server_packages.sii.") and p.suffix == ".bak"
    ]
    assert len(backups) == 1  # a single .sii backup, not a zip of the whole dir
    assert (tmp_path / "server_packages.dat").read_bytes() == dat_bytes  # never touched
    # no leftover temp file from the atomic write
    assert not any(p.suffix == ".tmp" for p in tmp_path.iterdir())


# --- package_name <-> nameless_id reconciliation ------------------------- #


def test_nameless_for_package_mapping(tmp_path: Path) -> None:
    pkg = read_server_packages(_PROMODS)
    mapping = pkg.nameless_for_package()
    assert len(mapping) == 23
    a_mod = pkg.mods[0]
    assert mapping[a_mod.package_name] == a_mod.nameless_id


def test_duplicate_package_name_does_not_raise(tmp_path: Path) -> None:
    text = (
        "SiiNunit\r\n{\r\nserver_packages_info : _n.0 {\r\n version: 1\r\n}\r\n\r\n"
        'server_mod_detail : _n.1 {\r\n package_name: "DUP"\r\n optional_mod: false\r\n}\r\n\r\n'
        'server_mod_detail : _n.2 {\r\n package_name: "DUP"\r\n optional_mod: false\r\n}\r\n}\r\n'
    )
    target = tmp_path / "server_packages.sii"
    target.write_bytes(text.encode("utf-8"))
    pkg = read_server_packages(target)
    pkg.nameless_for_package()  # logs, does not raise
    # the two rows stay individually addressable by their distinct nameless_ids
    assert {m.nameless_id for m in pkg.mods} == {"_n.1", "_n.2"}
    write_optional_flags(target, pkg.text, {"_n.2": True})
    flipped = {m.nameless_id for m in read_server_packages(target).mods if m.optional}
    assert flipped == {"_n.2"}
