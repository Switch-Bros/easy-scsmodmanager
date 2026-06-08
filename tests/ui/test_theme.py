from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PyQt6.QtGui import QPalette  # noqa: E402

from easy_scsmodmanager.ui.theme import Theme  # noqa: E402

# ---- WCAG contrast (pure, no Qt) ----------------------------------------- #


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    chans = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4) for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_primary_text_contrast_meets_4_5() -> None:
    assert _contrast(Theme.TEXT, Theme.BACKGROUND) >= 4.5
    assert _contrast(Theme.TEXT, Theme.SURFACE) >= 4.5


def test_secondary_text_contrast_meets_3() -> None:
    assert _contrast(Theme.TEXT_DIM, Theme.SURFACE) >= 3.0


def test_disabled_and_selection_contrast_meets_3() -> None:
    assert _contrast(Theme.TEXT_DISABLED, Theme.BACKGROUND) >= 3.0
    assert _contrast(Theme.SELECTION_TEXT, Theme.SELECTION) >= 3.0


def test_danger_button_text_contrast_meets_4_5() -> None:
    # white text on the destructive button, base and hover both legible
    assert _contrast(Theme.ON_DANGER, Theme.DANGER) >= 4.5
    assert _contrast(Theme.ON_DANGER, Theme.DANGER_HOVER) >= 4.5


def test_bvb_yellow_is_high_contrast_on_background() -> None:
    # mod names + warning glyph are BVB yellow (#FDE100), ~13.2:1 on the dark bg
    assert Theme.WARNING == "#FDE100"
    assert _contrast(Theme.WARNING, Theme.BACKGROUND) >= 13.0


def test_two_layer_semantic_tokens_resolve_to_raw_marks() -> None:
    # layer-2 tokens reference layer-1 marks, not stray hex
    assert Theme.ACCENT == Theme.YELLOW
    assert Theme.ACCENT_HOVER == Theme.YELLOW_LT
    assert Theme.TEXT_MOD_NAME == Theme.YELLOW
    assert Theme.MISPLACED == Theme.ORANGE
    assert Theme.ON_DANGER == Theme.WHITE


# ---- GLOBAL_QSS selectors ------------------------------------------------- #


@pytest.mark.parametrize(
    "selector",
    ["QMenuBar", "QCheckBox", "QComboBox QAbstractItemView", "QToolTip", "QScrollBar"],
)
def test_global_qss_contains_selector(selector: str) -> None:
    assert selector in Theme.GLOBAL_QSS


# ---- palette (needs a QApplication) -------------------------------------- #


def _name(color) -> str:
    # QColor.name() is lowercase; the tokens are uppercase
    return color.name().lower()


def test_build_palette_sets_dark_roles(qapp) -> None:
    pal = Theme.build_palette()
    roles = QPalette.ColorRole

    assert _name(pal.color(roles.Window)) == Theme.BACKGROUND.lower()
    assert _name(pal.color(roles.WindowText)) == Theme.TEXT.lower()
    assert _name(pal.color(roles.Base)) == Theme.SURFACE.lower()
    assert _name(pal.color(roles.Text)) == Theme.TEXT.lower()
    assert _name(pal.color(roles.Highlight)) == Theme.SELECTION.lower()
    assert _name(pal.color(roles.HighlightedText)) == Theme.SELECTION_TEXT.lower()
    assert _name(pal.color(roles.PlaceholderText)) == Theme.PLACEHOLDER.lower()


def test_build_palette_sets_disabled_group(qapp) -> None:
    pal = Theme.build_palette()
    disabled = pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
    assert _name(disabled) == Theme.TEXT_DISABLED.lower()


# ---- smoke: applying the theme does not raise ---------------------------- #


def test_apply_dark_theme_is_safe(qapp) -> None:
    from easy_scsmodmanager.app import _apply_dark_theme

    _apply_dark_theme(qapp)

    # palette and global stylesheet are both in place (Fusion gets wrapped in a
    # QStyleSheetStyle once a stylesheet is set, so we check the effects instead)
    assert _name(qapp.palette().color(QPalette.ColorRole.Window)) == Theme.BACKGROUND.lower()
    assert qapp.styleSheet() == Theme.GLOBAL_QSS
