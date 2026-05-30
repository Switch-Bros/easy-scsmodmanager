"""Render SCS mod-description colour markup as HTML.

ETS2/ATS ``description.txt`` uses opening-only colour tags: a tag like
``[orange]`` colours every following character until the next colour tag
or ``[normal]`` (reset to the widget's default colour). There are no
closing tags.

Only known colour names are markup. Every other ``[..]`` token - ``[WIP]``,
``[1.59]``, ``[en]``, a date - is literal text and survives verbatim,
brackets and all. That whitelist is the whole point: the game treats
unknown tags as plain text, and so must we, or we would eat legitimate
brackets out of people's descriptions.

Colours: the five official SCS names use the game's own hex values so the
text looks like it does in-game. ``yellow`` is not an official tag but is
common in the wild, so we map it too (HeikesFootSlave's pick: #FDE100).

Source: https://modding.scssoft.com/wiki/Documentation/Engine/Mod_manager
"""

from __future__ import annotations

import re
from html import escape

# name -> CSS hex. Official SCS values, plus yellow (see module docstring).
SCS_COLORS: dict[str, str] = {
    "red": "#FF2626",
    "green": "#75FF00",
    "blue": "#12ABE5",
    "white": "#FFFFFF",
    "orange": "#FFAE00",
    "yellow": "#FDE100",
}

# Resets to the widget's default text colour (no span emitted).
_RESET = "normal"

_TAG = re.compile(r"\[([^\]]*)\]")


def scs_markup_to_html(text: str) -> str:
    """Convert SCS colour markup to HTML for a QTextEdit.

    Default-coloured runs (before any tag, or after ``[normal]``) are left
    unwrapped so they inherit the widget's text colour. Unknown tags stay
    literal. ``<``, ``>``, ``&`` are escaped; newlines become ``<br>``.
    """
    if not text:
        return ""

    runs: list[tuple[str | None, str]] = []
    current: str | None = None
    buf: list[str] = []
    pos = 0

    def flush() -> None:
        if buf:
            runs.append((current, "".join(buf)))
            buf.clear()

    for match in _TAG.finditer(text):
        token = match.group(1).lower()
        if token not in SCS_COLORS and token != _RESET:
            continue  # unknown tag - leave it in place as literal text
        buf.append(text[pos : match.start()])
        flush()
        current = SCS_COLORS.get(token)  # None for "normal"
        pos = match.end()

    buf.append(text[pos:])
    flush()

    return "".join(_render_run(color, chunk) for color, chunk in runs if chunk)


def _render_run(color: str | None, chunk: str) -> str:
    html = escape(chunk).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    if color is None:
        return html
    return f'<span style="color:{color}">{html}</span>'
