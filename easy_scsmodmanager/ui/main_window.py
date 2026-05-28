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
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager import __app_name__, __version__
from easy_scsmodmanager.core.db.scan_cache import ScanCache, default_cache_path
from easy_scsmodmanager.core.db.workshop_meta_cache import WorkshopMetaCache
from easy_scsmodmanager.core.game_paths import Game, GameInstall, detect_game_installs
from easy_scsmodmanager.services.mod_matching import ActiveModMatcher, workshop_id_for_path
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.services.profile_reader import (
    ActiveMod,
    Profile,
    discover_profiles,
    read_profile,
)
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.threads.scan_thread import ScanResult, ScanThread
from easy_scsmodmanager.ui.threads.workshop_fetch_thread import WorkshopFetchThread
from easy_scsmodmanager.ui.widgets.active_mod_list import ActiveModList
from easy_scsmodmanager.ui.widgets.filter_toolbar import FilterState, FilterToolbar, SortKey
from easy_scsmodmanager.ui.widgets.mod_card_grid import ModCardGrid
from easy_scsmodmanager.ui.widgets.profile_header import ProfileChoice, ProfileHeader
from easy_scsmodmanager.utils.i18n import t

log = logging.getLogger(__name__)

GITHUB_ISSUES_URL = "https://github.com/Switch-Bros/easy-scsmodmanager/issues"


class MainWindow(QMainWindow):
    def __init__(self, *, game: Game = Game.ETS2, auto_scan: bool = True) -> None:
        super().__init__()
        self._game = game
        self._install: GameInstall | None = None
        self._profile: Profile | None = None
        self._profile_sii_path: Path | None = None
        self._profile_choices: list[tuple[Path, Profile | None]] = []
        self._all_mods: list[ScannedMod] = []
        self._matcher: ActiveModMatcher | None = None
        self._filter = FilterState()
        self._cache = ScanCache(default_cache_path())
        self._workshop_cache = WorkshopMetaCache(self._cache.connection())
        self._scan_thread: ScanThread | None = None
        self._workshop_thread: WorkshopFetchThread | None = None

        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.setMinimumSize(QSize(1280, 760))
        self.setStyleSheet(f"QMainWindow {{ background-color: {Theme.BACKGROUND}; }}")

        self._build_menu_bar()
        self._build_central()
        self.statusBar().setStyleSheet(f"color: {Theme.TEXT_DIM};")

        if auto_scan:
            self._detect_install_and_scan()

    # ------------------------------------------------------------------ #
    # building
    # ------------------------------------------------------------------ #

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu(t("menu.file"))
        refresh = QAction(t("menu.file.refresh"), self)
        refresh.setShortcut("F5")
        refresh.triggered.connect(self._on_refresh)
        file_menu.addAction(refresh)

        clear_cache = QAction(t("menu.file.clear_cache"), self)
        clear_cache.triggered.connect(self._on_clear_cache)
        file_menu.addAction(clear_cache)

        file_menu.addSeparator()
        quit_action = QAction(t("menu.file.quit"), self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(quit_action)

        help_menu = menu_bar.addMenu(t("menu.help"))
        about = QAction(t("menu.help.about"), self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

        issues = QAction(t("menu.help.report_issue"), self)
        issues.triggered.connect(lambda: webbrowser.open(GITHUB_ISSUES_URL))
        help_menu.addAction(issues)

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
        left_layout.addWidget(self._filter_toolbar)
        left_layout.addWidget(self._grid, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        self._profile_header = ProfileHeader()
        self._profile_header.profile_selected.connect(self._on_profile_chosen)
        self._active_list = ActiveModList()
        self._active_list.mod_focus_requested.connect(self._on_active_mod_focus)
        right_layout.addWidget(self._profile_header)
        right_layout.addWidget(self._active_list, 1)

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
        installs = detect_game_installs(self._game)
        if not installs:
            self.statusBar().showMessage(t("status_bar.no_install"))
            return
        proton = next((i for i in installs if i.kind.value == "proton"), None)
        self._install = proton or installs[0]
        self._load_profiles()
        self._start_scan()

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

        # Default: most recently modified profile.
        sii_path = max(loaded, key=lambda p: p[0].stat().st_mtime)[0]
        self._activate_profile(sii_path)

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
        self._scan_thread = ScanThread(self._install, self._cache)
        self._scan_thread.finished_with_result.connect(self._on_scan_finished)
        self._scan_thread.failed.connect(self._on_scan_failed)
        self._scan_thread.start()

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
        self._populate_categories()
        self._kickoff_workshop_fetch()

    def _on_scan_failed(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _populate_categories(self) -> None:
        cats: set[str] = set()
        for mod in self._all_mods:
            if mod.manifest is not None:
                cats.update(mod.manifest.categories)
        self._filter_toolbar.set_categories(sorted(cats))

    def _refresh_grid(self) -> None:
        filtered = self._apply_filter(self._all_mods, self._filter)
        self._grid.set_mods(
            filtered,
            active_names=self._active_paths_set(),
            icon_for=self._icon_for,
        )

    def _refresh_active_list(self) -> None:
        if self._profile is None or self._matcher is None:
            self._active_list.set_active_mods([])
            return
        installed = self._matcher.installed_active_names(list(self._profile.active_mods))
        self._active_list.set_active_mods(
            self._profile.active_mods,
            installed_names=installed,
            icon_for=self._active_icon_for,
        )

    def _icon_for(self, mod: ScannedMod) -> bytes | None:
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

    def _active_icon_for(self, active_mod: ActiveMod) -> bytes | None:
        if self._matcher is None:
            return None
        match = self._matcher.lookup(active_mod)
        if match is None:
            return None
        return self._icon_for(match)

    def _active_paths_set(self) -> set[str]:
        """The set of mod-path stems that are referenced by the profile.

        Used by the card grid to mark cards green. The grid uses path
        stems for matching; the matcher resolves the broader set so
        Workshop directory mods light up too.
        """
        if self._matcher is None or self._profile is None:
            return set()
        stems: set[str] = set()
        for active in self._profile.active_mods:
            match = self._matcher.lookup(active)
            if match is not None:
                stems.add(match.path.stem)
        return stems

    def _apply_filter(self, mods: list[ScannedMod], state: FilterState) -> list[ScannedMod]:
        needle = state.search.lower().strip()
        result: list[ScannedMod] = []
        for mod in mods:
            display = (mod.manifest.display_name if mod.manifest else mod.path.stem).lower()
            author = (mod.manifest.author if mod.manifest else "").lower()
            cats = list(mod.manifest.categories) if mod.manifest else []
            if needle and not (
                needle in display
                or needle in author
                or needle in mod.path.name.lower()
                or any(needle in c.lower() for c in cats)
            ):
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
            return (0 if mod.path.stem in self._active_paths_set() else 1, mod.path.name.lower())
        return (0, mod.path.name.lower())

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

    def _kickoff_workshop_fetch(self) -> None:
        """Start the Steam Workshop fetcher for mods we lack local data for.

        Targets workshop mods that either have no icon yet or no parsed
        manifest at all (encrypted map mods fall in the second bucket).
        Skips mods that already have everything from local scan.
        """
        if self._workshop_thread is not None and self._workshop_thread.isRunning():
            return

        workshop_ids: list[str] = []
        seen: set[str] = set()
        for mod in self._all_mods:
            wid = workshop_id_for_path(mod.path)
            if wid is None or wid in seen:
                continue
            entry = self._cache.get(mod.path)
            has_icon = bool(entry and entry.icon_bytes)
            has_manifest = mod.manifest is not None
            if has_icon and has_manifest:
                continue
            seen.add(wid)
            workshop_ids.append(wid)

        if not workshop_ids:
            return

        self._workshop_thread = WorkshopFetchThread(workshop_ids, self._workshop_cache)
        self._workshop_thread.preview_fetched.connect(self._on_workshop_preview_ready)
        self._workshop_thread.finished_with_summary.connect(self._on_workshop_fetch_done)
        self._workshop_thread.start()

    def _on_workshop_preview_ready(self, _workshop_id: str) -> None:
        # Bulk-refresh the grid + active list once per N updates would be
        # nicer; for now a full refresh on every fetched preview keeps the
        # code simple and stays cheap enough on 100-ish workshop mods.
        self._refresh_grid()
        self._refresh_active_list()

    def _on_workshop_fetch_done(self, downloaded: int) -> None:
        if downloaded == 0:
            return
        self.statusBar().showMessage(
            t("status_bar.workshop_fetched", count=downloaded),
            5000,
        )

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

    def _on_profile_chosen(self, choice: ProfileChoice) -> None:
        if choice.sii_path == self._profile_sii_path:
            return
        self._activate_profile(choice.sii_path)
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
    # lifecycle
    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._scan_thread.wait(5000)
        if self._workshop_thread is not None and self._workshop_thread.isRunning():
            self._workshop_thread.wait(5000)
        self._cache.close()
        super().closeEvent(event)


_ = Path
