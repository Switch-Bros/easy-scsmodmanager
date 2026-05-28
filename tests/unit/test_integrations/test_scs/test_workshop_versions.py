from __future__ import annotations

from pathlib import Path

from easy_scsmodmanager.integrations.scs.workshop_versions import (
    VersionSlot,
    is_helper_slot_name,
    pick_active_slot,
    read_versions_sii,
)


def _write(tmp_path: Path, body: str) -> Path:
    (tmp_path / "versions.sii").write_text(body, encoding="utf-8")
    return tmp_path


def test_read_versions_sii_returns_empty_when_file_missing(tmp_path: Path) -> None:
    assert read_versions_sii(tmp_path) == []


def test_read_versions_sii_parses_single_universal_slot(tmp_path: Path) -> None:
    body = """
SiiNunit
{
package_version_info : .universal
{
    package_name: "universal"
}
}
"""
    _write(tmp_path, body)

    slots = read_versions_sii(tmp_path)

    assert slots == [VersionSlot(name="universal", compatible_versions=())]
    assert slots[0].is_default is True


def test_read_versions_sii_parses_multi_version_slots(tmp_path: Path) -> None:
    body = """
SiiNunit
{
package_version_info : .latest { package_name: "latest" }
package_version_info : .158_content {
    package_name: "158_content"
    compatible_versions[]: "1.58.*"
}
package_version_info : .157_content {
    package_name: "157_content"
    compatible_versions[]: "1.57.*"
}
}
"""
    _write(tmp_path, body)

    slots = read_versions_sii(tmp_path)

    assert [s.name for s in slots] == ["latest", "158_content", "157_content"]
    assert slots[1].compatible_versions == ("1.58.*",)


def test_read_versions_sii_handles_malformed_file(tmp_path: Path) -> None:
    _write(tmp_path, "not actually valid SiiNunit content")

    assert read_versions_sii(tmp_path) == []


def test_pick_active_slot_matches_compatible_version_first(tmp_path: Path) -> None:
    slots = [
        VersionSlot(name="latest"),
        VersionSlot(name="158_content", compatible_versions=("1.58.*",)),
        VersionSlot(name="157_content", compatible_versions=("1.57.*",)),
    ]

    assert pick_active_slot(slots, "1.58.3") == "158_content"
    assert pick_active_slot(slots, "1.57.0") == "157_content"


def test_pick_active_slot_falls_back_to_default_when_no_version_match(tmp_path: Path) -> None:
    slots = [
        VersionSlot(name="universal"),
        VersionSlot(name="158_content", compatible_versions=("1.58.*",)),
    ]

    assert pick_active_slot(slots, "1.99") == "universal"


def test_pick_active_slot_returns_first_when_no_default(tmp_path: Path) -> None:
    slots = [
        VersionSlot(name="158_content", compatible_versions=("1.58.*",)),
        VersionSlot(name="157_content", compatible_versions=("1.57.*",)),
    ]

    assert pick_active_slot(slots, "1.50") == "158_content"


def test_pick_active_slot_returns_none_for_empty(tmp_path: Path) -> None:
    assert pick_active_slot([], "1.59") is None


def test_is_helper_slot_name_recognises_known_patterns() -> None:
    assert is_helper_slot_name("150") is True
    assert is_helper_slot_name("153_content") is True
    assert is_helper_slot_name("downgrade_info_package") is True
    assert is_helper_slot_name("universal") is False
    assert is_helper_slot_name("latest") is False
    assert is_helper_slot_name("manifest") is False
