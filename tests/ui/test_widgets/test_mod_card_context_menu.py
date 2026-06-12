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


def _local(name: str = "a.scs"):
    return ScannedMod(path=Path("/mods") / name, format=ScsFormat.ZIP, manifest=None, error=None)


def _workshop(wid: str = "123456", name: str = "b.scs"):
    p = Path("/steam/steamapps/workshop/content/227300") / wid / name
    return ScannedMod(path=p, format=ScsFormat.ZIP, manifest=None, error=None)


def _delete_action(menu):
    # actions(): [show_in_active, open_location, delete]
    return menu.actions()[2]


def test_open_location_present_and_enabled_for_local(qtbot) -> None:
    mod = _local()
    card = ModCard(mod, is_active=False)
    qtbot.addWidget(card)
    # index 1, right after show_in_active; available for every mod
    action = card.build_context_menu().actions()[1]
    assert action.isEnabled() is True
    with qtbot.waitSignal(card.open_location_requested, timeout=500):
        action.trigger()


def test_open_location_enabled_for_workshop(qtbot) -> None:
    mod = _workshop()
    card = ModCard(mod, is_active=False)
    qtbot.addWidget(card)
    assert card.build_context_menu().actions()[1].isEnabled() is True


def test_delete_enabled_for_local_selection(qtbot) -> None:
    mod = _local()
    card = ModCard(mod, selection_provider=lambda: [mod])
    qtbot.addWidget(card)
    assert _delete_action(card.build_context_menu()).isEnabled() is True


def test_delete_disabled_for_workshop_only(qtbot) -> None:
    mod = _workshop()
    card = ModCard(mod, selection_provider=lambda: [mod])
    qtbot.addWidget(card)
    action = _delete_action(card.build_context_menu())
    assert action.isEnabled() is False
    assert action.toolTip() != ""


def test_delete_enabled_for_mixed_selection(qtbot) -> None:
    loc, ws = _local(), _workshop()
    card = ModCard(loc, selection_provider=lambda: [loc, ws])
    qtbot.addWidget(card)
    assert _delete_action(card.build_context_menu()).isEnabled() is True


def test_delete_emits_signal(qtbot) -> None:
    mod = _local()
    card = ModCard(mod, selection_provider=lambda: [mod])
    qtbot.addWidget(card)
    action = _delete_action(card.build_context_menu())
    with qtbot.waitSignal(card.delete_requested, timeout=500):
        action.trigger()
