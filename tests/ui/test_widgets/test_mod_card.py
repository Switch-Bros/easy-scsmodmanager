from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from pytestqt.qtbot import QtBot

from easy_scsmodmanager.core.mod_categories import effective_categories, i18n_key
from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.widgets.mod_card import ModCard
from easy_scsmodmanager.utils.i18n import t


def _scanned(
    path: Path = Path("/tmp/mod.scs"),
    manifest: ModManifest | None = None,
    error: str | None = None,
    fmt: ScsFormat = ScsFormat.ZIP,
) -> ScannedMod:
    return ScannedMod(path=path, format=fmt, manifest=manifest, error=error)


def test_renders_manifest_name_and_author(qtbot: QtBot) -> None:
    mod = _scanned(
        manifest=ModManifest(display_name="Real Train Sounds", author="Cip", categories=("sound",))
    )
    card = ModCard(mod)
    qtbot.addWidget(card)

    assert "Real Train Sounds" in card._name_label.text()
    assert "Cip" in card._author_label.text()
    # Raw tag "sound" is shown via its official, localized game name.
    assert card._category.text() == t(i18n_key("sound")).upper()


def test_multiple_categories_joined_with_slash(qtbot: QtBot) -> None:
    mod = _scanned(manifest=ModManifest(display_name="x", categories=("tuning_parts", "interior")))
    card = ModCard(mod)
    qtbot.addWidget(card)

    expected = " / ".join(t(i18n_key(c)) for c in ("tuning_parts", "interior")).upper()
    assert card._category.text() == expected
    assert "/" in card._category.text()


def test_unknown_category_falls_back_to_other(qtbot: QtBot) -> None:
    mod = _scanned(manifest=ModManifest(display_name="x", categories=("donbass_map",)))
    card = ModCard(mod)
    qtbot.addWidget(card)

    assert card._category.text() == t(i18n_key("other")).upper()


def test_falls_back_to_filename_when_no_manifest(qtbot: QtBot) -> None:
    mod = _scanned(path=Path("/tmp/unknown_mod.scs"), manifest=None, error="bad")
    card = ModCard(mod)
    qtbot.addWidget(card)

    assert "unknown_mod" in card._name_label.text()


def test_status_for_active_mod_is_active(qtbot: QtBot) -> None:
    mod = _scanned(manifest=ModManifest(display_name="x"))
    card = ModCard(mod, is_active=True)
    qtbot.addWidget(card)

    assert card._status_kind() == "active"
    assert Theme.SUCCESS in card._status_indicator.styleSheet()


def test_status_for_inactive_mod_with_manifest_is_inactive(qtbot: QtBot) -> None:
    mod = _scanned(manifest=ModManifest(display_name="x"))
    card = ModCard(mod, is_active=False)
    qtbot.addWidget(card)

    assert card._status_kind() == "inactive"
    assert Theme.MUTED in card._status_indicator.styleSheet()


def test_status_for_error_mod_is_error(qtbot: QtBot) -> None:
    # An "error" mod (e.g. encrypted manifest) is still installed and
    # works in-game; we only mean "metadata not parseable". Render with
    # the muted colour, not the incompatible/danger red.
    mod = _scanned(manifest=None, error="missing manifest")
    card = ModCard(mod)
    qtbot.addWidget(card)

    assert card._status_kind() == "error"
    assert Theme.MUTED in card._status_indicator.styleSheet()


def test_set_active_updates_status_indicator(qtbot: QtBot) -> None:
    mod = _scanned(manifest=ModManifest(display_name="x"))
    card = ModCard(mod, is_active=False)
    qtbot.addWidget(card)

    card.set_active(True)

    assert card.is_active is True
    assert Theme.SUCCESS in card._status_indicator.styleSheet()


def test_set_selected_changes_border(qtbot: QtBot) -> None:
    card = ModCard(_scanned(manifest=ModManifest(display_name="x")))
    qtbot.addWidget(card)

    card.set_selected(True)

    assert card.is_selected is True
    assert Theme.PRIMARY in card.styleSheet()


def test_clicked_signal_emitted_on_left_click(qtbot: QtBot) -> None:
    card = ModCard(_scanned(manifest=ModManifest(display_name="x")))
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.clicked, timeout=500):
        qtbot.mouseClick(card, Qt.MouseButton.LeftButton)


def test_activated_signal_emitted_on_double_click(qtbot: QtBot) -> None:
    card = ModCard(_scanned(manifest=ModManifest(display_name="x")))
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.activated, timeout=500):
        qtbot.mouseDClick(card, Qt.MouseButton.LeftButton)


def test_favorite_toggled_emits_new_state(qtbot: QtBot) -> None:
    card = ModCard(_scanned(manifest=ModManifest(display_name="x")), is_favorite=False)
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.favorite_toggled, timeout=500) as sig:
        qtbot.mouseClick(card._fav_btn, Qt.MouseButton.LeftButton)

    assert sig.args == [True]


def test_info_requested_signal_emitted(qtbot: QtBot) -> None:
    card = ModCard(_scanned(manifest=ModManifest(display_name="x")))
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.info_requested, timeout=500):
        qtbot.mouseClick(card._info_btn, Qt.MouseButton.LeftButton)


def test_renders_no_icon_fallback_when_icon_bytes_is_none(qtbot: QtBot) -> None:
    card = ModCard(_scanned(manifest=ModManifest(display_name="x")), icon_bytes=None)
    qtbot.addWidget(card)

    # The icon QLabel falls back to a "no icon" text when no bytes provided.
    icon_label = card.findChildren(type(card._name_label))
    assert any("no icon" in lbl.text() for lbl in icon_label)


def test_no_category_uses_localized_fallback(qtbot: QtBot) -> None:
    card = ModCard(_scanned(manifest=ModManifest(display_name="x", categories=())))
    qtbot.addWidget(card)

    assert card._category.text() != ""


def test_is_map_mod_shows_maps_badge(qtbot):
    mod = _scanned(manifest=ModManifest(display_name="Donbass", categories=("other",)))
    object.__setattr__(mod, "is_map", True)  # ScannedMod is frozen
    card = ModCard(
        mod,
        categories_for=lambda m: effective_categories(
            m.manifest.categories, is_map=m.is_map, override=None
        ),
    )
    qtbot.addWidget(card)
    assert card._category.text() == t(i18n_key("map")).upper()
