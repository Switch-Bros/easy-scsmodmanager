"""Unit tests for the shared conflict formatter.

The tooltip, the dialog and the saved log all render through this module, so
the row format and the severity headers only exist once. Pure text, no Qt.
"""

from __future__ import annotations

from easy_scsmodmanager.services.conflict_detect import FrequentShare, ModOverride, Severity
from easy_scsmodmanager.ui.conflict_text import (
    ReportEntry,
    frequent_lines,
    mod_block,
    override_lines,
    report_text,
)
from easy_scsmodmanager.utils.i18n import t


def _override(count: int, *, severity: Severity = Severity.PARTIAL) -> ModOverride:
    lost = tuple((f"def/x{i}.sii", "winner") for i in range(count))
    return ModOverride(severity=severity, lost=lost)


def test_override_lines_without_limit_returns_everything() -> None:
    lines, rest = override_lines(_override(5), {})

    assert rest == 0
    assert len(lines) == 6  # header + 5 rows


def test_override_lines_caps_and_reports_the_remainder() -> None:
    lines, rest = override_lines(_override(5), {}, limit=2)

    assert rest == 3
    assert len(lines) == 3  # header + 2 rows
    # the caller decides whether to append the "more" line, not us
    assert t("conflict.tooltip.more", count=3) not in lines


def test_full_and_partial_use_their_own_header() -> None:
    full, _ = override_lines(_override(1, severity=Severity.FULL), {})
    partial, _ = override_lines(_override(1, severity=Severity.PARTIAL), {})

    assert full[0] == t("conflict.tooltip.header_full")
    assert partial[0] == t("conflict.tooltip.header_partial")


def test_winner_is_resolved_through_the_display_map() -> None:
    lines, _ = override_lines(_override(1), {"winner": "Better Weather"})

    assert "Better Weather" in lines[1]


def test_unknown_winner_falls_back_to_the_raw_name() -> None:
    lines, _ = override_lines(_override(1), {})

    assert "winner" in lines[1]


def test_frequent_lines_lead_depends_on_also() -> None:
    share = FrequentShare((("def/physics.sii", 9),))

    with_also, _ = frequent_lines(share, also=True)
    standalone, _ = frequent_lines(share, also=False)

    assert with_also[0] == t("conflict.tooltip.frequent_also")
    assert standalone[0] == t("conflict.tooltip.header_frequent")


def test_frequent_lines_carry_the_owner_count() -> None:
    share = FrequentShare((("def/physics.sii", 9),))

    lines, rest = frequent_lines(share, also=False)

    assert rest == 0
    assert "def/physics.sii" in lines[1]
    assert "9" in lines[1]


def test_frequent_lines_cap_like_the_override_block() -> None:
    share = FrequentShare(tuple((f"def/p{i}.sii", 9) for i in range(5)))

    lines, rest = frequent_lines(share, also=False, limit=2)

    assert rest == 3
    assert len(lines) == 3


def test_mod_block_starts_with_the_display_name_and_stays_uncapped() -> None:
    block = mod_block("Realistic Weather", _override(20), None, {})

    assert block[0] == "Realistic Weather"
    assert len(block) == 22  # name + header + 20 rows


def test_mod_block_joins_override_and_frequent() -> None:
    share = FrequentShare((("def/physics.sii", 9),))

    block = mod_block("Some Mod", _override(2), share, {})

    assert t("conflict.tooltip.frequent_also") in block
    assert t("conflict.tooltip.header_frequent") not in block


def test_report_text_header_carries_context_and_count() -> None:
    entries = [
        ReportEntry(name="a", display_name="Mod A", override=_override(2), frequent=None),
        ReportEntry(name="b", display_name="Mod B", override=_override(1), frequent=None),
    ]

    text = report_text(
        entries,
        {},
        version="1.6.1",
        game="ETS2",
        profile="My Profile",
        generated="2026-08-17 12:00",
    )

    assert "1.6.1" in text
    assert "ETS2" in text
    assert "My Profile" in text
    assert "2026-08-17 12:00" in text
    assert "Total mods with conflicts: 2" in text
    assert "Mod A" in text
    assert "Mod B" in text


def test_report_text_survives_an_empty_report() -> None:
    text = report_text(
        [], {}, version="1.6.1", game="ETS2", profile="P", generated="2026-08-17 12:00"
    )

    assert "Total mods with conflicts: 0" in text


def test_report_text_carries_no_glyphs() -> None:
    # the saved log is plain text; severity is in the header wording already
    entries = [
        ReportEntry(
            name="a",
            display_name="Mod A",
            override=_override(1, severity=Severity.FULL),
            frequent=FrequentShare((("def/p.sii", 9),)),
        )
    ]

    text = report_text(
        entries, {}, version="1.6.1", game="ETS2", profile="P", generated="2026-08-17 12:00"
    )

    assert "⊘" not in text
    assert "⚠" not in text
