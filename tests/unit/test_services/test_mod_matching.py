from __future__ import annotations

from pathlib import Path

from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_matching import ActiveModMatcher
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.services.profile_reader import ActiveMod


def _scanned(path: Path, display_name: str | None = None) -> ScannedMod:
    manifest = ModManifest(display_name=display_name) if display_name else None
    return ScannedMod(path=path, format=ScsFormat.ZIP, manifest=manifest, error=None)


def test_lookup_matches_by_file_stem() -> None:
    mods = [_scanned(Path("/mod/foo.scs"), "Foo")]
    matcher = ActiveModMatcher(mods)

    assert matcher.lookup(ActiveMod(name="foo", display_name="Foo")) is mods[0]


def test_lookup_matches_by_parent_directory_for_unpacked_slot() -> None:
    # Workshop directory mod: /workshop/.../999/universal/manifest.sii
    mods = [
        _scanned(
            Path("/games/SteamLib/steamapps/workshop/content/227300/999/universal"),
            "Demo Mod",
        )
    ]
    matcher = ActiveModMatcher(mods)

    assert matcher.lookup(ActiveMod(name="universal", display_name="Demo Mod")) is mods[0]


def test_lookup_matches_workshop_id_token() -> None:
    # ETS2 active_mods sometimes contain mod_workshop_package.<hex16>.
    # Hex 0x000000000000003A7 = decimal 935
    mods = [
        _scanned(
            Path("/games/SteamLib/steamapps/workshop/content/227300/935/universal.scs"),
            "Workshop Mod",
        )
    ]
    matcher = ActiveModMatcher(mods)

    active = ActiveMod(name="mod_workshop_package.00000000000003A7", display_name="Workshop Mod")
    assert matcher.lookup(active) is mods[0]


def test_lookup_falls_back_to_display_name() -> None:
    mods = [_scanned(Path("/mod/abc123.scs"), "My Cool Truck")]
    matcher = ActiveModMatcher(mods)

    assert matcher.lookup(ActiveMod(name="something_else", display_name="My Cool Truck")) is mods[0]


def test_lookup_returns_none_when_no_strategy_matches() -> None:
    mods = [_scanned(Path("/mod/foo.scs"), "Foo")]
    matcher = ActiveModMatcher(mods)

    assert matcher.lookup(ActiveMod(name="bar", display_name="Bar")) is None


def test_installed_active_names_returns_matchable_names() -> None:
    mods = [
        _scanned(Path("/mod/alpha.scs"), "Alpha"),
        _scanned(
            Path("/games/SteamLib/steamapps/workshop/content/227300/42/universal"),
            "Workshop",
        ),
    ]
    matcher = ActiveModMatcher(mods)

    actives = [
        ActiveMod(name="alpha", display_name="Alpha"),
        ActiveMod(name="universal", display_name="Workshop"),
        ActiveMod(name="orphan", display_name="Orphan"),
    ]

    assert matcher.installed_active_names(actives) == {"alpha", "universal"}
