"""Background fetcher that pulls workshop metadata and previews.

The UI calls this after a mod scan once it knows which workshop ids
need metadata + previews. The thread runs two phases:

1. Bulk metadata fetch (one HTTP request per 50 ids).
2. Preview image downloads for ids that have a ``preview_url`` but
   no cached bytes yet.

Each phase persists results into the workshop_meta cache and emits a
signal so the GUI can refresh the visible cards incrementally.
"""

from __future__ import annotations

import logging

import httpx
from PyQt6.QtCore import QThread, pyqtSignal

from easy_scsmodmanager.core.db.workshop_meta_cache import WorkshopMetaCache
from easy_scsmodmanager.integrations.steam.workshop_api import (
    fetch_metadata,
    fetch_preview_image,
)

log = logging.getLogger(__name__)


class WorkshopFetchThread(QThread):
    """Pulls metadata for ``workshop_ids`` into ``cache`` off the UI thread.

    Signals:
        metadata_fetched(int) - emits after the metadata-batch phase
          with the number of newly cached entries.
        preview_fetched(str) - emits per downloaded preview image
          (carries the workshop id) so the GUI can refresh a single
          card without rebuilding the whole grid.
        finished_with_summary(int) - emits at the end with the total
          previews downloaded.
    """

    metadata_fetched = pyqtSignal(int)
    preview_fetched = pyqtSignal(str)
    finished_with_summary = pyqtSignal(int)

    def __init__(
        self,
        workshop_ids: list[str],
        cache: WorkshopMetaCache,
    ) -> None:
        super().__init__()
        self._ids = list(dict.fromkeys(workshop_ids))  # deduplicate, preserve order
        self._cache = cache

    def run(self) -> None:  # noqa: D401
        if not self._ids:
            self.finished_with_summary.emit(0)
            return

        try:
            with httpx.Client(timeout=20.0) as client:
                self._fetch_metadata_phase(client)
                downloaded = self._fetch_preview_phase(client)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("workshop fetch failed: %s", exc)
            self.finished_with_summary.emit(0)
            return
        self.finished_with_summary.emit(downloaded)

    def _fetch_metadata_phase(self, client: httpx.Client) -> None:
        # Skip ids we have already enriched in this database.
        cached = self._cache.get_many(self._ids)
        missing = [wid for wid in self._ids if wid not in cached]
        if not missing:
            self.metadata_fetched.emit(0)
            return

        items = fetch_metadata(missing, client=client)
        for wid, item in items.items():
            self._cache.put_metadata(
                wid,
                title=item.title,
                description=item.description,
                preview_url=item.preview_url,
                time_updated=item.time_updated,
            )
        self.metadata_fetched.emit(len(items))

    def _fetch_preview_phase(self, client: httpx.Client) -> int:
        needs_preview = self._cache.workshop_ids_without_preview(self._ids)
        if not needs_preview:
            return 0

        downloaded = 0
        # Fetch one-by-one so the UI can refresh incrementally and a
        # single dead URL does not abort the run.
        for wid in needs_preview:
            entry = self._cache.get(wid)
            if entry is None or not entry.preview_url:
                continue
            payload = fetch_preview_image(entry.preview_url, client=client)
            if not payload:
                continue
            self._cache.put_preview_bytes(wid, payload)
            downloaded += 1
            self.preview_fetched.emit(wid)
        return downloaded
