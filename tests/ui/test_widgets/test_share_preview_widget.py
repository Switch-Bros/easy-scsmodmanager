"""Preview widget renders a ShareDiff into sections."""

import pytest

pytest.importorskip("pytestqt")

from easy_scsmodmanager.services.mod_share import ShareDiff, ShareEntry  # noqa: E402
from easy_scsmodmanager.ui.widgets.share_preview_widget import SharePreviewWidget  # noqa: E402


def _diff() -> ShareDiff:
    return ShareDiff(
        found=(ShareEntry(name="have", display_name="Have It"),),
        missing_workshop=(
            (
                ShareEntry(name="mod_workshop_package.00000000000000FF", display_name="WsMod"),
                "https://steamcommunity.com/sharedfiles/filedetails/?id=255",
            ),
        ),
        missing_local=(ShareEntry(name="loc", display_name="Local Mod"),),
        outdated=(),
    )


def _empty_diff() -> ShareDiff:
    return ShareDiff(found=(), missing_workshop=(), missing_local=(), outdated=())


def test_renders_all_sections(qtbot) -> None:
    widget = SharePreviewWidget()
    qtbot.addWidget(widget)
    widget.set_diff(_diff())
    text = widget.summary_text()
    assert "Have It" in text
    assert "WsMod" in text
    assert "Local Mod" in text
    assert "id=255" in text


def test_has_missing_reflects_diff(qtbot) -> None:
    widget = SharePreviewWidget()
    qtbot.addWidget(widget)
    widget.set_diff(_diff())
    assert widget.has_missing() is True
    widget.set_diff(_empty_diff())
    assert widget.has_missing() is False


def test_copy_button_only_with_missing_local(qtbot) -> None:
    widget = SharePreviewWidget()
    qtbot.addWidget(widget)
    widget.set_diff(_diff())
    assert not widget._copy_button.isHidden()
    widget.set_diff(_empty_diff())
    assert widget._copy_button.isHidden()


def test_copy_names_targets_missing_local(qtbot) -> None:
    widget = SharePreviewWidget()
    qtbot.addWidget(widget)
    widget.set_diff(_diff())
    assert widget.missing_local_names_for_clipboard() == "Local Mod"


def test_html_escapes_display_names(qtbot) -> None:
    evil = ShareDiff(
        found=(ShareEntry(name="x", display_name="<b>bold</b> & co"),),
        missing_workshop=(),
        missing_local=(),
        outdated=(),
    )
    widget = SharePreviewWidget()
    qtbot.addWidget(widget)
    widget.set_diff(evil)
    assert "<b>bold</b>" not in widget.summary_text()
    assert "&lt;b&gt;" in widget.summary_text()


def test_url_quotes_cannot_break_href(qtbot) -> None:
    crafted = ShareDiff(
        found=(),
        missing_workshop=(
            (ShareEntry(name="mod_workshop_package.00000000000000FF"), 'https://x/"evil'),
        ),
        missing_local=(),
        outdated=(),
    )
    widget = SharePreviewWidget()
    qtbot.addWidget(widget)
    widget.set_diff(crafted)
    assert '"evil' not in widget.summary_text()
    assert "&quot;evil" in widget.summary_text()
