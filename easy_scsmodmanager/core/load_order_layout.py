"""Turn the active mods (+ their effective category) into a row sequence
with load-order group headers (spacers) and misplacement flags.

Mod order is never changed; spacers are inserted before the first mod of
each group, every group's spacer is present even when empty, and a mod whose
group lies earlier than the furthest group already reached is flagged
misplaced (it sits too low in the order).
"""

from __future__ import annotations

from dataclasses import dataclass

from easy_scsmodmanager.core.load_order import GROUPS, group_index_for_token


@dataclass(frozen=True)
class SpacerRow:
    group_id: str


@dataclass(frozen=True)
class ModRow[T]:
    mod: T
    misplaced: bool
    expected_group_id: str


def build_rows[T](items: list[tuple[T, str]]) -> list[SpacerRow | ModRow[T]]:
    rows: list[SpacerRow | ModRow[T]] = [SpacerRow(GROUPS[0].id)]
    current = 0
    for mod, token in items:
        g = group_index_for_token(token)
        if g >= current:
            for gi in range(current + 1, g + 1):
                rows.append(SpacerRow(GROUPS[gi].id))
            current = g
            rows.append(ModRow(mod, False, GROUPS[g].id))
        else:
            rows.append(ModRow(mod, True, GROUPS[g].id))
    for gi in range(current + 1, len(GROUPS)):
        rows.append(SpacerRow(GROUPS[gi].id))
    return rows
