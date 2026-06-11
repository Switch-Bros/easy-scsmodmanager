"""Create-code dialog: upload flow, code display, error display."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from easy_scsmodmanager.ui.dialogs.share_create_dialog import ShareCreateDialog  # noqa: E402


class _Signal:
    def __init__(self) -> None:
        self._slots = []

    def connect(self, slot) -> None:
        self._slots.append(slot)

    def disconnect(self, slot) -> None:
        self._slots.remove(slot)

    def emit(self, *args) -> None:
        for slot in self._slots:
            slot(*args)


class _FakeThread:
    """Stands in for ShareUploadThread: capture args, fire callbacks manually."""

    instances: list[_FakeThread] = []

    def __init__(self, game: str, profile_name: str, payload: dict) -> None:
        self.game, self.profile_name, self.payload = game, profile_name, payload
        self.succeeded = _Signal()
        self.failed = _Signal()
        self.waited: list[int] = []
        _FakeThread.instances.append(self)

    def start(self) -> None:
        pass

    def isRunning(self) -> bool:
        return True

    def wait(self, msecs: int) -> bool:
        self.waited.append(msecs)
        return True

    def disconnect_all(self) -> None:
        self.succeeded._slots.clear()
        self.failed._slots.clear()


@pytest.fixture(autouse=True)
def _patch_thread(monkeypatch: pytest.MonkeyPatch):
    _FakeThread.instances.clear()
    monkeypatch.setattr(
        "easy_scsmodmanager.ui.dialogs.share_create_dialog.ShareUploadThread", _FakeThread
    )


def _dialog(qtbot) -> ShareCreateDialog:
    dlg = ShareCreateDialog(game="ets2", profile_name="Sender", payload={"mods": [1]})
    qtbot.addWidget(dlg)
    return dlg


def test_create_starts_upload_with_payload(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg._create_button.click()
    assert len(_FakeThread.instances) == 1
    assert _FakeThread.instances[0].profile_name == "Sender"
    assert not dlg._create_button.isEnabled()


def test_success_shows_code_and_copy(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg._create_button.click()
    _FakeThread.instances[0].succeeded.emit("AB2CD3")
    assert dlg._code_label.text() == "AB2CD3"
    assert not dlg._copy_button.isHidden()
    assert not dlg._ttl_label.isHidden()


def test_failure_shows_translated_error_and_reenables(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg._create_button.click()
    _FakeThread.instances[0].failed.emit("connection")
    assert dlg._error_label.text() != ""
    assert dlg._create_button.isEnabled()


def test_copy_button_puts_code_on_clipboard(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg._create_button.click()
    _FakeThread.instances[0].succeeded.emit("AB2CD3")
    dlg._copy_button.click()
    from PyQt6.QtWidgets import QApplication

    assert QApplication.clipboard().text() == "AB2CD3"


def test_shutdown_waits_for_running_upload(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg._create_button.click()
    dlg.shutdown(50)
    assert _FakeThread.instances[0].waited == [50]


def test_shutdown_without_upload_is_safe(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg.shutdown(50)
    assert _FakeThread.instances == []


def test_close_while_uploading_detaches_thread_signals(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg._create_button.click()
    thread = _FakeThread.instances[0]
    dlg.close()
    assert thread.succeeded._slots == []
    assert thread.failed._slots == []
    thread.succeeded.emit("AB2CD3")  # must be harmless now
