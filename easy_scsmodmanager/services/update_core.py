"""Pure update logic: install-type gating, version compare, asset picking.

Kept free of Qt and I/O so it is trivially unit-testable. The networked
QObject lives in update_service; the file-replacing parts in update_installer.

A GitHub release always ships every asset type (.AppImage AND .exe AND .deb
...), so the download URL must only be filled in for the asset that matches
*this* install - otherwise a .deb user would get install buttons that lead
nowhere. Package installs (deb/rpm/AUR/tar.gz/source) are check-only.
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from enum import Enum


class InstallType(Enum):
    APPIMAGE = "appimage"  # $APPIMAGE set - full self-update
    WINDOWS_EXE = "windows_exe"  # frozen win32 - self-update via helper batch
    PACKAGE = "package"  # deb/rpm/AUR/tar.gz/source - check only, never replace


# which asset extension each self-updatable type wants
_ASSET_SUFFIX = {
    InstallType.APPIMAGE: ".AppImage",
    InstallType.WINDOWS_EXE: ".exe",
}


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str  # "" for package installs (check-only)
    download_size: int
    asset_name: str
    sha256sums_url: str
    release_notes: str
    html_url: str

    @property
    def can_self_update(self) -> bool:
        return bool(self.download_url)


def detect_install_type() -> InstallType:
    # how was this copy installed? decides whether we may replace it
    if os.environ.get("APPIMAGE"):
        return InstallType.APPIMAGE
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        return InstallType.WINDOWS_EXE
    return InstallType.PACKAGE


def version_tuple(value: str) -> tuple[int, ...]:
    # "v1.2.3" -> (1, 2, 3); a pre-release suffix on a part stops that part
    out: list[int] = []
    for part in value.strip().lstrip("v").split("."):
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        out.append(int(digits) if digits else 0)
    return tuple(out)


def is_newer(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def select_asset(assets: list[dict], install_type: InstallType) -> tuple[str, str, int]:
    """Pick the asset for this install type: (url, name, size).

    Returns ("", "", 0) for package installs or when no matching asset exists,
    which leaves the update check-only.
    """
    suffix = _ASSET_SUFFIX.get(install_type)
    if not suffix:
        return "", "", 0
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.endswith(suffix):
            return str(asset.get("browser_download_url", "")), name, int(asset.get("size", 0))
    return "", "", 0


def find_sha256sums_url(assets: list[dict]) -> str:
    for asset in assets:
        if "SHA256SUMS" in str(asset.get("name", "")):
            return str(asset.get("browser_download_url", ""))
    return ""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_sha256sums(text: str, filename: str) -> str | None:
    """Hash for filename from a 'sha  name' SHA256SUMS listing, or None."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        digest = parts[0]
        # the name column may carry a leading '*' (binary marker) or a path
        name = parts[-1].lstrip("*")
        if name.rsplit("/", 1)[-1] == filename:
            return digest.lower()
    return None


def build_update_info(release: dict, install_type: InstallType) -> UpdateInfo:
    # turn the GitHub releases/latest JSON into our typed view
    assets = release.get("assets") or []
    url, name, size = select_asset(assets, install_type)
    return UpdateInfo(
        version=str(release.get("tag_name", "")).lstrip("v"),
        download_url=url,
        download_size=size,
        asset_name=name,
        sha256sums_url=find_sha256sums_url(assets),
        release_notes=str(release.get("body", "")),
        html_url=str(release.get("html_url", "")),
    )
