"""Replace the running app with a freshly downloaded build.

Two very different jobs:

* AppImage - the file is just a binary we own, so back it up, swap it in
  atomically and re-exec. Roll back from the .bak if anything throws.
* Windows .exe - a running exe is locked and cannot replace itself, so we
  drop a tiny helper batch that waits for us to quit, swaps the files and
  relaunches. We only kick it off and report whether the launch worked.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def current_appimage_path() -> Path | None:
    ai = os.environ.get("APPIMAGE")
    return Path(ai) if ai else None


def install_appimage(new_path: str) -> bool:
    """Swap the new AppImage in for the running one and re-exec. False on setup failure."""
    cur = current_appimage_path()
    new = Path(new_path)
    if cur is None or not cur.exists():
        return False

    bak = cur.with_suffix(".bak")
    try:
        shutil.copy2(cur, bak)
        new.chmod(0o755)
        new.replace(cur)  # atomic on the same filesystem
        log.info("installing AppImage update: %s", cur)
        os.execv(str(cur), [str(cur)])  # never returns on success
    except Exception as exc:
        log.error("AppImage update failed, rolling back: %s", exc)
        if bak.exists():
            bak.replace(cur)
        return False
    return True  # pragma: no cover - unreachable after execv


def current_exe_path() -> Path:
    return Path(sys.executable)


def windows_helper_batch(current: Path, new: Path, pid: int) -> str:
    """The .bat that waits for our PID to die, swaps the exe and relaunches.

    ``chcp 65001`` + a UTF-8 (no BOM) file let it run on a CJK install path. The
    ``current -> bak`` move happens ONCE before the retry loop; only ``new ->
    current`` is retried (the locked-target case). If every retry fails the
    backup is restored and the OLD exe relaunched, so a failed swap never leaves
    the user without a runnable app. Everything is logged for diagnosis.
    """
    return (
        "@echo off\r\n"
        "chcp 65001 >NUL\r\n"
        'set "LOG=%TEMP%\\escsmm_update.log"\r\n'
        f'echo [start] waiting for PID {pid} >> "%LOG%"\r\n'
        ":wait\r\n"
        f'tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL\r\n'
        "if not errorlevel 1 ( timeout /t 1 /nobreak >NUL & goto wait )\r\n"
        f'move /Y "{current}" "{current}.bak" >> "%LOG%" 2>&1\r\n'
        "set /a tries=0\r\n"
        ":swap\r\n"
        f'move /Y "{new}" "{current}" >> "%LOG%" 2>&1\r\n'
        f'if not exist "{new}" goto ok\r\n'
        "set /a tries+=1\r\n"
        "if %tries% geq 10 goto fail\r\n"
        'echo [retry %tries%] target locked >> "%LOG%"\r\n'
        "timeout /t 1 /nobreak >NUL\r\n"
        "goto swap\r\n"
        ":ok\r\n"
        'echo [ok] swapped, relaunch >> "%LOG%"\r\n'
        f'start "" "{current}"\r\n'
        "goto done\r\n"
        ":fail\r\n"
        'echo [error] swap failed after retries, restoring backup >> "%LOG%"\r\n'
        f'move /Y "{current}.bak" "{current}" >> "%LOG%" 2>&1\r\n'
        f'start "" "{current}"\r\n'
        ":done\r\n"
        'del "%~f0"\r\n'
    )


def install_windows_exe(new_path: str) -> bool:
    """Launch the swap-and-restart helper, then the caller should quit. False on failure."""
    cur = current_exe_path()
    new = Path(new_path)
    if not new.exists():
        return False

    try:
        script = windows_helper_batch(cur, new, os.getpid())
        fd, bat = tempfile.mkstemp(suffix=".bat", prefix="escsmm_update_")
        # utf-8 (NOT utf-8-sig) - a BOM would break the leading @echo off
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(script)
        # detached so it survives us exiting; flags only exist on Windows
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
        subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True)
        log.info("launched Windows update helper: %s", bat)
    except Exception as exc:
        log.error("Windows update helper failed to launch: %s", exc)
        return False
    return True
