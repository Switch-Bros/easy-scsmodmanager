#
# easy_scsmodmanager/core/load_order.py
# Fixed ETS2/ATS load-order groups shown as headers in the active list.
#
# Top = highest priority = top of the in-game load order. Each group (except
# the decorative map_base header) maps a set of effective-category tokens;
# tokens with no group of their own fall into ui_other.
#
# TODO: revisit group order once we have user feedback from beta?

from __future__ import annotations

from dataclasses import dataclass

MAP_BASE = "map_base"


@dataclass(frozen=True)
class LoadOrderGroup:
    """One named bucket in the active-list load-order layout."""

    id: str
    label_keys: tuple[str, ...]
    tokens: tuple[str, ...]


GROUPS: tuple[LoadOrderGroup, ...] = (
    LoadOrderGroup(
        MAP_BASE,
        (
            "load_order.map_base.world",
            "load_order.map_base.background",
            "load_order.map_base.loading",
        ),
        (MAP_BASE,),
    ),
    LoadOrderGroup(
        "graphics_weather",
        ("load_order.graphics_weather",),
        ("graphics", "weather_setup"),
    ),
    LoadOrderGroup("sound", ("load_order.sound",), ("sound",)),
    LoadOrderGroup("physics", ("load_order.physics",), ("physics",)),
    LoadOrderGroup(
        "ui_other",
        ("load_order.ui_other",),
        ("ui", "other", "models", "movers", "walkers", "prefabs"),
    ),
    LoadOrderGroup(
        "tuning_interior", ("load_order.tuning_interior",), ("tuning_parts", "interior")
    ),
    LoadOrderGroup("ai_traffic", ("load_order.ai_traffic",), ("ai_traffic",)),
    LoadOrderGroup("cargo", ("load_order.cargo",), ("cargo_pack",)),
    LoadOrderGroup("paint_jobs", ("load_order.paint_jobs",), ("paint_job",)),
    LoadOrderGroup("trailers", ("load_order.trailers",), ("trailer",)),
    LoadOrderGroup("trucks", ("load_order.trucks",), ("truck",)),
    LoadOrderGroup("maps", ("load_order.maps",), ("map",)),
)

_UI_OTHER_INDEX = next(i for i, g in enumerate(GROUPS) if g.id == "ui_other")
_TOKEN_TO_INDEX: dict[str, int] = {tok: i for i, g in enumerate(GROUPS) for tok in g.tokens}


def group_index_for_token(token: str) -> int:
    # unmapped tokens fall into ui_other, never map_base (index 0)
    return _TOKEN_TO_INDEX.get(token, _UI_OTHER_INDEX)


def group_label_keys(group_id: str) -> tuple[str, ...]:
    return next(g.label_keys for g in GROUPS if g.id == group_id)


def group_repr_token(group_id: str) -> str:
    """Return the first token for a group (used as the effective category token
    when a group override is active)."""
    return next(g for g in GROUPS if g.id == group_id).tokens[0]
