"""Dialog tests for the conflict details window.

The dialog is fed finished data (a report plus the display-name map), so these
tests never touch the presenter - they only check what the user sees and what
lands in the clipboard / on disk.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QGuiApplication
from pytestqt.qtbot import QtBot

from easy_scsmodmanager.services.conflict_detect import FrequentShare, ModOverride, Severity
from easy_scsmodmanager.ui.conflict_text import ReportEntry
from easy_scsmodmanager.ui.dialogs import conflict_dialog as mod
from easy_scsmodmanager.ui.dialogs.conflict_dialog import ConflictDialog
from easy_scsmodmanager.utils.i18n import t


def _entry(name: str, display: str, *, files: int = 2) -> ReportEntry:
    lost = tuple((f"def/{name}{i}.sii", "winner") for i in range(files))
    return ReportEntry(
        name=name,
        display_name=display,
        override=ModOverride(severity=Severity.FULL, lost=lost),
        frequent=None,
    )


def _dialog(entries: list[ReportEntry], *, focus: str = "a") -> ConflictDialog:
    return ConflictDialog(
        entries,
        {"winner": "Winning Mod"},
        focus_name=focus,
        version="1.6.1",
        game="ETS2",
        profile="My Profile",
    )


def test_opens_on_the_focused_mod_only(qtbot: QtBot) -> None:
    dlg = _dialog([_entry("a", "Mod A"), _entry("b", "Mod B")])
    qtbot.addWidget(dlg)

    shown = dlg.shown_text()

    assert "Mod A" in shown
    assert "Mod B" not in shown


def test_switching_to_all_mods_lists_everything(qtbot: QtBot) -> None:
    dlg = _dialog([_entry("a", "Mod A"), _entry("b", "Mod B")])
    qtbot.addWidget(dlg)

    dlg._scope_all.setChecked(True)
    shown = dlg.shown_text()

    assert "Mod A" in shown
    assert "Mod B" in shown


def test_focused_view_shows_every_lost_file(qtbot: QtBot) -> None:
    # the whole point of the dialog: no "... and N more files" cap
    dlg = _dialog([_entry("a", "Mod A", files=30)])
    qtbot.addWidget(dlg)

    shown = dlg.shown_text()

    assert "def/a29.sii" in shown
    assert t("conflict.tooltip.more", count=18) not in shown


def test_empty_report_says_so(qtbot: QtBot) -> None:
    dlg = _dialog([], focus="nothing")
    qtbot.addWidget(dlg)

    dlg._scope_all.setChecked(True)

    assert t("conflict_dialog.empty") in dlg.shown_text()


def test_frequent_only_entry_renders(qtbot: QtBot) -> None:
    entry = ReportEntry(
        name="a",
        display_name="Mod A",
        override=None,
        frequent=FrequentShare((("def/physics.sii", 9),)),
    )
    dlg = _dialog([entry])
    qtbot.addWidget(dlg)

    shown = dlg.shown_text()

    assert "def/physics.sii" in shown
    assert t("conflict.tooltip.header_frequent") in shown


def test_copy_takes_all_mods_even_while_focused(qtbot: QtBot) -> None:
    dlg = _dialog([_entry("a", "Mod A"), _entry("b", "Mod B")])
    qtbot.addWidget(dlg)

    dlg._on_copy()
    clip = QGuiApplication.clipboard()
    assert clip is not None
    text = clip.text()

    assert "Mod A" in text and "Mod B" in text
    assert "Total mods with conflicts: 2" in text


def test_save_writes_every_mod_even_while_focused(qtbot: QtBot, tmp_path, monkeypatch) -> None:
    target = tmp_path / "log.txt"
    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    monkeypatch.setattr(mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dlg = _dialog([_entry("a", "Mod A"), _entry("b", "Mod B")])
    qtbot.addWidget(dlg)

    dlg._on_save()

    written = target.read_text(encoding="utf-8")
    assert "Mod A" in written and "Mod B" in written
    assert "1.6.1" in written and "My Profile" in written


def test_save_appends_the_extension(qtbot: QtBot, tmp_path, monkeypatch) -> None:
    chosen = tmp_path / "log"
    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(chosen), ""))
    )
    monkeypatch.setattr(mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dlg = _dialog([_entry("a", "Mod A")])
    qtbot.addWidget(dlg)

    dlg._on_save()

    assert Path(str(chosen) + ".txt").is_file()


def test_cancelled_save_writes_nothing(qtbot: QtBot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    dlg = _dialog([_entry("a", "Mod A")])
    qtbot.addWidget(dlg)

    dlg._on_save()

    assert list(tmp_path.iterdir()) == []


def test_failed_save_warns_instead_of_raising(qtbot: QtBot, tmp_path, monkeypatch) -> None:
    seen: list[str] = []
    unwritable = tmp_path / "no_such_dir" / "log.txt"
    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(unwritable), ""))
    )
    monkeypatch.setattr(
        mod.QMessageBox, "warning", staticmethod(lambda _p, _title, body: seen.append(body))
    )
    dlg = _dialog([_entry("a", "Mod A")])
    qtbot.addWidget(dlg)

    dlg._on_save()

    assert seen  # warned, did not raise
    assert not unwritable.exists()


def test_markup_in_a_mod_name_does_not_break_the_view(qtbot: QtBot) -> None:
    dlg = _dialog([_entry("a", "Ben & Jerry <Trucks>")])
    qtbot.addWidget(dlg)

    assert "Ben & Jerry <Trucks>" in dlg.shown_text()


def test_default_file_name_carries_game_and_date(qtbot: QtBot) -> None:
    dlg = _dialog([_entry("a", "Mod A")])
    qtbot.addWidget(dlg)

    name = dlg._default_file_name()

    assert name.startswith("escsmm-conflicts-ets2-")
    assert name.endswith(".txt")
