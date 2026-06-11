"""Phase 2 read-only main window.

Layout::

    +-----------------------------------------------------------+
    |  MenuBar                                                  |
    +----------------------------------------+------------------+
    |  FilterToolbar                         | ProfileHeader    |
    |  ----------------------------------    | ---------------- |
    |  ModCardGrid (3 columns, 276x162 cards)| ActiveModList    |
    |                                        |                  |
    +----------------------------------------+------------------+
    |  StatusBar: scan progress / counts / selection info       |
    +-----------------------------------------------------------+
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from PyQt6.QtCore import QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager import __app_name__, __version__
from easy_scsmodmanager.core.category_overrides import (
    CategoryOverrides,
    default_group_overrides_path,
    default_overrides_path,
)
from easy_scsmodmanager.core.db.scan_cache import ScanCache, default_cache_path
from easy_scsmodmanager.core.db.workshop_meta_cache import WorkshopMetaCache
from easy_scsmodmanager.core.favorites_store import FavoritesStore, default_favorites_path
from easy_scsmodmanager.core.game_paths import (
    GAME_SHORT_NAME,
    Game,
    GameInstall,
    InstallKind,
    detect_game_installs,
    find_game_install_dir,
    install_for_overrides,
)
from easy_scsmodmanager.core.game_version import read_game_version
from easy_scsmodmanager.core.load_order import (
    GROUPS,
    group_index_for_token,
    group_repr_token,
)
from easy_scsmodmanager.core.settings_store import SettingsStore
from easy_scsmodmanager.services.mod_matching import (
    ActiveModMatcher,
    active_name_for,
)
from easy_scsmodmanager.services.mod_scanner import ScannedMod, owned_dlc_tokens
from easy_scsmodmanager.services.profile_reader import (
    ActiveMod,
    Profile,
    decode_profile_dir_name,
    discover_profiles,
    read_profile,
)
from easy_scsmodmanager.services.profile_writer import save_active_mods
from easy_scsmodmanager.ui.controllers.map_combo_controller import MapComboController
from easy_scsmodmanager.ui.controllers.mod_delete_controller import ModDeleteController
from easy_scsmodmanager.ui.controllers.mod_share_controller import ModShareController
from easy_scsmodmanager.ui.controllers.profile_backup_controller import ProfileBackupController
from easy_scsmodmanager.ui.controllers.workshop_fetch_controller import WorkshopFetchController
from easy_scsmodmanager.ui.dialogs.extract_dialog import ExtractDialog
from easy_scsmodmanager.ui.dialogs.mod_info_dialog import ModInfoDialog
from easy_scsmodmanager.ui.dialogs.settings_dialog import SettingsDialog
from easy_scsmodmanager.ui.menu.main_menu import build_menu_bar
from easy_scsmodmanager.ui.mod_presenter import ModPresenter
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.threads.scan_thread import ScanResult, ScanThread
from easy_scsmodmanager.ui.widgets.active_mod_list import MOVE_TO_GROUP_AUTO, ActiveModList
from easy_scsmodmanager.ui.widgets.filter_toolbar import FilterState, FilterToolbar
from easy_scsmodmanager.ui.widgets.mod_card_grid import ModCardGrid
from easy_scsmodmanager.ui.widgets.profile_header import ProfileChoice, ProfileHeader
from easy_scsmodmanager.utils.i18n import t
from easy_scsmodmanager.utils.logging_setup import default_log_dir

if TYPE_CHECKING:
    from PyQt6.QtGui import QAction

log = logging.getLogger(__name__)

GITHUB_ISSUES_URL = "https://github.com/Switch-Bros/easy-scsmodmanager/issues"


class MainWindow(QMainWindow):
    def __init__(self, *, game: Game = Game.ETS2, auto_scan: bool = True) -> None:
        super().__init__()
        self._game = game
        self._settings = SettingsStore()
        # game_id -> its checkable menu action, filled by build_menu_bar
        self._game_actions: dict[Game, QAction] = {}
        self._install: GameInstall | None = None
        self._profile: Profile | None = None
        self._profile_sii_path: Path | None = None
        self._profile_choices: list[tuple[Path, Profile | None]] = []
        self._all_mods: list[ScannedMod] = []
        self._matcher: ActiveModMatcher | None = None
        self._filter = FilterState()
        self._cache = ScanCache(default_cache_path())
        self._workshop_cache = WorkshopMetaCache(self._cache.connection())
        self._overrides = CategoryOverrides(default_overrides_path())
        self._group_overrides = CategoryOverrides(default_group_overrides_path())
        self._favorites = FavoritesStore(default_favorites_path())
        self._map_base_names = SettingsStore().get_map_base_names()
        self._game_version: str | None = None
        self._owned_dlc: frozenset[str] | None = None
        self._scan_thread: ScanThread | None = None
        # derives display data (names, icons, categories, conflicts, filtering)
        self._presenter = ModPresenter(
            cache=self._cache,
            workshop_cache=self._workshop_cache,
            overrides=self._overrides,
            group_overrides=self._group_overrides,
            favorites=self._favorites,
        )
        self._workshop = WorkshopFetchController(
            cache=self._cache,
            presenter=self._presenter,
            on_updated=self._refresh_all,
            show_status=self.statusBar().showMessage,
        )
        self._share_controller = ModShareController(
            parent=self,
            current_game=lambda: self._game,
            current_profile=lambda: self._profile,
            profile_sii_path=lambda: self._profile_sii_path,
            matcher=lambda: self._matcher,
            local_versions=self._presenter.local_versions,
            group_token_for=self._share_group_id_for,
            apply_group_pin=self._apply_group_pin,
            show_status=self.statusBar().showMessage,
            request_rescan=self._rescan_if_possible,
            reload_profile=self._reload_profile_after_share,
        )

        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.setMinimumSize(QSize(1280, 760))
        self.resize(QSize(1382, 1125))  # open roomy; the WM clamps to the screen
        self.setStyleSheet(f"QMainWindow {{ background-color: {Theme.BACKGROUND}; }}")

        build_menu_bar(self)
        self._build_central()
        self.statusBar().setStyleSheet(f"color: {Theme.TEXT_DIM};")

        self._update_service: object | None = None  # kept alive during a check
        if auto_scan:
            self._detect_install_and_scan()

        # silent update check once the app has finished loading
        if self._settings.get_update_check_on_startup():
            QTimer.singleShot(5000, self._on_startup_update_check)

    # ------------------------------------------------------------------ #
    # building
    # ------------------------------------------------------------------ #

    def _build_central(self) -> None:
        central = QWidget()
        central.setStyleSheet(f"background-color: {Theme.BACKGROUND};")
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 0)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        self._filter_toolbar = FilterToolbar()
        self._filter_toolbar.filter_changed.connect(self._on_filter_changed)
        self._grid = ModCardGrid(columns=Theme.MOD_GRID_COLUMNS)
        self._grid.selection_changed.connect(self._on_grid_selection_changed)
        self._grid.info_requested.connect(self._on_mod_info_requested)
        self._grid.card_activated.connect(self._on_mod_activated)
        self._grid.favorite_toggled.connect(self._on_favorite_toggled)
        self._grid.show_in_active_requested.connect(self._show_mod_in_active_list)
        self._delete = ModDeleteController(
            parent=self,
            profiles=lambda: [p for _, p in self._profile_choices if p is not None],
            display_name_for=self._presenter.display_name_for,
            on_mods_deleted=self._on_mods_deleted,
            show_status=self.statusBar().showMessage,
        )
        self._grid.delete_requested.connect(self._delete.request_delete)
        del_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self._grid)
        del_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        del_shortcut.activated.connect(
            lambda: self._delete.request_delete(self._grid.selected_mods())
        )
        select_all = QShortcut(QKeySequence.StandardKey.SelectAll, self._grid)
        select_all.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        select_all.activated.connect(self._grid.select_all)
        left_layout.addWidget(self._filter_toolbar)
        left_layout.addWidget(self._grid, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        self._profile_header = ProfileHeader()
        self._profile_header.set_game_name(GAME_SHORT_NAME[self._game])
        self._backup = ProfileBackupController(
            parent=self,
            current_path=lambda: self._profile_sii_path,
            restore_name=self._restore_display_name,
            show_status=self.statusBar().showMessage,
            on_restored=self._reload_after_restore,
            game_name=lambda: GAME_SHORT_NAME[self._game],
        )
        self._profile_header.profile_selected.connect(self._on_profile_chosen)
        self._profile_header.backup_requested.connect(self._backup.backup)
        self._profile_header.restore_requested.connect(self._backup.restore)
        self._active_list = ActiveModList()
        self._active_list.mod_focus_requested.connect(self._on_active_mod_focus)
        self._active_list.order_changed.connect(self._on_active_order_changed)
        self._active_list.mods_dropped.connect(self._on_mods_dropped)
        self._active_list.reorder_pin_requested.connect(self._on_reorder_pin)
        self._active_list.move_to_group_requested.connect(self._on_move_to_group)
        self._combo = MapComboController(
            parent=self,
            active_list=self._active_list,
            presenter=self._presenter,
            show_status=self.statusBar().showMessage,
            request_rescan=self._rescan_if_possible,
        )
        self._active_list.export_combo_requested.connect(self._combo.export)
        self._active_list.import_combo_requested.connect(self._combo.import_)
        right_layout.addWidget(self._profile_header)
        right_layout.addWidget(self._active_list, 1)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self._save_btn = QPushButton(t("active_panel.save"))
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_clicked)
        save_row.addWidget(self._save_btn)
        right_layout.addLayout(save_row)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

    # ------------------------------------------------------------------ #
    # data flow
    # ------------------------------------------------------------------ #

    def _detect_install_and_scan(self) -> None:
        self._install = self._resolve_install()
        if self._install is None:
            self.statusBar().showMessage(t("status_bar.no_install"))
            return
        self._game_version = read_game_version(self._install.documents_dir)
        # owned DLCs gate the 1.48 dlc_ package normalisation in the scanner
        store = SettingsStore()
        install_dir = store.get_install_override(self._game) or find_game_install_dir(self._game)
        self._owned_dlc = owned_dlc_tokens(install_dir)
        self._load_profiles()
        self._start_scan()

    def _resolve_install(self) -> GameInstall | None:
        """A manual override from Settings wins; otherwise auto-detect."""
        store = SettingsStore()
        documents = store.get_documents_override(self._game)
        if documents is not None:
            workshop = store.get_workshop_override(self._game)
            log.info("using documents override for %s: %s", self._game.value, documents)
            return install_for_overrides(self._game, documents, workshop)
        installs = detect_game_installs(self._game)
        if not installs:
            return None
        proton = next((i for i in installs if i.kind is InstallKind.PROTON), None)
        chosen = proton or installs[0]
        log.info(
            "resolved %s install: %s (%s)",
            self._game.value,
            chosen.documents_dir,
            chosen.kind.value,
        )
        return chosen

    def _on_open_settings(self) -> None:
        dialog = SettingsDialog(SettingsStore(), self)
        if dialog.exec():
            # the map-base name list may have changed: re-read it so auto
            # detection in the active list uses the new terms.
            self._map_base_names = SettingsStore().get_map_base_names()
            # Re-detect from scratch: a path override may have changed.
            self._detect_install_and_scan()

    def _on_open_extract(self) -> None:
        store = SettingsStore()
        install_dir = store.get_install_override(self._game) or find_game_install_dir(self._game)
        ExtractDialog(install_dir, self).exec()

    def _on_open_log_folder(self) -> None:
        log_dir = default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))

    def available_games(self) -> set[Game]:
        """Games we can actually open - a manual override or an auto-detect."""
        available: set[Game] = set()
        for game in Game:
            if self._settings.get_documents_override(game) is not None or detect_game_installs(
                game
            ):
                available.add(game)
        return available

    def _switch_game(self, game: Game) -> None:
        if game is self._game:
            return
        # switching reloads a different profile; an unsaved edit would be lost
        if self._save_btn.isEnabled():
            choice = QMessageBox.question(
                self,
                t("dialog.switch_game.title"),
                t("dialog.switch_game.body"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self._sync_game_menu()  # put the radio check back on the old game
                return
        self._game = game
        self._settings.set_active_game(game)
        self._profile_header.set_game_name(GAME_SHORT_NAME[game])
        self._save_btn.setEnabled(False)
        self._sync_game_menu()
        self._detect_install_and_scan()

    def _sync_game_menu(self) -> None:
        for game, action in self._game_actions.items():
            action.setChecked(game is self._game)

    def _load_profiles(self) -> None:
        if self._install is None:
            return
        paths = discover_profiles(self._install)
        loaded: list[tuple[Path, Profile | None]] = []
        for sii in paths:
            try:
                loaded.append((sii, read_profile(sii)))
            except Exception as exc:
                log.warning("failed to read profile %s: %s", sii, exc)
                loaded.append((sii, None))
        self._profile_choices = loaded

        if not loaded:
            self._profile = None
            self._profile_sii_path = None
            self._profile_header.set_profile(None)
            self._profile_header.set_profile_choices([])
            return

        # Reopen the profile the user last had selected; when it is gone
        # (deleted, renamed) fall back to the most recently modified one.
        remembered = self._settings.get_last_selected_profile(self._game)
        sii_path = next((s for s, _ in loaded if s == remembered), None)
        if sii_path is None:
            sii_path = max(loaded, key=lambda p: p[0].stat().st_mtime)[0]
        self._activate_profile(sii_path)
        self._settings.set_last_selected_profile(self._game, sii_path)

    def _activate_profile(self, sii_path: Path) -> None:
        profile = next((p for s, p in self._profile_choices if s == sii_path), None)
        self._profile = profile
        self._profile_sii_path = sii_path
        avatar = sii_path.parent / "online_avatar.png"
        self._profile_header.set_profile(
            profile,
            avatar_path=avatar if avatar.exists() else None,
            meta_text=(
                t("active_panel.count", count=len(profile.active_mods))
                if profile is not None
                else ""
            ),
            restorable=True,  # we have a path; restore works even if it won't parse
        )
        self._refresh_profile_choices_menu()

    def _refresh_profile_choices_menu(self) -> None:
        choices = [
            ProfileChoice(
                sii_path=sii,
                display_name=(profile.profile_name if profile else sii.parent.name),
                active_count=(len(profile.active_mods) if profile else 0),
                is_current=(sii == self._profile_sii_path),
            )
            for sii, profile in self._profile_choices
        ]
        self._profile_header.set_profile_choices(choices)

    def _start_scan(self) -> None:
        if self._install is None:
            return
        self.statusBar().showMessage(
            t("status_bar.scanning", path=str(self._install.documents_dir))
        )
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._scan_thread.wait()
        self._scan_thread = ScanThread(
            self._install, self._cache, self._game_version, self._owned_dlc
        )
        self._scan_thread.finished_with_result.connect(self._on_scan_finished)
        self._scan_thread.failed.connect(self._on_scan_failed)
        self._scan_thread.progress.connect(self._on_scan_progress)
        self._scan_thread.start()

    def _on_scan_progress(self, done: int, name: str) -> None:
        self.statusBar().showMessage(t("status_bar.scan_progress", done=done, name=name))

    def _on_scan_finished(self, result: ScanResult) -> None:
        self._all_mods = result.mods
        self._matcher = ActiveModMatcher(self._all_mods)
        self._refresh_grid()
        self._refresh_active_list()

        installed_actives = (
            self._matcher.installed_active_names(list(self._profile.active_mods))
            if self._profile is not None
            else set()
        )
        active_count = len(installed_actives)
        errors = sum(1 for m in self._all_mods if m.manifest is None and m.error is not None)
        self.statusBar().showMessage(
            t(
                "status_bar.scan_done",
                total=len(self._all_mods),
                active=active_count,
                errors=errors,
                elapsed=result.elapsed_seconds,
            )
        )
        self._workshop.kickoff(self._all_mods)
        if self._combo.has_pending():
            self._combo.apply_pending()
        self._share_controller.on_scan_finished()

    def _on_scan_failed(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _sync_presenter(self) -> None:
        """Push the current scan context into the presenter before it derives."""
        self._presenter.set_context(
            matcher=self._matcher,
            profile=self._profile,
            game_version=self._game_version,
            map_base_names=self._map_base_names,
        )

    def _on_mods_deleted(self, mods: list[ScannedMod]) -> None:
        # files are already in the trash; drop them from model, cache and the
        # loaded active list (no full rescan - cheap for big libraries)
        paths = {m.path for m in mods}
        self._all_mods = [m for m in self._all_mods if m.path not in paths]
        for mod in mods:
            self._cache.delete(mod.path)
        self._matcher = ActiveModMatcher(self._all_mods)
        active_names = {am.name for am in self._active_list.display_order()}
        for mod in mods:
            name = active_name_for(mod)
            if name in active_names:
                # removes by name + emits order_changed -> Save button enables
                self._active_list.remove_mod(ActiveMod(name=name, display_name=""))
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        self._sync_presenter()
        filtered = self._presenter.filter_and_sort(self._all_mods, self._filter)
        self._grid.set_mods(
            filtered,
            active_names=self._presenter.active_names(),
            icon_for=self._presenter.icon_for,
            name_for=self._presenter.display_name_for,
            categories_for=self._presenter.effective_for,
            compat_for=self._presenter.compat_for,
            is_favorite_for=self._presenter.is_favorite,
        )

    def _refresh_active_list(self) -> None:
        if self._profile is None or self._matcher is None:
            self._active_list.set_active_mods([])
            return
        self._sync_presenter()
        installed = {active_name_for(m) for m in self._all_mods}
        self._presenter.compute_conflicts()
        self._active_list.set_active_mods(
            self._profile.active_mods,
            installed_names=installed,
            icon_for=self._presenter.active_icon_for,
            category_for=self._presenter.category_for_active,
            conflict_for=self._presenter.conflict_for,
            severity_for=self._presenter.severity_for,
            frequent_for=self._presenter.frequent_for,
        )

    # ------------------------------------------------------------------ #
    # signal handlers
    # ------------------------------------------------------------------ #

    def _on_filter_changed(self, state: FilterState) -> None:
        self._filter = state
        self._refresh_grid()

    def _on_grid_selection_changed(self, mods: list[ScannedMod]) -> None:
        if not mods:
            self.statusBar().clearMessage()
            return
        self.statusBar().showMessage(t("status_bar.selection", count=len(mods)))
        # opt-in: a single click on a card jumps to its row in the active list
        if len(mods) == 1 and self._settings.get_grid_click_jumps_to_active():
            self._show_mod_in_active_list(mods[0])

    def _show_mod_in_active_list(self, mod: ScannedMod) -> None:
        # no-op when the mod is not on the active list (focus_active returns False)
        self._active_list.focus_active(active_name_for(mod))

    def _on_mod_info_requested(self, mod: ScannedMod) -> None:
        ModInfoDialog(mod, parent=self, display_name=self._presenter.display_name_for(mod)).exec()

    def _on_favorite_toggled(self, mod: ScannedMod, is_favorite: bool) -> None:
        self._favorites.set_favorite(mod.mod_name, is_favorite)
        # only the favourites filter changes which cards are shown; otherwise the
        # card already flipped its own star, so no rebuild is needed
        if self._filter.favorites_only:
            self._refresh_grid()

    def _on_active_order_changed(self) -> None:
        self._save_btn.setEnabled(True)
        self._grid.set_active_names({m.name for m in self._active_list.display_order()})

    def _on_mod_activated(self, mod: ScannedMod) -> None:
        # double-click in the grid drops the mod into its own group's block
        # (group-aware, so it never renders under a later group's header)
        self._active_list.insert_into_group_block(
            ActiveMod(name=active_name_for(mod), display_name=self._presenter.display_name_for(mod))
        )

    def _on_mods_dropped(self, paths: list[str], row: int, group_id: str) -> None:
        # mods dragged from the grid land at the drop position; an already
        # active mod is relocated there. Dropping into a section adopts that
        # section's group (same meaning as the right-click move), via the pin
        # rule, so the mod stays where it was dropped instead of snapping back.
        by_path = {str(mod.path): mod for mod in self._all_mods}
        to_place: list[ActiveMod] = []
        seen: set[str] = set()
        for path in paths:
            mod = by_path.get(path)
            if mod is None:
                continue
            name = active_name_for(mod)
            if name in seen:  # dedup within this drag itself
                continue
            seen.add(name)
            to_place.append(
                ActiveMod(name=name, display_name=self._presenter.display_name_for(mod))
            )
        if to_place:
            for active_mod in to_place:
                self._apply_group_pin(active_mod, group_id)
            self._active_list.insert_or_move(to_place, at=row)

    def _on_reorder_pin(self, mods: object, group_id: str) -> None:
        # internal reorder-drag: pin the moved mods to the target section before
        # the widget re-renders (the widget moves the rows itself afterwards)
        for active_mod in mods if isinstance(mods, list) else []:
            self._apply_group_pin(cast(ActiveMod, active_mod), group_id)

    def _on_move_to_group(self, mods: object, group_id: str) -> None:
        # payload carries the whole selection (a single right-clicked mod is
        # collapsed to a one-item list by the widget)
        raw = mods if isinstance(mods, list) else [mods]
        selection: list[ActiveMod] = [cast(ActiveMod, m) for m in raw]
        if not selection:
            return
        if group_id == MOVE_TO_GROUP_AUTO:
            self._move_mods_to_natural_group(selection)
            return
        # pin per mod first (DB only, no rerender) so the batch move renders
        # with the new groups, then one physical batch move = one order_changed
        for mod in selection:
            self._apply_group_pin(mod, group_id)
        self._active_list.move_mods_to_group(selection, group_id)

    def _apply_group_pin(self, mod: ActiveMod, group_id: str) -> None:
        # pin only when the target differs from the mod's natural (override-free)
        # group; targeting home clears the pin instead of freezing a stale one
        natural = self._presenter.natural_group_token_for(mod)
        target = group_repr_token(group_id)
        if group_index_for_token(natural) == group_index_for_token(target):
            self._group_overrides.clear(mod.name)
        else:
            self._group_overrides.set(mod.name, group_id)

    def _share_group_id_for(self, mod: ActiveMod) -> str:
        """Effective group id for the share: explicit pin first, else natural."""
        pinned = self._group_overrides.get(mod.name)
        if pinned:
            return pinned
        token = self._presenter.natural_group_token_for(mod)
        return GROUPS[group_index_for_token(token)].id

    def _move_mods_to_natural_group(self, mods: list[ActiveMod]) -> None:
        # "Automatic": drop the pin and send each mod back to its home group,
        # bucketed so each distinct group is a single rerender
        buckets: dict[str, list[ActiveMod]] = {}
        for mod in mods:
            self._group_overrides.clear(mod.name)
            natural = self._presenter.natural_group_token_for(mod)
            gid = GROUPS[group_index_for_token(natural)].id
            buckets.setdefault(gid, []).append(mod)
        for gid, group_mods in buckets.items():
            self._active_list.move_mods_to_group(group_mods, gid)

    def _rescan_if_possible(self) -> bool:
        """Kick off a rescan when an install is known. Returns whether it ran."""
        if self._install is None:
            return False
        self._start_scan()
        return True

    def _on_save_clicked(self) -> None:
        if self._profile_sii_path is None:
            return
        choice = QMessageBox.question(
            self,
            t("dialog.save.title"),
            t("dialog.save.body", game=GAME_SHORT_NAME[self._game]),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return
        backup = choice == QMessageBox.StandardButton.Yes
        try:
            save_active_mods(
                self._profile_sii_path,
                self._active_list.ordered_active_mods(),
                backup=backup,
            )
            self._reread_current_profile()
        except Exception as exc:
            log.warning("save failed for %s: %s", self._profile_sii_path, exc)
            self.statusBar().showMessage(t("status_bar.save_failed", error=str(exc)))
            return
        self._save_btn.setEnabled(False)
        self.statusBar().showMessage(t("status_bar.saved"))

    def _reread_current_profile(self) -> None:
        # reload from disk so the in-memory profile matches what was written
        if self._profile_sii_path is None:
            return
        self._profile = read_profile(self._profile_sii_path)
        self._profile_choices = [
            (s, self._profile if s == self._profile_sii_path else p)
            for s, p in self._profile_choices
        ]
        # re-activate so the header meta text and the chooser entries pick up
        # the new active-mod count instead of showing the stale one
        self._activate_profile(self._profile_sii_path)

    def _reload_profile_after_share(self) -> None:
        # the share apply rewrote profile.sii behind the widget's back:
        # re-read and re-render so the active list shows the imported order
        try:
            self._reread_current_profile()
        except Exception as exc:
            log.warning("reload after share failed for %s: %s", self._profile_sii_path, exc)
            return
        self._refresh_active_list()
        self._refresh_grid()
        self._save_btn.setEnabled(False)

    def _refresh_all(self) -> None:
        self._refresh_grid()
        self._refresh_active_list()

    def _on_active_mod_focus(self, active_mod: ActiveMod) -> None:
        """Clicking a row in the active list scrolls to + selects the
        matching mod card in the left grid."""
        if self._matcher is None:
            return
        match = self._matcher.lookup(active_mod)
        if match is None:
            self.statusBar().showMessage(
                t("status_bar.active_not_on_disk", name=active_mod.display_name or active_mod.name)
            )
            return
        if not self._grid.focus_mod(match):
            # The mod is on disk but currently filtered out - clear the
            # filter so it becomes visible, then try again.
            self._filter_toolbar._search.clear()
            self._filter = FilterState()
            self._refresh_grid()
            self._grid.focus_mod(match)

    def _restore_display_name(self) -> str:
        # falls back to the decoded dir name when the profile no longer parses
        if self._profile is not None:
            return self._profile.profile_name or self._profile.dir_name
        if self._profile_sii_path is not None:
            return decode_profile_dir_name(self._profile_sii_path.parent.name)
        return ""

    def _reload_after_restore(self) -> None:
        # re-read the profile so the active list reflects the restored state
        self._load_profiles()
        self._refresh_active_list()
        self._refresh_grid()

    def _on_profile_chosen(self, choice: ProfileChoice) -> None:
        if choice.sii_path == self._profile_sii_path:
            return
        self._activate_profile(choice.sii_path)
        self._settings.set_last_selected_profile(self._game, choice.sii_path)
        self._refresh_active_list()
        self._refresh_grid()

    def _on_refresh(self) -> None:
        if self._install is None:
            self._detect_install_and_scan()
            return
        self._start_scan()

    def _on_clear_cache(self) -> None:
        removed = self._cache.clear()
        self.statusBar().showMessage(f"Cleared {removed} cache entries")
        if self._install is not None:
            self._start_scan()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            t("dialog.about.title"),
            t("dialog.about.body", version=__version__),
        )

    # ------------------------------------------------------------------ #
    # updates
    # ------------------------------------------------------------------ #

    def _on_check_updates(self) -> None:
        self._run_update_check(silent=False)

    def _on_startup_update_check(self) -> None:
        self._run_update_check(silent=True)

    def _run_update_check(self, *, silent: bool) -> None:
        from easy_scsmodmanager.services.update_service import UpdateService

        svc = UpdateService(parent=self)
        self._update_service = svc  # keep the QObject alive past this method
        svc.update_available.connect(self._on_update_available)
        if not silent:
            svc.update_not_available.connect(self._on_update_up_to_date)
            svc.check_failed.connect(self._on_update_check_failed)
        else:
            svc.check_failed.connect(lambda msg: log.info("startup update check failed: %s", msg))
        svc.check_for_update()

    def _on_update_available(self, info: object) -> None:
        from easy_scsmodmanager.services.update_core import UpdateInfo
        from easy_scsmodmanager.ui.dialogs.update_dialog import UpdateDialog

        svc = self._update_service
        if not isinstance(info, UpdateInfo) or svc is None:
            return
        UpdateDialog(info, svc, parent=self).exec()  # type: ignore[arg-type]

    def _on_update_up_to_date(self) -> None:
        QMessageBox.information(
            self,
            t("update.check_title"),
            t("update.up_to_date", version=__version__),
        )

    def _on_update_check_failed(self, message: str) -> None:
        QMessageBox.warning(
            self,
            t("update.check_title"),
            t("update.check_failed", error=message),
        )

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._scan_thread.wait(5000)
        self._workshop.shutdown(5000)
        self._share_controller.shutdown(5000)
        self._cache.close()
        self._favorites.close()
        self._overrides.close()
        self._group_overrides.close()
        super().closeEvent(event)
