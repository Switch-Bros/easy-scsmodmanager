"""QThread that unpacks one or more .scs archives off the UI thread.

base.scs is ~9 GB, so extraction must not block the UI. Each job is an
(archive, destination) pair; progress is reported per file and the whole
run can be cancelled.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from easy_scsmodmanager.services.scs_extractor import ExtractResult, extract_scs

log = logging.getLogger(__name__)


class ExtractThread(QThread):
    # done, total, archive name
    progress = pyqtSignal(int, int, str)
    # list[tuple[Path, ExtractResult]]
    finished_with_results = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, jobs: list[tuple[Path, Path]], *, clean: bool = False) -> None:
        super().__init__()
        self._jobs = jobs
        self._clean = clean
        self._cancel = False
        self._current_name = ""

    def cancel(self) -> None:
        self._cancel = True

    def _emit_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total, self._current_name)

    def _cancelled(self) -> bool:
        return self._cancel

    def run(self) -> None:
        results: list[tuple[Path, ExtractResult]] = []
        try:
            for scs_path, dest in self._jobs:
                if self._cancel:
                    break
                if self._clean and dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                self._current_name = scs_path.name
                result = extract_scs(
                    scs_path,
                    dest,
                    on_progress=self._emit_progress,
                    should_cancel=self._cancelled,
                )
                results.append((scs_path, result))
                if result.cancelled:
                    break
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("extraction failed")
            self.failed.emit(str(exc))
            return
        self.finished_with_results.emit(results)
