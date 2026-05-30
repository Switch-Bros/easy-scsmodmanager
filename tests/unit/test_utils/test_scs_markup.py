from __future__ import annotations

from easy_scsmodmanager.utils.scs_markup import SCS_COLORS, scs_markup_to_html


def test_empty_string() -> None:
    assert scs_markup_to_html("") == ""


def test_plain_text_without_tags_is_unchanged() -> None:
    assert scs_markup_to_html("just text") == "just text"


def test_single_tag_colors_the_rest() -> None:
    out = scs_markup_to_html("[orange]Ourense Mod by Moreira")
    assert out == '<span style="color:#FFAE00">Ourense Mod by Moreira</span>'


def test_text_before_first_tag_keeps_default_color() -> None:
    out = scs_markup_to_html("by [blue]Author")
    assert out == 'by <span style="color:#12ABE5">Author</span>'


def test_multiple_tags_in_sequence() -> None:
    out = scs_markup_to_html("[red]A[green]B")
    assert out == ('<span style="color:#FF2626">A</span>' '<span style="color:#75FF00">B</span>')


def test_normal_resets_to_default() -> None:
    out = scs_markup_to_html("[red]A[normal]B")
    assert out == '<span style="color:#FF2626">A</span>B'


def test_unknown_tag_stays_literal() -> None:
    # [WIP] and [1.59] are not colours - keep the brackets verbatim.
    assert scs_markup_to_html("Map [WIP] v[1.59]") == "Map [WIP] v[1.59]"


def test_unknown_tag_keeps_current_color() -> None:
    # An unknown tag must not reset an active colour.
    out = scs_markup_to_html("[red]A[WIP]B")
    assert out == '<span style="color:#FF2626">A[WIP]B</span>'


def test_yellow_is_supported() -> None:
    out = scs_markup_to_html("[yellow]gold")
    assert out == '<span style="color:#FDE100">gold</span>'


def test_html_special_chars_are_escaped() -> None:
    out = scs_markup_to_html("[red]a < b & c > d")
    assert out == '<span style="color:#FF2626">a &lt; b &amp; c &gt; d</span>'


def test_crlf_and_lf_become_br() -> None:
    assert scs_markup_to_html("a\r\nb\nc") == "a<br>b<br>c"


def test_tag_at_end_without_following_text() -> None:
    assert scs_markup_to_html("abc[red]") == "abc"


def test_case_insensitive_color_names() -> None:
    assert scs_markup_to_html("[ORANGE]x") == '<span style="color:#FFAE00">x</span>'


def test_color_table_has_official_values() -> None:
    assert SCS_COLORS["orange"] == "#FFAE00"
    assert SCS_COLORS["yellow"] == "#FDE100"
