from __future__ import annotations

import os

import pytest

from easy_scsmodmanager.services.update_core import (
    InstallType,
    build_update_info,
    detect_install_type,
    find_sha256sums_url,
    is_newer,
    parse_sha256sums,
    select_asset,
    version_tuple,
)


def _release(tag: str = "v2.0.0") -> dict:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/Switch-Bros/easy-scsmodmanager/releases/{tag}",
        "body": f"# {tag}\n- thing",
        "assets": [
            {
                "name": "Easy_SCSModManager-x86_64.AppImage",
                "browser_download_url": "https://example/app.AppImage",
                "size": 50_000_000,
            },
            {
                "name": "EasySCSModManager.exe",
                "browser_download_url": "https://example/app.exe",
                "size": 40_000_000,
            },
            {
                "name": "easy-scsmodmanager_2.0.0_amd64.deb",
                "browser_download_url": "https://example/app.deb",
                "size": 1_000,
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://example/SHA256SUMS.txt",
                "size": 256,
            },
        ],
    }


# version compare


def test_is_newer_handles_double_digit_patch() -> None:
    assert is_newer("1.1.10", "1.1.9") is True
    assert is_newer("1.1.9", "1.1.10") is False


def test_is_newer_same_version() -> None:
    assert is_newer("1.2.0", "1.2.0") is False


def test_version_tuple_strips_v_and_prerelease() -> None:
    assert version_tuple("v1.2.3") == (1, 2, 3)
    assert version_tuple("1.2.3rc1") == (1, 2, 3)


# install-type gating


def test_detect_install_type_appimage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPIMAGE", "/tmp/App.AppImage")
    assert detect_install_type() is InstallType.APPIMAGE


def test_detect_install_type_windows_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr("easy_scsmodmanager.services.update_core.sys.platform", "win32")
    monkeypatch.setattr("easy_scsmodmanager.services.update_core.sys.frozen", True, raising=False)
    assert detect_install_type() is InstallType.WINDOWS_EXE


def test_detect_install_type_package(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {k: v for k, v in os.environ.items() if k != "APPIMAGE"}
    monkeypatch.setattr(os, "environ", env)
    monkeypatch.setattr("easy_scsmodmanager.services.update_core.sys.platform", "linux")
    assert detect_install_type() is InstallType.PACKAGE


# asset selection per install type


def test_select_asset_appimage() -> None:
    url, name, size = select_asset(_release()["assets"], InstallType.APPIMAGE)
    assert url == "https://example/app.AppImage"
    assert name.endswith(".AppImage")
    assert size == 50_000_000


def test_select_asset_windows() -> None:
    url, name, _ = select_asset(_release()["assets"], InstallType.WINDOWS_EXE)
    assert url == "https://example/app.exe"
    assert name.endswith(".exe")


def test_select_asset_package_is_empty() -> None:
    # a .deb/.rpm/AUR user must get NO download url, even though the release
    # carries an AppImage and an exe
    assert select_asset(_release()["assets"], InstallType.PACKAGE) == ("", "", 0)


def test_build_update_info_for_package_is_check_only() -> None:
    info = build_update_info(_release(), InstallType.PACKAGE)
    assert info.version == "2.0.0"
    assert info.download_url == ""
    assert info.can_self_update is False
    assert "github.com" in info.html_url


def test_build_update_info_for_appimage_can_self_update() -> None:
    info = build_update_info(_release(), InstallType.APPIMAGE)
    assert info.can_self_update is True
    assert info.sha256sums_url == "https://example/SHA256SUMS.txt"
    assert info.asset_name.endswith(".AppImage")


# sha256sums parsing


def test_find_sha256sums_url() -> None:
    assert find_sha256sums_url(_release()["assets"]) == "https://example/SHA256SUMS.txt"


def test_parse_sha256sums_matches_filename() -> None:
    text = "aaaa1111  Easy_SCSModManager-x86_64.AppImage\n" "bbbb2222  EasySCSModManager.exe\n"
    assert parse_sha256sums(text, "Easy_SCSModManager-x86_64.AppImage") == "aaaa1111"
    assert parse_sha256sums(text, "EasySCSModManager.exe") == "bbbb2222"


def test_parse_sha256sums_handles_binary_marker_and_path() -> None:
    text = "cccc3333 *dist/EasySCSModManager.exe\n"
    assert parse_sha256sums(text, "EasySCSModManager.exe") == "cccc3333"


def test_parse_sha256sums_missing_returns_none() -> None:
    assert parse_sha256sums("aaaa  other.bin\n", "EasySCSModManager.exe") is None
