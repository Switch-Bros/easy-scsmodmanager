"""Runs the Steam Workshop fetcher for mods we lack local data for.

Pulled out of MainWindow. Owns the fetch thread's lifecycle: it picks the
workshop mods still missing an icon, a parsed manifest, or a real name, starts
the thread, and refreshes the UI as previews arrive. The window forwards its
close event so the thread can be waited on during shutdown.
"""

from __future__ import annotations

from collections.abc import Callable

from easy_scsmodmanager.core.db.scan_cache import ScanCache
from easy_scsmodmanager.services.mod_matching import workshop_id_for_path
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.ui.mod_presenter import ModPresenter
from easy_scsmodmanager.ui.threads.workshop_fetch_thread import WorkshopFetchThread
from easy_scsmodmanager.utils.i18n import t


class WorkshopFetchController:
    def __init__(
        self,
        *,
        cache: ScanCache,
        presenter: ModPresenter,
        on_updated: Callable[[], None],
        show_status: Callable[[str, int], None],
    ) -> None:
        self._cache = cache
        self._presenter = presenter
        self._on_updated = on_updated
        self._show_status = show_status
        self._thread: WorkshopFetchThread | None = None

    def kickoff(self, mods: list[ScannedMod]) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        workshop_ids = self._targets(mods)
        if not workshop_ids:
            return
        self._thread = WorkshopFetchThread(workshop_ids, self._cache.path)
        self._thread.preview_fetched.connect(self._on_preview)
        self._thread.finished_with_summary.connect(self._on_done)
        self._thread.start()

    def shutdown(self, msecs: int) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait(msecs)

    def _targets(self, mods: list[ScannedMod]) -> list[str]:
        """Workshop ids still missing an icon, a manifest, or a real name."""
        workshop_ids: list[str] = []
        seen: set[str] = set()
        for mod in mods:
            wid = workshop_id_for_path(mod.path)
            if wid is None or wid in seen:
                continue
            has_icon = self._cache.icon_bytes_for(mod.path) is not None
            has_manifest = mod.manifest is not None
            # also fetch when we still have no real name (workshop mods whose
            # manifest carries no display_name and that aren't in the profile)
            has_name = self._presenter.display_name_for(mod) != mod.path.stem
            if has_icon and has_manifest and has_name:
                continue
            seen.add(wid)
            workshop_ids.append(wid)
        return workshop_ids

    def _on_preview(self, _workshop_id: str) -> None:
        # Bulk-refreshing once per N updates would be nicer; for now a full
        # refresh on every fetched preview keeps it simple and stays cheap
        # enough on 100-ish workshop mods.
        self._on_updated()

    def _on_done(self, downloaded: int) -> None:
        if downloaded == 0:
            return
        self._show_status(t("status_bar.workshop_fetched", count=downloaded), 5000)
