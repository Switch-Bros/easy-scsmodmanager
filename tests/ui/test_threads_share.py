"""Share threads deliver results/errors as signals off the UI thread."""

import pytest

pytest.importorskip("pytestqt")

from easy_scsmodmanager.integrations.supabase.share_api import (  # noqa: E402
    ShareConnectionError,
    ShareNotFoundError,
)
from easy_scsmodmanager.ui.threads.share_thread import (
    ShareFetchThread,
    ShareUploadThread,
)  # noqa: E402


def test_upload_emits_code(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "easy_scsmodmanager.ui.threads.share_thread.create_share",
        lambda game, name, payload: "AB2CD3",
    )
    thread = ShareUploadThread("ets2", "Sender", {"mods": []})
    with qtbot.waitSignal(thread.succeeded, timeout=2000) as blocker:
        thread.start()
    assert blocker.args == ["AB2CD3"]
    thread.wait()


def test_upload_maps_errors_to_kind(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(game, name, payload):
        raise ShareConnectionError("no net")

    monkeypatch.setattr("easy_scsmodmanager.ui.threads.share_thread.create_share", boom)
    thread = ShareUploadThread("ets2", "Sender", {})
    with qtbot.waitSignal(thread.failed, timeout=2000) as blocker:
        thread.start()
    assert blocker.args == ["connection"]
    thread.wait()


def test_fetch_emits_payload(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "easy_scsmodmanager.ui.threads.share_thread.fetch_share",
        lambda code: {"format": "easy-scsmodmanager-modshare"},
    )
    thread = ShareFetchThread("AB2CD3")
    with qtbot.waitSignal(thread.succeeded, timeout=2000) as blocker:
        thread.start()
    assert blocker.args[0]["format"] == "easy-scsmodmanager-modshare"
    thread.wait()


def test_fetch_not_found_kind(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(code):
        raise ShareNotFoundError(code)

    monkeypatch.setattr("easy_scsmodmanager.ui.threads.share_thread.fetch_share", boom)
    thread = ShareFetchThread("AB2CD3")
    with qtbot.waitSignal(thread.failed, timeout=2000) as blocker:
        thread.start()
    assert blocker.args == ["not_found"]
    thread.wait()
