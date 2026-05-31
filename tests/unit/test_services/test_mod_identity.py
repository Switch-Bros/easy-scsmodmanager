from __future__ import annotations

from pathlib import Path

from easy_scsmodmanager.integrations.scs.detector import ScsFormat
from easy_scsmodmanager.services.mod_identity import mod_name_for_path, workshop_id_for_path
from easy_scsmodmanager.services.mod_matching import active_name_for
from easy_scsmodmanager.services.mod_scanner import ScannedMod


def _mod(path: str) -> ScannedMod:
    return ScannedMod(path=Path(path), format=ScsFormat.UNKNOWN, manifest=None, error=None)


def test_mod_name_for_plain_file_is_stem() -> None:
    assert mod_name_for_path(Path("/games/ETS2/mod/cool_truck.scs")) == "cool_truck"


def test_mod_name_for_directory_is_dir_name() -> None:
    assert mod_name_for_path(Path("/games/ETS2/mod/my_unpacked_mod")) == "my_unpacked_mod"


def test_mod_name_for_workshop_is_hex_package() -> None:
    path = Path("/lib/steamapps/workshop/content/227300/123456789/universal.scs")
    assert mod_name_for_path(path) == f"mod_workshop_package.{123456789:016X}"


def test_workshop_id_detected_in_tree() -> None:
    path = Path("/lib/steamapps/workshop/content/227300/977853202/universal.scs")
    assert workshop_id_for_path(path) == "977853202"


def test_workshop_id_none_outside_tree() -> None:
    assert workshop_id_for_path(Path("/games/ETS2/mod/foo.scs")) is None


def test_scanned_mod_exposes_mod_name() -> None:
    assert _mod("/games/ETS2/mod/foo.scs").mod_name == "foo"


def test_active_name_for_matches_mod_name() -> None:
    mod = _mod("/lib/steamapps/workshop/content/227300/977853202/universal.scs")
    assert active_name_for(mod) == mod.mod_name == f"mod_workshop_package.{977853202:016X}"
