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


def _dated(path: str, installed_at: float) -> ScannedMod:
    return ScannedMod(
        path=Path(path),
        format=ScsFormat.ZIP,
        manifest=None,
        error=None,
        installed_at=installed_at,
    )


def test_date_sort_orders_by_installed_at_not_live_stat() -> None:
    # Regression LLBBC #64: DATE sorted by a live mod.path.stat() which, for
    # local mods, is the upstream build date (not the install date) and raised
    # on a missing file. The order must follow the captured installed_at, and
    # the paths here do not exist on disk, so a live stat would crash.
    presenter = _presenter()
    old = _dated("/mod/old.scs", 100.0)
    mid = _dated("/mod/mid.scs", 200.0)
    new = _dated("/mod/new.scs", 300.0)
    presenter.set_context(matcher=None, profile=None, game_version=None, map_base_names=())

    ascending = presenter.filter_and_sort([new, old, mid], FilterState(sort_key=SortKey.DATE))
    assert ascending == [old, mid, new]

    descending = presenter.filter_and_sort(
        [new, old, mid], FilterState(sort_key=SortKey.DATE, sort_descending=True)
    )
    assert descending == [new, mid, old]


def test_date_sort_puts_unknown_install_time_first() -> None:
    # A mod whose stamp could not be read keeps installed_at 0.0 and sorts to
    # the start (ascending) rather than raising - missing file is not a crash.
    presenter = _presenter()
    known = _dated("/mod/known.scs", 500.0)
    unknown = _dated("/mod/unknown.scs", 0.0)
    presenter.set_context(matcher=None, profile=None, game_version=None, map_base_names=())

    ordered = presenter.filter_and_sort([known, unknown], FilterState(sort_key=SortKey.DATE))

    assert ordered == [unknown, known]


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


def test_frequent_tier_in_presenter() -> None:
    from easy_scsmodmanager.services.mod_matching import ActiveModMatcher

    # 9 mods sharing one physics def -> frequent, not a conflict
    mods = [
        ScannedMod(
            path=Path(f"/m/m{i}.scs"),
            format=ScsFormat.ZIP,
            manifest=None,
            error=None,
            def_files=("def/vehicle/physics/physics.sii",),
        )
        for i in range(9)
    ]
    presenter = _presenter()
    profile = Profile(
        dir_name="d",
        profile_name="P",
        active_mods=tuple(ActiveMod(f"m{i}", f"M{i}") for i in range(9)),
    )
    presenter.set_context(
        matcher=ActiveModMatcher(mods),
        profile=profile,
        game_version=None,
        map_base_names=(),
    )
    presenter.compute_conflicts()

    assert presenter.has_frequent() is True
    assert presenter.has_conflicts() is False  # >8 never a red/yellow conflict
    assert presenter.frequent_for(ActiveMod("m0", "M0")) is True
    assert presenter.severity_for(ActiveMod("m0", "M0")) is None
    tip = presenter.conflict_for(ActiveMod("m0", "M0"))
    assert "physics.sii" in tip
    assert "9" in tip  # owner count, no names


# conflict report + tooltip hint


def _with_defs(name: str, defs: tuple[str, ...]) -> ScannedMod:
    return ScannedMod(
        path=Path(f"/m/{name}.scs"),
        format=ScsFormat.ZIP,
        manifest=None,
        error=None,
        def_files=defs,
    )


def _conflict_presenter(mods: list[ScannedMod], names: list[str]) -> ModPresenter:
    from easy_scsmodmanager.services.mod_matching import ActiveModMatcher

    presenter = _presenter()
    presenter.set_context(
        matcher=ActiveModMatcher(mods),
        profile=Profile(
            dir_name="d",
            profile_name="P",
            active_mods=tuple(ActiveMod(n, n.upper()) for n in names),
        ),
        game_version=None,
        map_base_names=(),
    )
    presenter.compute_conflicts()
    return presenter


def test_conflict_report_runs_top_down_and_skips_clean_mods() -> None:
    # a chain: a loses def/1 to b, b loses def/2 to c, c wins everything.
    # profile order is bottom-up (a, b, c) so the report must come back b, a.
    mods = [
        _with_defs("a", ("def/1.sii",)),
        _with_defs("b", ("def/1.sii", "def/2.sii")),
        _with_defs("c", ("def/2.sii",)),
    ]
    presenter = _conflict_presenter(mods, ["a", "b", "c"])

    report = presenter.conflict_report()

    assert [e.name for e in report] == ["b", "a"]  # display order, c has no marks
    assert report[0].display_name == "B"


def test_conflict_report_is_empty_without_a_profile() -> None:
    assert _presenter().conflict_report() == []


def test_tooltip_appends_the_right_click_hint_once_it_caps() -> None:
    from easy_scsmodmanager.utils.i18n import t

    shared = tuple(f"def/x{i}.sii" for i in range(15))
    presenter = _conflict_presenter(
        [_with_defs("low", shared), _with_defs("high", shared)], ["low", "high"]
    )

    tip = presenter.conflict_for(ActiveMod("low", "LOW"))

    assert t("conflict.tooltip.more", count=3) in tip
    assert tip.endswith(t("conflict.tooltip.full_hint"))


def test_tooltip_has_no_hint_when_nothing_was_capped() -> None:
    from easy_scsmodmanager.utils.i18n import t

    shared = ("def/x0.sii", "def/x1.sii")
    presenter = _conflict_presenter(
        [_with_defs("low", shared), _with_defs("high", shared)], ["low", "high"]
    )

    tip = presenter.conflict_for(ActiveMod("low", "LOW"))

    assert t("conflict.tooltip.full_hint") not in tip


def test_hint_also_fires_for_a_capped_frequent_block() -> None:
    # the frequent block caps silently (no "more" row), so the hint is the only
    # sign that files are missing - the one path that would otherwise go untested
    from easy_scsmodmanager.utils.i18n import t

    shared = tuple(f"def/p{i}.sii" for i in range(15))
    mods = [_with_defs(f"m{i}", shared) for i in range(9)]
    presenter = _conflict_presenter(mods, [f"m{i}" for i in range(9)])

    tip = presenter.conflict_for(ActiveMod("m0", "M0"))

    assert presenter.severity_for(ActiveMod("m0", "M0")) is None  # frequent only
    assert t("conflict.tooltip.more", count=3) not in tip  # frequent never says it
    assert tip.endswith(t("conflict.tooltip.full_hint"))


def test_no_hint_when_both_blocks_fit() -> None:
    from easy_scsmodmanager.utils.i18n import t

    frequent = tuple(f"def/p{i}.sii" for i in range(3))
    overridden = tuple(f"def/x{i}.sii" for i in range(3))
    # m0 and m1 fight over the x files; all nine share the p files
    mods = [_with_defs("m0", frequent + overridden), _with_defs("m1", frequent + overridden)]
    mods += [_with_defs(f"m{i}", frequent) for i in range(2, 9)]
    presenter = _conflict_presenter(mods, [f"m{i}" for i in range(9)])

    tip = presenter.conflict_for(ActiveMod("m0", "M0"))

    assert presenter.severity_for(ActiveMod("m0", "M0")) is not None
    assert presenter.frequent_for(ActiveMod("m0", "M0")) is True
    assert t("conflict.tooltip.full_hint") not in tip


def test_active_display_names_exposes_the_profile_map() -> None:
    presenter = _presenter()
    presenter.set_context(
        matcher=None,
        profile=Profile(
            dir_name="d", profile_name="P", active_mods=(ActiveMod("raw", "Pretty Name"),)
        ),
        game_version=None,
        map_base_names=(),
    )

    assert presenter.active_display_names() == {"raw": "Pretty Name"}
