"""Smoke test that the main window can be constructed and shown.

Uses pytest-qt's qtbot to manage the QApplication lifecycle.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from easy_scsmodmanager.ui.main_window import MainWindow  # noqa: E402


def test_main_window_constructs(qtbot) -> None:
    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    assert window.windowTitle().startswith("Easy SCSModManager")
    assert window.minimumWidth() >= 1000


_PROFILE_TEMPLATE = (
    "SiiNunit\n{\nuser_profile : _nameless.x {\n" ' profile_name: "T"\n active_mods: 0\n}\n}\n'
)


def test_save_writes_active_list_to_profile(qtbot, tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from easy_scsmodmanager.services.profile_reader import ActiveMod, read_profile

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)

    sii = tmp_path / "profiles" / "abc" / "profile.sii"
    sii.parent.mkdir(parents=True)
    sii.write_text(_PROFILE_TEMPLATE, encoding="utf-8")
    window._profile_sii_path = sii
    window._profile = read_profile(sii)
    window._active_list.set_active_mods([ActiveMod("a", "A"), ActiveMod("b", "B")])

    # user declines the pre-save backup
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window._on_save_clicked()

    assert [m.name for m in read_profile(sii).active_mods] == ["a", "b"]


def test_save_aborts_on_cancel(qtbot, tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from easy_scsmodmanager.services.profile_reader import ActiveMod, read_profile

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)

    sii = tmp_path / "profiles" / "abc" / "profile.sii"
    sii.parent.mkdir(parents=True)
    sii.write_text(_PROFILE_TEMPLATE, encoding="utf-8")
    window._profile_sii_path = sii
    window._profile = read_profile(sii)
    window._active_list.set_active_mods([ActiveMod("a", "A")])

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    window._on_save_clicked()

    # nothing written - still zero active mods on disk
    assert list(read_profile(sii).active_mods) == []


def test_double_click_grid_card_adds_mod_to_active_top(qtbot) -> None:
    from pathlib import Path

    from easy_scsmodmanager.core.models.mod_manifest import ModManifest
    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    window._active_list.set_active_mods([ActiveMod("existing", "Existing")])

    mod = ScannedMod(
        path=Path("/mod/newmod.scs"),
        format=ScsFormat.ZIP,
        manifest=ModManifest(display_name="New Mod"),
        error=None,
    )
    window._on_mod_activated(mod)

    assert window._active_list.display_order()[0].name == "newmod"
    assert window._save_btn.isEnabled() is True


def test_drop_from_grid_inserts_mods_at_row(qtbot) -> None:
    from pathlib import Path

    from easy_scsmodmanager.core.models.mod_manifest import ModManifest
    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    dropped = ScannedMod(
        path=Path("/mod/dropme.scs"),
        format=ScsFormat.ZIP,
        manifest=ModManifest(display_name="Drop Me"),
        error=None,
    )
    window._all_mods = [dropped]
    window._active_list.set_active_mods([ActiveMod("existing", "Existing")])

    window._on_mods_dropped(["/mod/dropme.scs"], 0)  # drop at display top

    assert window._active_list.display_order()[0].name == "dropme"
    assert window._active_list.display_order()[0].display_name == "Drop Me"


def test_drop_skips_already_active_mod(qtbot) -> None:
    from pathlib import Path

    from easy_scsmodmanager.core.models.mod_manifest import ModManifest
    from easy_scsmodmanager.integrations.scs.detector import ScsFormat
    from easy_scsmodmanager.services.mod_scanner import ScannedMod
    from easy_scsmodmanager.services.profile_reader import ActiveMod

    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    mod = ScannedMod(
        path=Path("/mod/already.scs"),
        format=ScsFormat.ZIP,
        manifest=ModManifest(display_name="Already"),
        error=None,
    )
    window._all_mods = [mod]
    window._active_list.set_active_mods([ActiveMod("already", "Already")])

    window._on_mods_dropped(["/mod/already.scs"], 0)

    names = [m.name for m in window._active_list.display_order()]
    assert names.count("already") == 1  # not duplicated


def test_restore_reachable_when_profile_failed_to_parse(qtbot, tmp_path, monkeypatch) -> None:
    # the whole point of restore is to recover a profile that no longer parses
    window = MainWindow(auto_scan=False)
    qtbot.addWidget(window)
    window._profile_sii_path = tmp_path / "profile.sii"
    window._profile = None  # corrupt / unparseable

    monkeypatch.setattr("easy_scsmodmanager.ui.main_window.list_backups", lambda p: [])
    window._on_restore_requested()

    # reached the "no backups" branch (status set) instead of silently returning
    assert window.statusBar().currentMessage() != ""
