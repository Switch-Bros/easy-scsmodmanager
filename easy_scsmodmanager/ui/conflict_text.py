"""One formatter for every place a conflict is spelled out.

Three outputs share this module: the hover tooltip (capped), the conflict
dialog (complete, on screen) and the saved log file (complete, plain). Keeping
the ``{file} -> {mod}`` row and the severity headers here means they exist once
instead of drifting apart in three renderers.

Pure text - no Qt import, so it unit-tests without an app. The glyphs live here
too because both the list widgets and the dialog need them; the file version of
the report deliberately carries none (the headers say the severity in words).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from easy_scsmodmanager.services.conflict_detect import FrequentShare, ModOverride, Severity
from easy_scsmodmanager.utils.i18n import t

# Severity glyphs: shape differs (triangle vs. crossed circle) so the two levels
# stay distinct in greyscale / for colour-blind users, not colour alone.
# U+2298 renders in Inter on Win+Linux; documented fallback is U+2715 ("X").
GLYPH_PARTIAL = "⚠"  # warning triangle
GLYPH_FULL = "⊘"  # circled division slash (crossed circle)
GLYPH_FREQUENT = "="  # neutral "frequently shared" (not a conflict); fallback "•"

_RULE = "=" * 44


@dataclass(frozen=True)
class ReportEntry:
    """One mod's share of the report: what it loses and what it shares."""

    name: str  # internal active.name, the key everything else is looked up by
    display_name: str
    override: ModOverride | None
    frequent: FrequentShare | None


def override_lines(
    override: ModOverride,
    names: Mapping[str, str],
    *,
    limit: int | None = None,
) -> tuple[list[str], int]:
    # severity header plus one '{file} -> {mod}' row each; returns (lines, rest)
    key = (
        "conflict.tooltip.header_full"
        if override.severity is Severity.FULL
        else "conflict.tooltip.header_partial"
    )
    shown = override.lost if limit is None else override.lost[:limit]
    lines = [t(key)]
    for path, winner in shown:
        lines.append(t("conflict.tooltip.row", file=path, mod=names.get(winner, winner)))
    # the caller decides what to do with the remainder (tooltip appends "more",
    # the report never caps at all)
    return lines, len(override.lost) - len(shown)


def frequent_lines(
    frequent: FrequentShare,
    *,
    also: bool,
    limit: int | None = None,
) -> tuple[list[str], int]:
    # 'also' means a severity header already sits above this block
    key = "conflict.tooltip.frequent_also" if also else "conflict.tooltip.header_frequent"
    shown = frequent.files if limit is None else frequent.files[:limit]
    lines = [t(key)]
    for path, count in shown:
        lines.append(t("conflict.tooltip.frequent_row", file=path, count=count))
    return lines, len(frequent.files) - len(shown)


def mod_block(
    display_name: str,
    override: ModOverride | None,
    frequent: FrequentShare | None,
    names: Mapping[str, str],
) -> list[str]:
    """Uncapped block for one mod, its display name as the first line."""
    lines = [display_name]
    if override is not None:
        lines.extend(override_lines(override, names)[0])
    if frequent is not None:
        lines.extend(frequent_lines(frequent, also=override is not None)[0])
    return lines


def report_text(
    entries: Sequence[ReportEntry],
    names: Mapping[str, str],
    *,
    version: str,
    game: str,
    profile: str,
    generated: str,
) -> str:
    """The whole log, header block first, one block per mod below."""
    # The header stays English on purpose: this file gets pasted into forum
    # threads, where one shape for everyone is worth more than a translation.
    head = [
        f"Easy SCSModManager {version} - conflict log",
        f"Game: {game}   Profile: {profile}",
        f"Generated: {generated}",
        f"Total mods with conflicts: {len(entries)}",
        _RULE,
    ]
    out = "\n".join(head)
    for e in entries:
        out += "\n\n" + "\n".join(mod_block(e.display_name, e.override, e.frequent, names))
    return out + "\n"
