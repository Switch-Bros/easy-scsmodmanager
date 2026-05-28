from __future__ import annotations

import pytest

from easy_scsmodmanager.integrations.sii.parser import SiiParseError, SiiUnit, parse_sii


def test_parses_single_unit_with_string_property() -> None:
    text = """
SiiNunit
{
mod_package : .mod_package
{
    display_name: "Real Train Sounds ETS2"
}
}
"""
    units = parse_sii(text)

    assert len(units) == 1
    assert units[0] == SiiUnit(
        unit_class="mod_package",
        unit_name=".mod_package",
        properties={"display_name": "Real Train Sounds ETS2"},
    )


def test_string_property_handles_escaped_quotes() -> None:
    text = 'SiiNunit\n{\nmod_package: .x\n{\nname: "He said \\"hi\\""\n}\n}\n'

    units = parse_sii(text)

    assert units[0].properties["name"] == 'He said "hi"'


def test_array_property_aggregates_indexed_values() -> None:
    text = """
SiiNunit
{
mod_package: .mod_package
{
    category[]: "sound"
    category[]: "ai_traffic"
    category[]: "ui"
}
}
"""
    units = parse_sii(text)

    assert units[0].properties["category"] == ["sound", "ai_traffic", "ui"]


def test_integer_and_float_and_hex_values() -> None:
    text = """
SiiNunit
{
mod_package: .x
{
    count: 42
    rate: 1.5
    addr: 0x1F
    neg: -7
}
}
"""
    units = parse_sii(text)
    p = units[0].properties

    assert p == {"count": 42, "rate": 1.5, "addr": 0x1F, "neg": -7}


def test_boolean_values() -> None:
    text = """
SiiNunit
{
mod_package: .x
{
    enabled: true
    hidden: false
}
}
"""
    units = parse_sii(text)
    p = units[0].properties

    assert p == {"enabled": True, "hidden": False}


def test_hash_line_comments_are_ignored() -> None:
    text = """
# top-level comment
SiiNunit
{
mod_package: .x # trailing comment after value
{
    # full-line comment
    display_name: "Hello"
}
}
"""
    units = parse_sii(text)

    assert units[0].properties == {"display_name": "Hello"}


def test_double_slash_line_comments_are_ignored() -> None:
    text = """
// header comment
SiiNunit
{
mod_package: .x
{
    // comment line
    display_name: "Hi" // trailing
}
}
"""
    units = parse_sii(text)

    assert units[0].properties == {"display_name": "Hi"}


def test_multiple_units_in_one_file() -> None:
    text = """
SiiNunit
{
a : .first
{
    x: "1"
}
b : .second
{
    y: "2"
}
}
"""
    units = parse_sii(text)

    assert len(units) == 2
    assert units[0].unit_class == "a"
    assert units[0].unit_name == ".first"
    assert units[1].unit_class == "b"
    assert units[1].unit_name == ".second"


def test_realistic_manifest_sii() -> None:
    text = """SiiNunit
{
mod_package: .package
{
    package_version: "1.0.0"
    display_name: "Real Train Sounds ETS2"
    author: "Cip"
    category[]: "sound"
    category[]: "ai_traffic"
    description_file: "description.txt"
    icon: "icon.jpg"
    compatible_versions[]: "1.59.*"
}
}
"""
    units = parse_sii(text)
    p = units[0].properties

    assert p["package_version"] == "1.0.0"
    assert p["display_name"] == "Real Train Sounds ETS2"
    assert p["author"] == "Cip"
    assert p["category"] == ["sound", "ai_traffic"]
    assert p["description_file"] == "description.txt"
    assert p["icon"] == "icon.jpg"
    assert p["compatible_versions"] == ["1.59.*"]


def test_parses_file_with_utf8_bom_prefix() -> None:
    # SCS mod authors on Windows save manifest.sii with a UTF-8 BOM.
    # Real-world: ~6 of 313 mods in a representative ETS2 collection.
    text = "﻿SiiNunit\n{\nmod_package: .x\n{\ndisplay_name: \"WithBOM\"\n}\n}\n"

    units = parse_sii(text)

    assert units[0].properties["display_name"] == "WithBOM"


def test_string_decodes_hex_byte_escapes_into_utf8() -> None:
    # SCS writes non-ASCII chars as \xNN byte escapes. The bytes form
    # valid UTF-8 once recombined, e.g. \xe2\x98\x86 == "☆".
    text = 'SiiNunit\n{\nx: .x\n{\nname: "\\xe2\\x98\\x86Becky"\n}\n}\n'

    units = parse_sii(text)

    assert units[0].properties["name"] == "☆Becky"


def test_string_leaves_pure_latin1_bytes_alone_when_not_valid_utf8() -> None:
    # \xff alone is not a valid UTF-8 start byte. Keep the raw char.
    text = 'SiiNunit\n{\nx: .x\n{\nname: "\\xff"\n}\n}\n'

    units = parse_sii(text)

    assert units[0].properties["name"] == "ÿ"


def test_indexed_array_property_aggregates_in_order() -> None:
    # profile.sii uses indexed arrays for active_mods
    text = """
SiiNunit
{
profile: .profile_id
{
    active_mods: 3
    active_mods[0]: "low_prio|Low"
    active_mods[1]: "mid_prio|Mid"
    active_mods[2]: "high_prio|High"
}
}
"""
    units = parse_sii(text)

    assert units[0].properties["active_mods"] == [
        "low_prio|Low",
        "mid_prio|Mid",
        "high_prio|High",
    ]


def test_indexed_array_handles_non_sequential_indices() -> None:
    text = """
SiiNunit
{
x: .x
{
    items[2]: "third"
    items[0]: "first"
    items[1]: "second"
}
}
"""
    units = parse_sii(text)

    assert units[0].properties["items"] == ["first", "second", "third"]


def test_raises_on_missing_siinunit_header() -> None:
    text = "{\nmod_package: .x\n{\n}\n}\n"

    with pytest.raises(SiiParseError):
        parse_sii(text)


def test_raises_on_unterminated_string() -> None:
    text = 'SiiNunit\n{\nx: .x\n{\nname: "no end\n}\n}\n'

    with pytest.raises(SiiParseError):
        parse_sii(text)
