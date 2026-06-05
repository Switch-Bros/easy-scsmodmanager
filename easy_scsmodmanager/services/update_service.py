"""Checks GitHub for a newer release and, where allowed, installs it.

Self-update is gated by install type (see update_core): AppImage and the
frozen Windows exe replace themselves, everything else is check-only. The
download is verified against the release's SHA256SUMS before anything is
swapped in - a mismatch aborts and deletes the partial file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from easy_scsmodmanager import __version__
from easy_scsmodmanager.services.update_core import (
    InstallType,
    UpdateInfo,
    build_update_info,
    detect_install_type,
    is_newer,
    parse_sha256sums,
    sha256_hex,
)
from easy_scsmodmanager.services.update_installer import (
    current_appimage_path,
    current_exe_path,
    install_appimage,
    install_windows_exe,
)

log = logging.getLogger(__name__)

_RELEASES_URL = "https://api.github.com/repos/Switch-Bros/easy-scsmodmanager/releases/latest"
_USER_AGENT = f"EasySCSModManager/{__version__}"


class UpdateService(QObject):
    """GitHub update check + verified download + install, all non-blocking."""

    update_available = pyqtSignal(object)
    update_not_available = pyqtSignal()
    check_failed = pyqtSignal(str)
    download_progress = pyqtSignal(int, int)
    download_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._net = QNetworkAccessManager(self)
        self._info: UpdateInfo | None = None
        self._target: Path | None = None
        self._expected_sha = ""
        self._reply: QNetworkReply | None = None

    # ---- check ---------------------------------------------------------- #

    def check_for_update(self) -> None:
        reply = self._net.get(self._request(_RELEASES_URL))
        reply.finished.connect(lambda: self._on_check(reply))

    def _on_check(self, reply: QNetworkReply) -> None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            msg = reply.errorString()
            log.warning("update check failed: %s", msg)
            reply.deleteLater()
            self.check_failed.emit(msg)
            return
        try:
            release = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            reply.deleteLater()
            log.warning("update check parse failed: %s", exc)
            self.check_failed.emit(str(exc))
            return
        reply.deleteLater()

        info = build_update_info(release, detect_install_type())
        if not is_newer(info.version, __version__):
            log.info("up to date (%s)", __version__)
            self.update_not_available.emit()
            return
        log.info("update available: %s -> %s", __version__, info.version)
        self._info = info
        self.update_available.emit(info)

    # ---- download (sha256sums first, then the asset) -------------------- #

    def download_update(self, info: UpdateInfo) -> None:
        self._info = info
        self._target = self._download_target()
        if self._target is None or not info.download_url:
            self.download_failed.emit("no self-update for this install")
            return
        if info.sha256sums_url:
            r = self._net.get(self._request(info.sha256sums_url))
            r.finished.connect(lambda: self._on_sha(r))
        else:
            self._expected_sha = ""
            self._start_asset_download()

    def _on_sha(self, reply: QNetworkReply) -> None:
        self._expected_sha = ""
        if reply.error() == QNetworkReply.NetworkError.NoError and self._info is not None:
            text = bytes(reply.readAll()).decode("utf-8", "replace")
            self._expected_sha = parse_sha256sums(text, self._info.asset_name) or ""
        reply.deleteLater()
        self._start_asset_download()

    def _start_asset_download(self) -> None:
        if self._info is None:
            return
        self._reply = self._net.get(self._request(self._info.download_url))
        self._reply.downloadProgress.connect(self.download_progress.emit)
        self._reply.finished.connect(self._on_asset)

    def _on_asset(self) -> None:
        reply = self._reply
        if reply is None or self._target is None:
            return
        if reply.error() != QNetworkReply.NetworkError.NoError:
            msg = reply.errorString()
            reply.deleteLater()
            self._reply = None
            log.error("download failed: %s", msg)
            self.download_failed.emit(msg)
            return

        data = bytes(reply.readAll())
        reply.deleteLater()
        self._reply = None

        if self._expected_sha and sha256_hex(data) != self._expected_sha:
            log.error("update hash mismatch, discarding download")
            self.download_failed.emit("checksum mismatch")
            return

        try:
            self._target.write_bytes(data)
        except OSError as exc:
            log.error("could not write update: %s", exc)
            self.download_failed.emit(str(exc))
            return
        log.info("update downloaded: %s", self._target)
        self.download_finished.emit(str(self._target))

    def cancel(self) -> None:
        if self._reply is not None:
            self._reply.abort()
        if self._target is not None and self._target.exists():
            self._target.unlink(missing_ok=True)

    # ---- install -------------------------------------------------------- #

    @staticmethod
    def install(path: str) -> bool:
        itype = detect_install_type()
        if itype is InstallType.APPIMAGE:
            return install_appimage(path)
        if itype is InstallType.WINDOWS_EXE:
            return install_windows_exe(path)
        return False

    # ---- helpers -------------------------------------------------------- #

    def _download_target(self) -> Path | None:
        itype = detect_install_type()
        if itype is InstallType.APPIMAGE:
            cur = current_appimage_path()
            return cur.parent / ".escsmm_update.AppImage" if cur else None
        if itype is InstallType.WINDOWS_EXE:
            cur = current_exe_path()
            return cur.with_name(cur.stem + "_new.exe")
        return None

    @staticmethod
    def _request(url: str) -> QNetworkRequest:
        req = QNetworkRequest(QUrl(url))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, _USER_AGENT)
        return req
