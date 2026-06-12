"""Derives the things the UI shows from the raw scan plus the caches.

Pulled out of :class:`MainWindow`: turning a ``ScannedMod`` / ``ActiveMod`` into
a display name, icon, categories, compatibility status, conflict tooltip, and
the filtered/sorted browser list. Pure data, no Qt widgets, so it unit-tests
without a running app.

The static dependencies (caches, override stores) are passed once at
construction. The per-scan context (matcher, profile, game version, map-base
names) changes whenever a scan finishes or the profile switches, so the window
pushes it in via :meth:`set_context`.
"""

from __future__ import annotations

from easy_scsmodmanager.core.load_order import group_repr_token
from easy_scsmodmanager.core.map_base_mods import is_map_base
from easy_scsmodmanager.core.mod_categories import effective_categories, i18n_key
from easy_scsmodmanager.core.version_compat import CompatStatus, compat_status
from easy_scsmodmanager.integrations.scs.content_category import content_category
from easy_scsmodmanager.services.conflict_detect import (
    FrequentShare,
    ModOverride,
    Severity,
    analyze,
)
from easy_scsmodmanager.services.mod_matching import (
    ActiveModMatcher,
    active_name_for,
    resolve_display_name,
    workshop_id_for_path,
)
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.services.mod_search import matches_search
from easy_scsmodmanager.services.profile_reader import ActiveMod, Profile
from easy_scsmodmanager.ui.widgets.filter_toolbar import FilterState, ModSource, SortKey
from easy_scsmodmanager.utils.i18n import t

_MAX_TOOLTIP_ROWS = 12  # cap the per-mod conflict tooltip so it stays readable


class ModPresenter:
    def __init__(self, *, cache, workshop_cache, overrides, group_overrides, favorites) -> None:
        self._cache = cache
        self._workshop_cache = workshop_cache
        self._overrides = overrides
        self._group_overrides = group_overrides
        self._favorites = favorites
        # per-scan context, pushed in via set_context()
        self._matcher: ActiveModMatcher | None = None
        self._profile: Profile | None = None
        self._game_version: str | None = None
        self._map_base_names: tuple[str, ...] = ()
        # active.name -> mods it shares a def file with (recomputed per scan)
        self._conflict_overrides: dict[str, ModOverride] = {}
        self._frequent: dict[str, FrequentShare] = {}

    def set_context(
        self,
        *,
        matcher: ActiveModMatcher | None,
        profile: Profile | None,
        game_version: str | None,
        map_base_names: tuple[str, ...],
    ) -> None:
        self._matcher = matcher
        self._profile = profile
        self._game_version = game_version
        self._map_base_names = map_base_names

    # ------------------------------------------------------------------ #
    # names
    # ------------------------------------------------------------------ #

    def active_names(self) -> set[str]:
        """The active_mods names referenced by the current profile."""
        if self._profile is None:
            return set()
        return {active.name for active in self._profile.active_mods}

    def is_favorite(self, mod: ScannedMod) -> bool:
        return self._favorites.is_favorite(mod.mod_name)

    def _active_display_map(self) -> dict[str, str]:
        if self._profile is None:
            return {}
        return {a.name: a.display_name for a in self._profile.active_mods if a.display_name}

    def display_name_for(self, mod: ScannedMod) -> str:
        title = None
        wid = workshop_id_for_path(mod.path)
        if wid is not None:
            meta = self._workshop_cache.get(wid)
            title = meta.title if meta else None
        return resolve_display_name(mod, self._active_display_map(), workshop_title=title)

    # ------------------------------------------------------------------ #
    # icons
    # ------------------------------------------------------------------ #

    def icon_for(self, mod: ScannedMod) -> bytes | None:
        # icon is independent of the owned-DLC gate, so read it without dlc_fp
        icon = self._cache.icon_bytes_for(mod.path)
        if icon:
            return icon
        # Fall back to a Steam-Workshop preview when no local icon is in
        # the .scs - covers map mods with encrypted manifests.
        workshop_id = workshop_id_for_path(mod.path)
        if workshop_id is None:
            return None
        meta = self._workshop_cache.get(workshop_id)
        return meta.preview_bytes if meta else None

    def active_icon_for(self, active_mod: ActiveMod) -> bytes | None:
        if self._matcher is None:
            return None
        match = self._matcher.lookup(active_mod)
        if match is None:
            return None
        return self.icon_for(match)

    # ------------------------------------------------------------------ #
    # categories
    # ------------------------------------------------------------------ #

    def effective_for(self, mod: ScannedMod) -> tuple[str, ...]:
        cats = mod.manifest.categories if mod.manifest else ()
        return effective_categories(
            cats,
            is_map=mod.is_map,
            override=self._overrides.get(mod.path.stem),
            content_category=content_category(mod.def_files),
        )

    def category_for_active(self, active_mod: ActiveMod) -> tuple[str, ...]:
        """Effective category of an active mod, via its matched ScannedMod.

        Group overrides take priority: if the user pinned this mod to a specific
        load-order group the override token is returned directly, bypassing the
        scanner match entirely.
        """
        go = self._group_overrides.get(active_mod.name)
        if go:
            return (group_repr_token(go),)
        return (self.natural_group_token_for(active_mod),)

    def natural_group_token_for(self, active_mod: ActiveMod) -> str:
        """The mod's natural group token, ignoring any group override.

        The pin rule needs the home group computed override-free; otherwise
        dragging a pinned mod back home would compare against its own stale pin
        and re-pin instead of clearing. Same token path the renderer uses
        (category_for_active[0]), so the rule never disagrees with the layout.
        """
        if is_map_base(active_mod.name, active_mod.display_name or "", self._map_base_names):
            return "map_base"
        if self._matcher is None:
            return "other"
        match = self._matcher.lookup(active_mod)
        if match is None:
            return "other"
        cats = self.effective_for(match)
        return cats[0] if cats else "other"

    # ------------------------------------------------------------------ #
    # compatibility
    # ------------------------------------------------------------------ #

    def compat_for(self, mod: ScannedMod) -> CompatStatus:
        cvs = mod.manifest.compatible_versions if mod.manifest else ()
        return compat_status(self._game_version, cvs)

    # ------------------------------------------------------------------ #
    # conflicts
    # ------------------------------------------------------------------ #

    def compute_conflicts(self) -> None:
        """Recompute per-mod override severity + frequent-share info."""
        self._conflict_overrides = {}
        self._frequent = {}
        if self._profile is None or self._matcher is None:
            return
        active_defs: dict[str, tuple[str, ...]] = {}
        positions: dict[str, int] = {}
        # active_mods index 0 = bottom = lowest priority; higher index = above
        for index, active in enumerate(self._profile.active_mods):
            positions[active.name] = index
            match = self._matcher.lookup(active)
            if match is not None and match.def_files:
                active_defs[active.name] = match.def_files
        self._conflict_overrides, self._frequent = analyze(active_defs, positions)

    def has_conflicts(self) -> bool:
        return bool(self._conflict_overrides)

    def has_frequent(self) -> bool:
        return bool(self._frequent)

    def severity_for(self, active_mod: ActiveMod) -> Severity | None:
        """Override severity of this mod, or None when it wins all its files."""
        override = self._conflict_overrides.get(active_mod.name)
        return override.severity if override else None

    def frequent_for(self, active_mod: ActiveMod) -> bool:
        """Whether this mod shares any def file with many mods (frequent tier)."""
        return active_mod.name in self._frequent

    def conflict_for(self, active_mod: ActiveMod) -> str:
        """Tooltip: severity block (if any), then a dimmed frequent-shared block."""
        override = self._conflict_overrides.get(active_mod.name)
        frequent = self._frequent.get(active_mod.name)
        lines: list[str] = []
        if override is not None:
            names = self._active_display_map()
            header = (
                "conflict.tooltip.header_full"
                if override.severity is Severity.FULL
                else "conflict.tooltip.header_partial"
            )
            lines.append(t(header))
            shown = override.lost[:_MAX_TOOLTIP_ROWS]
            for path, winner in shown:
                lines.append(t("conflict.tooltip.row", file=path, mod=names.get(winner, winner)))
            rest = len(override.lost) - len(shown)
            if rest > 0:
                lines.append(t("conflict.tooltip.more", count=rest))
        if frequent is not None:
            # a real conflict already has a header above, so use the "also" lead
            lines.append(
                t("conflict.tooltip.frequent_also")
                if override is not None
                else t("conflict.tooltip.header_frequent")
            )
            for path, count in frequent.files[:_MAX_TOOLTIP_ROWS]:
                lines.append(t("conflict.tooltip.frequent_row", file=path, count=count))
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # versions
    # ------------------------------------------------------------------ #

    def local_versions(self) -> dict[str, str]:
        """active.name -> local package_version, for combo version checks."""
        result: dict[str, str] = {}
        if self._profile is None or self._matcher is None:
            return result
        for active in self._profile.active_mods:
            match = self._matcher.lookup(active)
            if match is not None and match.manifest and match.manifest.package_version:
                result[active.name] = match.manifest.package_version
        return result

    # ------------------------------------------------------------------ #
    # filtering / sorting
    # ------------------------------------------------------------------ #

    def filter_and_sort(self, mods: list[ScannedMod], state: FilterState) -> list[ScannedMod]:
        result: list[ScannedMod] = []
        for mod in mods:
            source_id = workshop_id_for_path(mod.path)
            if state.source is ModSource.WORKSHOP and source_id is None:
                continue
            if state.source is ModSource.LOCAL and source_id is not None:
                continue
            if state.favorites_only and not self.is_favorite(mod):
                continue
            # Search the name the user actually sees on the card, not a second
            # divergent source - a workshop "...Dashboard" lives in its title.
            display = self.display_name_for(mod)
            author = mod.manifest.author if mod.manifest else ""
            cats = self.effective_for(mod)
            cat_names = [t(i18n_key(c)) for c in cats]
            if not matches_search(state.search, display, author, mod.path.name, *cat_names):
                continue
            if state.category is not None and state.category not in cats:
                continue
            result.append(mod)

        result.sort(key=lambda m: self._sort_key(m, state.sort_key), reverse=state.sort_descending)
        return result

    def _sort_key(self, mod: ScannedMod, key: SortKey) -> tuple[int, str | float]:
        if key is SortKey.NAME:
            return (0, (mod.manifest.display_name if mod.manifest else mod.path.stem).lower())
        if key is SortKey.AUTHOR:
            return (0, (mod.manifest.author if mod.manifest else "").lower())
        if key is SortKey.DATE:
            # installed_at captured once at scan time (st_ctime) - no live stat,
            # so a vanished file sorts to the start instead of raising
            return (0, mod.installed_at)
        if key is SortKey.STATUS:
            is_active = active_name_for(mod) in self.active_names()
            return (0 if is_active else 1, mod.path.name.lower())
        return (0, mod.path.name.lower())
