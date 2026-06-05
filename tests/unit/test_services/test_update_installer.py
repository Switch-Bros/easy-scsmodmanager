from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from easy_scsmodmanager.services import update_installer as ui
from easy_scsmodmanager.services.update_core import sha256_hex


def test_sha256_hex_matches_hashlib() -> None:
    data = b"hello update"
    assert sha256_hex(data) == hashlib.sha256(data).hexdigest()


def test_install_appimage_no_env_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert ui.install_appimage("/tmp/new.AppImage") is False


def test_install_appimage_backs_up_and_replaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cur = tmp_path / "Easy_SCSModManager.AppImage"
    cur.write_text("old")
    new = tmp_path / ".escsmm_update.AppImage"
    new.write_text("new")

    monkeypatch.setenv("APPIMAGE", str(cur))
    monkeypatch.setattr(os, "execv", lambda *a: (_ for _ in ()).throw(SystemExit(0)))

    with pytest.raises(SystemExit):
        ui.install_appimage(str(new))

    bak = cur.with_suffix(".bak")
    assert bak.read_text() == "old"
    assert cur.read_text() == "new"


def test_install_appimage_rolls_back_on_exec_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cur = tmp_path / "Easy_SCSModManager.AppImage"
    cur.write_text("old")
    new = tmp_path / ".escsmm_update.AppImage"
    new.write_text("new")

    monkeypatch.setenv("APPIMAGE", str(cur))
    monkeypatch.setattr(os, "execv", lambda *a: (_ for _ in ()).throw(OSError("nope")))

    assert ui.install_appimage(str(new)) is False
    assert cur.read_text() == "old"  # rolled back


def test_windows_helper_batch_contains_pid_and_swap() -> None:
    bat = ui.windows_helper_batch(Path(r"C:\app\ESCSMM.exe"), Path(r"C:\app\new.exe"), 4321)
    assert "PID eq 4321" in bat
    assert "ESCSMM.exe.bak" in bat
    assert 'start ""' in bat
    assert "del" in bat


def test_install_windows_exe_launches_helper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    new = tmp_path / "new.exe"
    new.write_text("binary")

    launched: dict[str, object] = {}

    def fake_popen(cmd, **kw):
        launched["cmd"] = cmd
        return object()

    monkeypatch.setattr(ui.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(ui, "current_exe_path", lambda: tmp_path / "ESCSMM.exe")

    assert ui.install_windows_exe(str(new)) is True
    assert launched["cmd"][0] == "cmd"


def test_install_windows_exe_missing_new_returns_false(tmp_path: Path) -> None:
    assert ui.install_windows_exe(str(tmp_path / "absent.exe")) is False
