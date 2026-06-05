from __future__ import annotations

from pathlib import Path

import pytest

from easy_scsmodmanager.services import update_service as us
from easy_scsmodmanager.services.update_core import InstallType


@pytest.fixture
def service(qapp):
    return us.UpdateService()


def test_download_target_appimage(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(us, "detect_install_type", lambda: InstallType.APPIMAGE)
    monkeypatch.setattr(us, "current_appimage_path", lambda: Path("/opt/app/ESCSMM.AppImage"))
    assert service._download_target() == Path("/opt/app/.escsmm_update.AppImage")


def test_download_target_windows(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(us, "detect_install_type", lambda: InstallType.WINDOWS_EXE)
    monkeypatch.setattr(us, "current_exe_path", lambda: Path(r"C:\app\ESCSMM.exe"))
    assert service._download_target() == Path(r"C:\app\ESCSMM_new.exe")


def test_download_target_package_is_none(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(us, "detect_install_type", lambda: InstallType.PACKAGE)
    assert service._download_target() is None


def test_install_dispatch_package_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(us, "detect_install_type", lambda: InstallType.PACKAGE)
    assert us.UpdateService.install("/tmp/whatever") is False


def test_install_dispatch_appimage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(us, "detect_install_type", lambda: InstallType.APPIMAGE)
    seen: dict[str, str] = {}

    def fake_install(p: str) -> bool:
        seen["p"] = p
        return True

    monkeypatch.setattr(us, "install_appimage", fake_install)
    assert us.UpdateService.install("/tmp/new.AppImage") is True
    assert seen["p"] == "/tmp/new.AppImage"


def test_download_update_without_url_fails(service, monkeypatch: pytest.MonkeyPatch) -> None:
    from easy_scsmodmanager.services.update_core import UpdateInfo

    monkeypatch.setattr(us, "detect_install_type", lambda: InstallType.PACKAGE)
    info = UpdateInfo("2.0.0", "", 0, "", "", "notes", "https://x")
    failures: list[str] = []
    service.download_failed.connect(failures.append)

    service.download_update(info)

    assert failures  # a check-only build cannot download
