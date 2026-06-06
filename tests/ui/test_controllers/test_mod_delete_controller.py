from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from PyQt6.QtWidgets import QWidget  # noqa: E402

from easy_scsmodmanager.integrations.scs.detector import ScsFormat  # noqa: E402
from easy_scsmodmanager.services.mod_scanner import ScannedMod  # noqa: E402
from easy_scsmodmanager.ui.controllers import mod_delete_controller as mdc  # noqa: E402
from easy_scsmodmanager.ui.controllers.mod_delete_controller import (
    ModDeleteController,
)  # noqa: E402


def _local(name: str) -> ScannedMod:
    return ScannedMod(path=Path("/mods") / name, format=ScsFormat.ZIP, manifest=None, error=None)


def _workshop(wid: str = "999") -> ScannedMod:
    p = Path("/steam/steamapps/workshop/content/227300") / wid / "w.scs"
    return ScannedMod(path=p, format=ScsFormat.ZIP, manifest=None, error=None)


def _make(qtbot, **over):
    parent = QWidget()
    qtbot.addWidget(parent)
    kw = dict(
        parent=parent,
        profiles=lambda: [],
        display_name_for=lambda m: m.path.stem,
        on_mods_deleted=lambda d: None,
        show_status=lambda *a: None,
    )
    kw.update(over)
    return ModDeleteController(**kw)


def test_only_locals_deleted_workshop_skipped(qtbot, monkeypatch) -> None:
    deleted: list = []
    ctrl = _make(qtbot, on_mods_deleted=deleted.append)
    monkeypatch.setattr(ctrl, "_confirm", lambda *a: True)
    monkeypatch.setattr(mdc, "move_path_to_trash", lambda p: True)

    ctrl.request_delete([_local("a.scs"), _workshop()])

    assert len(deleted) == 1
    assert [m.path.name for m in deleted[0]] == ["a.scs"]


def test_workshop_only_does_nothing(qtbot, monkeypatch) -> None:
    deleted: list = []
    ctrl = _make(qtbot, on_mods_deleted=deleted.append)
    confirmed = []
    monkeypatch.setattr(ctrl, "_confirm", lambda *a: confirmed.append(True) or True)

    ctrl.request_delete([_workshop()])

    assert deleted == []
    assert confirmed == []  # no dialog for a workshop-only selection


def test_cancel_deletes_nothing(qtbot, monkeypatch) -> None:
    deleted: list = []
    ctrl = _make(qtbot, on_mods_deleted=deleted.append)
    monkeypatch.setattr(ctrl, "_confirm", lambda *a: False)
    monkeypatch.setattr(mdc, "move_path_to_trash", lambda p: pytest.fail("must not trash"))

    ctrl.request_delete([_local("a.scs")])

    assert deleted == []


def test_failed_trash_continues_with_rest(qtbot, monkeypatch) -> None:
    deleted: list = []
    ctrl = _make(qtbot, on_mods_deleted=deleted.append)
    monkeypatch.setattr(ctrl, "_confirm", lambda *a: True)
    monkeypatch.setattr(mdc.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    # first fails, second succeeds
    results = {"a.scs": False, "b.scs": True}
    monkeypatch.setattr(mdc, "move_path_to_trash", lambda p: results[p.name])

    ctrl.request_delete([_local("a.scs"), _local("b.scs")])

    assert len(deleted) == 1
    assert [m.path.name for m in deleted[0]] == ["b.scs"]


def test_no_hard_delete_in_module() -> None:
    src = Path(mdc.__file__).read_text()
    assert "os.remove" not in src
    assert ".unlink(" not in src
    assert "rmtree" not in src
