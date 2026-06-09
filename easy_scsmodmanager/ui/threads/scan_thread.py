"""QThread wrapper around scan_game_install.

The UI cannot block on the cold-scan (12 seconds), so the heavy lifting
runs on a worker thread and signals back to the main thread. The
SQLite cache is opened with check_same_thread=False so it can be
passed across the thread boundary.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from easy_scsmodmanager.core.db.scan_cache import ScanCache
from easy_scsmodmanager.core.game_paths import GameInstall
from easy_scsmodmanager.services.mod_scanner import ScannedMod, scan_game_install

log = logging.getLogger(__name__)


def _log_peak_rss(mod_count: int) -> None:
    # baseline for the planned 1.3.0 icon/grid rework - measure, do not guess.
    # resource is Unix-only, so skip silently on Windows.
    try:
        import resource

        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        log.info("peak RSS after scanning %d mods: %d MB", mod_count, kb // 1024)
    except Exception:  # pragma: no cover - platform without resource
        pass


@dataclass(frozen=True)
class ScanResult:
    install: GameInstall
    mods: list[ScannedMod]
    elapsed_seconds: float


class ScanWorker(QObject):
    """Lives on the worker thread, does the scan, emits the result."""

    finished = pyqtSignal(object)  # ScanResult
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, str)  # (mods scanned so far, current mod name)

    def __init__(
        self,
        install: GameInstall,
        cache: ScanCache | None,
        game_version: str | None = None,
        owned_dlc: frozenset[str] | None = None,
    ) -> None:
        super().__init__()
        self._install = install
        self._cache = cache
        self._game_version = game_version
        self._owned_dlc = owned_dlc
        self._done = 0

    def run(self) -> None:
        start = time.monotonic()
        self._done = 0
        try:
            mods = scan_game_install(
                self._install,
                cache=self._cache,
                game_version=self._game_version,
                on_scan=self._tick,
                owned_dlc=self._owned_dlc,
            )
        except Exception as exc:  # pragma: no cover - defensive only
            log.exception("scan failed")
            self.failed.emit(str(exc))
            return
        elapsed = time.monotonic() - start
        _log_peak_rss(len(mods))
        self.finished.emit(ScanResult(install=self._install, mods=mods, elapsed_seconds=elapsed))

    def _tick(self, path: Path) -> None:
        # fed straight from the scanner's per-mod hook - no separate count path
        self._done += 1
        self.progress.emit(self._done, path.name)


class ScanThread(QThread):
    """Thin QThread that owns a single ScanWorker.

    Usage::

        thread = ScanThread(install, cache)
        thread.finished_with_result.connect(self._on_done)
        thread.start()
    """

    finished_with_result = pyqtSignal(object)  # ScanResult
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, str)  # (mods scanned so far, current mod name)

    def __init__(
        self,
        install: GameInstall,
        cache: ScanCache | None,
        game_version: str | None = None,
        owned_dlc: frozenset[str] | None = None,
    ) -> None:
        super().__init__()
        self._worker = ScanWorker(install, cache, game_version, owned_dlc)
        self._worker.finished.connect(self.finished_with_result.emit)
        self._worker.failed.connect(self.failed.emit)
        self._worker.progress.connect(self.progress.emit)

    def run(self) -> None:  # noqa: D401
        self._worker.run()
