"""Import dialog: source toggle, debounced code lookup, preview, apply gating."""

import pytest

pytest.importorskip("pytestqt")

from easy_scsmodmanager.core.game_paths import Game  # noqa: E402
from easy_scsmodmanager.services.mod_share import (  # noqa: E402
    ShareEntry,
    ShareList,
    diff,
)
from easy_scsmodmanager.ui.dialogs.share_import_dialog import ShareImportDialog  # noqa: E402


def _share() -> ShareList:
    return ShareList(
        game=Game.ETS2,
        profile_name="Sender",
        entries=(ShareEntry(name="a", display_name="A"),),
    )


def _dialog(qtbot) -> ShareImportDialog:
    dlg = ShareImportDialog()
    qtbot.addWidget(dlg)
    dlg.set_target_profile("MyProfile")
    return dlg


def test_code_input_normalizes_and_debounces(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg.set_source("code")
    with qtbot.waitSignal(dlg.code_lookup_requested, timeout=2000) as blocker:
        dlg._code_edit.setText("ab2cd3")
    assert blocker.args == ["AB2CD3"]


def test_short_code_does_not_start_debounce(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg.set_source("code")
    dlg._code_edit.setText("AB2CD")
    assert not dlg._debounce.isActive()


def test_source_toggle_shows_matching_controls(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg.set_source("file")
    assert dlg._code_edit.isHidden()
    assert not dlg._pick_file_button.isHidden()
    assert dlg._pick_profile_button.isHidden()
    dlg.set_source("profile")
    assert dlg._pick_file_button.isHidden()
    assert not dlg._pick_profile_button.isHidden()


def test_show_share_enables_apply_when_game_matches(qtbot) -> None:
    dlg = _dialog(qtbot)
    share = _share()
    dlg.show_share(share, diff(share, installed={"a": ""}), game_matches=True)
    assert dlg._apply_button.isEnabled()
    assert "MyProfile" in dlg._apply_button.text()
    assert dlg.current_share() == share


def test_game_mismatch_locks_apply_and_says_why(qtbot) -> None:
    dlg = _dialog(qtbot)
    share = _share()
    dlg.show_share(share, diff(share, installed={"a": ""}), game_matches=False)
    assert not dlg._apply_button.isEnabled()
    assert dlg._status_label.text() != ""


def test_show_error_clears_share_and_disables_apply(qtbot) -> None:
    dlg = _dialog(qtbot)
    share = _share()
    dlg.show_share(share, diff(share, installed={"a": ""}), game_matches=True)
    dlg.show_error("boom")
    assert dlg.current_share() is None
    assert not dlg._apply_button.isEnabled()
    assert dlg._status_label.text() == "boom"


def test_include_missing_default_on(qtbot) -> None:
    dlg = _dialog(qtbot)
    assert dlg.include_missing() is True


def test_recheck_visible_only_with_missing(qtbot) -> None:
    dlg = _dialog(qtbot)
    share = _share()
    dlg.show_share(share, diff(share, installed={}), game_matches=True)
    assert not dlg._recheck_button.isHidden()
    dlg.show_share(share, diff(share, installed={"a": ""}), game_matches=True)
    assert dlg._recheck_button.isHidden()


def test_apply_emits_signal(qtbot) -> None:
    dlg = _dialog(qtbot)
    share = _share()
    dlg.show_share(share, diff(share, installed={"a": ""}), game_matches=True)
    with qtbot.waitSignal(dlg.apply_requested, timeout=1000):
        dlg._apply_button.click()


def test_lookup_busy_clears_stale_share(qtbot) -> None:
    dlg = _dialog(qtbot)
    share = _share()
    dlg.show_share(share, diff(share, installed={"a": ""}), game_matches=True)
    dlg.show_lookup_busy()
    assert dlg.current_share() is None
    assert not dlg._apply_button.isEnabled()
    assert dlg._recheck_button.isHidden()


def test_error_clears_preview_and_recheck(qtbot) -> None:
    dlg = _dialog(qtbot)
    share = _share()
    dlg.show_share(
        share, diff(share, installed={}), game_matches=True
    )  # has missing -> recheck visible
    dlg.show_error("boom")
    assert dlg._recheck_button.isHidden()
    assert "A" not in dlg._preview.summary_text()


def test_pasted_code_with_leading_junk_normalizes_fully(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg.set_source("code")
    with qtbot.waitSignal(dlg.code_lookup_requested, timeout=2000) as blocker:
        dlg._code_edit.setText(" ab2cd3")
    assert blocker.args == ["AB2CD3"]


def test_reset_clears_share_status_and_code(qtbot) -> None:
    dlg = _dialog(qtbot)
    share = _share()
    dlg._code_edit.setText("AB2CD3")
    # game mismatch fills the status label
    dlg.show_share(share, diff(share, installed={"a": ""}), game_matches=False)
    dlg.reset()
    assert dlg.current_share() is None
    assert not dlg._apply_button.isEnabled()
    assert dlg._status_label.text() == ""
    assert dlg._code_edit.text() == ""
    assert dlg._recheck_button.isHidden()


def test_source_switch_cancels_pending_lookup(qtbot) -> None:
    dlg = _dialog(qtbot)
    dlg.set_source("code")
    dlg._code_edit.setText("AB2CD3")
    assert dlg._debounce.isActive()
    dlg.set_source("file")
    assert not dlg._debounce.isActive()
