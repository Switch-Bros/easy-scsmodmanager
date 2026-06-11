"""Runs share uploads/lookups off the UI thread.

Both threads translate share_api exceptions into a short error KIND token
("not_configured" | "connection" | "not_found" | "rejected"); the dialogs
map kinds to i18n keys (mod_share.error.<kind>) so no user-facing string
lives down here.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from easy_scsmodmanager.integrations.supabase.share_api import (
    ShareApiError,
    ShareConnectionError,
    ShareNotConfiguredError,
    ShareNotFoundError,
    create_share,
    fetch_share,
)

log = logging.getLogger(__name__)


def _kind_for(exc: ShareApiError) -> str:
    if isinstance(exc, ShareNotConfiguredError):
        return "not_configured"
    if isinstance(exc, ShareConnectionError):
        return "connection"
    if isinstance(exc, ShareNotFoundError):
        return "not_found"
    return "rejected"


class ShareUploadThread(QThread):
    succeeded = pyqtSignal(str)  # the share code
    failed = pyqtSignal(str)  # error kind token

    def __init__(self, game: str, profile_name: str, payload: dict) -> None:
        super().__init__()
        self._game = game
        self._profile_name = profile_name
        self._payload = payload

    def run(self) -> None:
        try:
            self.succeeded.emit(create_share(self._game, self._profile_name, self._payload))
        except ShareApiError as exc:
            log.warning("share upload failed: %s", exc)
            self.failed.emit(_kind_for(exc))


class ShareFetchThread(QThread):
    succeeded = pyqtSignal(object)  # the raw payload (dict)
    failed = pyqtSignal(str)  # error kind token

    def __init__(self, code: str) -> None:
        super().__init__()
        self._code = code

    @property
    def code(self) -> str:
        return self._code

    def run(self) -> None:
        try:
            self.succeeded.emit(fetch_share(self._code))
        except ShareApiError as exc:
            log.warning("share lookup failed: %s", exc)
            self.failed.emit(_kind_for(exc))
