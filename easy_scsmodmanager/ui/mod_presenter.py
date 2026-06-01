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
from easy_scsmodmanager.services.conflict_detect import ModConflict, find_conflicts
from easy_scsmodmanager.services.mod_matching import (
    ActiveModMatcher,
    active_name_for,
    resolve_display_name,
    workshop_id_for_path,
)
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.services.mod_search import matches_search
from easy_scsmodmanager.services.profile_reader import ActiveMod, Profile
from easy_scsmodmanager.ui.widgets.filter_toolbar import FilterState, SortKey
from easy_scsmodmanager.utils.i18n import t


class ModPresenter:
    def __init__(self, *, cache, workshop_cache, overrides, group_overrides) -> None:
        self._cache = cache
        self._workshop_cache = workshop_cache
        self._overrides = overrides
        self._group_overrides = group_overrides
        # per-scan context, pushed in via set_context()
        self._matcher: ActiveModMatcher | None = None
        self._profile: Profile | None = None
        self._game_version: str | None = None
        self._map_base_names: tuple[str, ...] = ()
        # active.name -> mods it shares a def file with (recomputed per scan)
        self._conflicts: dict[str, list[ModConflict]] = {}

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
        entry = self._cache.get(mod.path)
        if entry and entry.icon_bytes:
            return entry.icon_bytes
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
        if is_map_base(active_mod.name, active_mod.display_name or "", self._map_base_names):
            return ("map_base",)
        if self._matcher is None:
            return ("other",)
        match = self._matcher.lookup(active_mod)
        if match is None:
            return ("other",)
        return self.effective_for(match)

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
        """Recompute which active mods overwrite the same def files."""
        self._conflicts = {}
        if self._profile is None or self._matcher is None:
            return
        active_defs: dict[str, tuple[str, ...]] = {}
        for active in self._profile.active_mods:
            match = self._matcher.lookup(active)
            if match is not None and match.def_files:
                active_defs[active.name] = match.def_files
        self._conflicts = find_conflicts(active_defs)

    def conflict_for(self, active_mod: ActiveMod) -> str:
        """Tooltip listing the active mods this one shares def files with."""
        conflicts = self._conflicts.get(active_mod.name)
        if not conflicts:
            return ""
        names = self._active_display_map()
        lines = [t("conflict.tooltip_header")]
        for c in conflicts[:8]:
            other = names.get(c.other, c.other)
            sample = c.shared[0] if c.shared else ""
            lines.append(t("conflict.tooltip_row", mod=other, file=sample))
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
            if state.workshop_only and workshop_id_for_path(mod.path) is None:
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
            return (0, mod.path.stat().st_mtime)
        if key is SortKey.STATUS:
            is_active = active_name_for(mod) in self.active_names()
            return (0 if is_active else 1, mod.path.name.lower())
        return (0, mod.path.name.lower())
