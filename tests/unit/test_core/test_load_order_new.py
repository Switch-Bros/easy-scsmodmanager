"""Tests for the new group_repr_token function and map_base token mapping."""

from easy_scsmodmanager.core.load_order import (
    group_index_for_token,
    group_repr_token,
)


def test_map_base_token_maps_to_index_zero() -> None:
    assert group_index_for_token("map_base") == 0


def test_group_repr_token_trucks() -> None:
    assert group_repr_token("trucks") == "truck"


def test_group_repr_token_map_base() -> None:
    assert group_repr_token("map_base") == "map_base"


def test_group_repr_token_maps() -> None:
    assert group_repr_token("maps") == "map"


def test_group_repr_token_sound() -> None:
    assert group_repr_token("sound") == "sound"
