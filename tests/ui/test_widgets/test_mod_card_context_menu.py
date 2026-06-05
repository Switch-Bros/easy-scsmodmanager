from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.ui.widgets.mod_card import ModCard


def _scanned() -> ScannedMod:
    return ScannedMod(path=Path("/tmp/mod.scs"), format=ScsFormat.ZIP, manifest=None, error=None)


def test_show_in_active_disabled_for_inactive_mod(qtbot: QtBot) -> None:
    card = ModCard(_scanned(), is_active=False)
    qtbot.addWidget(card)

    menu = card.build_context_menu()
    assert menu.actions()[0].isEnabled() is False


def test_show_in_active_enabled_and_emits_for_active_mod(qtbot: QtBot) -> None:
    card = ModCard(_scanned(), is_active=True)
    qtbot.addWidget(card)

    menu = card.build_context_menu()
    action = menu.actions()[0]
    assert action.isEnabled() is True

    with qtbot.waitSignal(card.show_in_active_requested, timeout=500):
        action.trigger()
