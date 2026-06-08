"""Unit tests for the ModPresenter (pulled out of MainWindow).

Pure data derivation - no Qt - so it tests without a running app.
"""

from __future__ import annotations

from pathlib import Path

from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.services.profile_reader import ActiveMod, Profile
from easy_scsmodmanager.ui.mod_presenter import ModPresenter
from easy_scsmodmanager.ui.widgets.filter_toolbar import FilterState, SortKey


class _NullCache:
    """Stands in for ScanCache / WorkshopMetaCache - never hit by these tests."""

    def get(self, *_args: object) -> None:
        return None


class _NoFavorites:
    """Favourites store that holds nothing."""

    def is_favorite(self, _mod_key: str) -> bool:
        return False


def _mod(path: str) -> ScannedMod:
    return ScannedMod(path=Path(path), format=ScsFormat.ZIP, manifest=None, error=None)


def _presenter() -> ModPresenter:
    return ModPresenter(
        cache=_NullCache(),
        workshop_cache=_NullCache(),
        overrides=_NullCache(),
        group_overrides=_NullCache(),
        favorites=_NoFavorites(),
    )


def test_status_sort_orders_active_first_without_crashing() -> None:
    # Regression: _sort_key called a non-existent _active_paths_set() and would
    # raise AttributeError the moment a user sorted by Status.
    presenter = _presenter()
    active = _mod("/mod/active_one.scs")
    inactive = _mod("/mod/inactive_one.scs")
    presenter.set_context(
        matcher=None,
        profile=Profile(
            dir_name="d", profile_name="P", active_mods=(ActiveMod("active_one", "A"),)
        ),
        game_version=None,
        map_base_names=(),
    )

    ordered = presenter.filter_and_sort([inactive, active], FilterState(sort_key=SortKey.STATUS))

    assert ordered[0] is active  # active mods come first


def test_display_name_prefers_profile_active_display() -> None:
    # A workshop-less mod with no manifest name falls back through the chain;
    # the profile's active display name wins over the bare file stem.
    presenter = _presenter()
    mod = _mod("/mod/universal.scs")
    presenter.set_context(
        matcher=None,
        profile=Profile(
            dir_name="d",
            profile_name="P",
            active_mods=(ActiveMod("universal", "Pretty Name"),),
        ),
        game_version=None,
        map_base_names=(),
    )

    assert presenter.display_name_for(mod) == "Pretty Name"


def test_favorites_only_keeps_just_favourites(tmp_path) -> None:
    from easy_scsmodmanager.core.favorites_store import FavoritesStore
    from easy_scsmodmanager.ui.mod_presenter import ModPresenter

    favorites = FavoritesStore(tmp_path / "fav.db")
    favorites.set_favorite("liked", True)
    presenter = ModPresenter(
        cache=_NullCache(),
        workshop_cache=_NullCache(),
        overrides=_NullCache(),
        group_overrides=_NullCache(),
        favorites=favorites,
    )
    presenter.set_context(matcher=None, profile=None, game_version=None, map_base_names=())
    liked = _mod("/mod/liked.scs")
    other = _mod("/mod/other.scs")

    result = presenter.filter_and_sort([liked, other], FilterState(favorites_only=True))

    assert result == [liked]


def test_source_workshop_keeps_just_workshop_mods() -> None:
    from easy_scsmodmanager.ui.widgets.filter_toolbar import ModSource

    presenter = _presenter()
    workshop = _mod("/lib/steamapps/workshop/content/227300/123/universal.scs")
    local = _mod("/games/ETS2/mod/local_mod.scs")
    presenter.set_context(matcher=None, profile=None, game_version=None, map_base_names=())

    result = presenter.filter_and_sort([workshop, local], FilterState(source=ModSource.WORKSHOP))

    assert result == [workshop]


def test_source_local_keeps_just_local_mods() -> None:
    from easy_scsmodmanager.ui.widgets.filter_toolbar import ModSource

    presenter = _presenter()
    workshop = _mod("/lib/steamapps/workshop/content/227300/123/universal.scs")
    local = _mod("/games/ETS2/mod/local_mod.scs")
    presenter.set_context(matcher=None, profile=None, game_version=None, map_base_names=())

    result = presenter.filter_and_sort([workshop, local], FilterState(source=ModSource.LOCAL))

    assert result == [local]


def test_source_all_keeps_both() -> None:
    from easy_scsmodmanager.ui.widgets.filter_toolbar import ModSource

    presenter = _presenter()
    workshop = _mod("/lib/steamapps/workshop/content/227300/123/universal.scs")
    local = _mod("/games/ETS2/mod/local_mod.scs")
    presenter.set_context(matcher=None, profile=None, game_version=None, map_base_names=())

    result = presenter.filter_and_sort([workshop, local], FilterState(source=ModSource.ALL))

    assert set(result) == {workshop, local}


def test_severity_and_tooltip_come_from_owner_positions() -> None:
    from easy_scsmodmanager.services.conflict_detect import Severity
    from easy_scsmodmanager.services.mod_matching import ActiveModMatcher

    low = ScannedMod(
        path=Path("/m/low.scs"),
        format=ScsFormat.ZIP,
        manifest=None,
        error=None,
        def_files=("def/x.sii",),
    )
    high = ScannedMod(
        path=Path("/m/high.scs"),
        format=ScsFormat.ZIP,
        manifest=None,
        error=None,
        def_files=("def/x.sii",),
    )
    presenter = _presenter()
    profile = Profile(
        dir_name="d",
        profile_name="P",
        # index 0 = bottom; "high" higher index = above = wins
        active_mods=(ActiveMod("low", "Low"), ActiveMod("high", "High")),
    )
    presenter.set_context(
        matcher=ActiveModMatcher([low, high]),
        profile=profile,
        game_version=None,
        map_base_names=(),
    )
    presenter.compute_conflicts()

    assert presenter.severity_for(ActiveMod("low", "Low")) is Severity.FULL
    assert presenter.severity_for(ActiveMod("high", "High")) is None
    assert presenter.has_conflicts() is True
    tip = presenter.conflict_for(ActiveMod("low", "Low"))
    assert "def/x.sii" in tip
    assert "High" in tip  # winner shown by display name
