from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from easy_scsmodmanager.ui.font_helper import FontHelper  # noqa: E402


def test_font_returns_inter_family(qtbot) -> None:
    f = FontHelper.font(12)
    assert f.family() == FontHelper.FONT_NAME
    assert f.pointSize() == 12


def test_load_is_idempotent(qtbot) -> None:
    FontHelper.load()
    FontHelper.load()  # must not raise on a second call
    assert FontHelper._loaded is True


def test_apply_app_font_sets_inter(qtbot) -> None:
    app = QApplication.instance()
    FontHelper.apply_app_font(app, size=11)
    assert app.font().family() == FontHelper.FONT_NAME
