"""Controller logic: payload building, installed map via matcher, apply."""

import pytest

pytest.importorskip("pytestqt")

from pathlib import Path  # noqa: E402

from easy_scsmodmanager.core.game_paths import Game  # noqa: E402
from easy_scsmodmanager.services.mod_share import (  # noqa: E402
    ShareEntry,
    ShareList,
    parse,
    serialize,
)
from easy_scsmodmanager.services.profile_reader import ActiveMod, read_profile  # noqa: E402
from easy_scsmodmanager.ui.controllers import mod_share_controller  # noqa: E402
from easy_scsmodmanager.ui.controllers.mod_share_controller import (  # noqa: E402
    ModShareController,
)

PROFILE_TEXT = (
    "SiiNunit\n"
    "{\n"
    "user_profile : _nameless.1ad.dead {\n"
    ' profile_name: "Receiver"\n'
    " active_mods: 1\n"
    ' active_mods[0]: "old_mod|Old"\n'
    "}\n"
    "}\n"
)


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep profile backups (save_active_mods) out of the real user data dir."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))


class _Manifest:
    def __init__(self, version: str) -> None:
        self.package_version = version
        self.display_name = ""


class _Scanned:
    def __init__(self, version: str = "") -> None:
        self.manifest = _Manifest(version) if version else None


class _Matcher:
    """Knows exactly one installed mod: ``have`` with version 1.0."""

    def lookup(self, active: ActiveMod):
        return _Scanned("1.0") if active.name == "have" else None


def _controller(
    tmp_path: Path,
) -> tuple[ModShareController, Path, list[str], list[tuple[str, str]]]:
    profile_path = tmp_path / "profile.sii"
    profile_path.write_text(PROFILE_TEXT, encoding="utf-8")
    statuses: list[str] = []
    pins: list[tuple[str, str]] = []
    controller = ModShareController(
        parent=None,
        current_game=lambda: Game.ETS2,
        current_profile=lambda: read_profile(profile_path),
        profile_sii_path=lambda: profile_path,
        matcher=lambda: _Matcher(),
        local_versions=lambda: {"old_mod": "0.9"},
        group_token_for=lambda mod: "trucks" if mod.name == "have" else "",
        apply_group_pin=lambda mod, token: pins.append((mod.name, token)),
        show_status=statuses.append,
        request_rescan=lambda: False,
        reload_profile=lambda: None,
    )
    return controller, profile_path, statuses, pins


def test_build_share_carries_groups_and_versions(tmp_path: Path, qtbot) -> None:
    controller, _, _, _ = _controller(tmp_path)
    share = controller._build_share()
    assert share is not None
    assert share.game is Game.ETS2
    assert share.profile_name == "Receiver"
    assert share.entries[0].name == "old_mod"
    assert share.entries[0].package_version == "0.9"


def test_installed_map_uses_matcher(tmp_path: Path, qtbot) -> None:
    controller, _, _, _ = _controller(tmp_path)
    share = ShareList(
        game=Game.ETS2,
        profile_name="Sender",
        entries=(ShareEntry(name="have"), ShareEntry(name="missing")),
    )
    installed = controller._installed_map(share)
    assert installed == {"have": "1.0", "missing": None}


def test_apply_writes_profile_and_pins_groups(tmp_path: Path, qtbot) -> None:
    controller, profile_path, statuses, pins = _controller(tmp_path)
    share = ShareList(
        game=Game.ETS2,
        profile_name="Sender",
        entries=(
            ShareEntry(name="have", display_name="Have", group="trucks"),
            ShareEntry(name="missing", display_name="Missing"),
        ),
    )
    controller._apply(share, include_missing=True)
    written = read_profile(profile_path)
    assert [m.name for m in written.active_mods] == ["have", "missing"]
    assert ("have", "trucks") in pins
    assert statuses


def test_apply_can_skip_missing(tmp_path: Path, qtbot) -> None:
    controller, profile_path, _, _ = _controller(tmp_path)
    share = ShareList(
        game=Game.ETS2,
        profile_name="Sender",
        entries=(ShareEntry(name="have"), ShareEntry(name="missing")),
    )
    controller._apply(share, include_missing=False)
    written = read_profile(profile_path)
    assert [m.name for m in written.active_mods] == ["have"]


def test_share_roundtrip_through_build(tmp_path: Path, qtbot) -> None:
    controller, _, _, _ = _controller(tmp_path)
    share = controller._build_share()
    assert share is not None
    assert parse(serialize(share)) == share


def test_stale_fetch_result_is_ignored(tmp_path: Path, qtbot) -> None:
    controller, _, _, _ = _controller(tmp_path)
    controller._open_import("code")

    class _StaleThread:
        code = "OLDOLD"

    controller._fetch_thread = None  # no current lookup anymore
    controller._on_payload({"format": "x"}, source_thread=_StaleThread())
    # nothing presented: dialog still has no share
    assert controller._import_dialog.current_share() is None


def test_stale_fetch_failure_is_ignored(tmp_path: Path, qtbot) -> None:
    controller, _, _, _ = _controller(tmp_path)
    controller._open_import("code")

    class _StaleThread:
        code = "OLDOLD"

    controller._fetch_thread = None
    controller._on_lookup_failed("connection", source_thread=_StaleThread())
    assert controller._import_dialog._status_label.text() == ""


def test_apply_failure_keeps_dialog_open_and_reports(tmp_path: Path, qtbot) -> None:
    controller, profile_path, statuses, _ = _controller(tmp_path)
    controller._open_import("code")
    # no active_mods line -> save_active_mods raises ValueError
    profile_path.write_text("SiiNunit\n{\n}\n", encoding="utf-8")
    share = ShareList(game=Game.ETS2, profile_name="S", entries=(ShareEntry(name="have"),))
    assert controller._apply(share, include_missing=True) is False
    assert controller._import_dialog._status_label.text() != ""
    assert statuses == []  # no success status


def test_apply_skips_unknown_group_id(tmp_path: Path, qtbot) -> None:
    controller, profile_path, _, pins = _controller(tmp_path)
    share = ShareList(
        game=Game.ETS2,
        profile_name="Sender",
        entries=(ShareEntry(name="have", group="hovercrafts"),),
    )
    assert controller._apply(share, include_missing=True) is True
    assert pins == []  # foreign/newer group id is ignored, never pinned
    written = read_profile(profile_path)
    assert [m.name for m in written.active_mods] == ["have"]


def test_shutdown_with_no_threads_is_safe(tmp_path: Path, qtbot) -> None:
    controller, _, _, _ = _controller(tmp_path)
    controller.shutdown(100)


def test_load_share_file_invalidates_pending_lookup(tmp_path: Path, qtbot) -> None:
    """A file pick must drop an in-flight code lookup or its late result
    would replace the file's preview and Apply would write the wrong list."""
    controller, _, _, _ = _controller(tmp_path)
    controller._open_import("file")
    share = controller._build_share()
    assert share is not None
    share_path = tmp_path / "list.modshare.json"
    share_path.write_text(serialize(share), encoding="utf-8")

    class _InFlight:
        code = "OLDOLD"

    controller._fetch_thread = _InFlight()
    controller._load_share_file(str(share_path))
    assert controller._fetch_thread is None
    assert controller._import_dialog.current_share() == share
    # the superseded lookup resolving now must not touch the preview
    controller._on_payload({"format": "x"}, source_thread=_InFlight())
    assert controller._import_dialog.current_share() == share


def test_load_foreign_profile_invalidates_pending_lookup(tmp_path: Path, qtbot) -> None:
    controller, profile_path, _, _ = _controller(tmp_path)
    controller._open_import("profile")

    class _InFlight:
        code = "OLDOLD"

    controller._fetch_thread = _InFlight()
    controller._load_foreign_profile(str(profile_path))
    assert controller._fetch_thread is None
    assert controller._import_dialog.current_share() is not None


def test_export_file_write_failure_reports_status(
    tmp_path: Path, qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _, statuses, _ = _controller(tmp_path)
    target = tmp_path / "out.modshare.json"
    monkeypatch.setattr(
        mod_share_controller.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )

    def _boom(self: Path, *args, **kwargs) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _boom)
    controller.export_file()
    assert len(statuses) == 1
    assert "disk full" in statuses[0]


def test_reopen_import_resets_stale_share(tmp_path: Path, qtbot) -> None:
    controller, _, _, _ = _controller(tmp_path)
    controller._open_import("code")
    share = ShareList(game=Game.ETS2, profile_name="Sender", entries=(ShareEntry(name="have"),))
    controller._present(share)
    assert controller._import_dialog.current_share() is not None
    controller._import_dialog.close()
    controller._open_import("code")
    assert controller._import_dialog.current_share() is None


def test_outdated_warning_fires_once_per_share(
    tmp_path: Path, qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _, _, _ = _controller(tmp_path)
    controller._open_import("code")
    warnings: list[tuple] = []
    monkeypatch.setattr(
        mod_share_controller.QMessageBox,
        "information",
        staticmethod(lambda *a, **k: warnings.append(a)),
    )
    # matcher reports "have" installed at 1.0 -> share at 2.0 is outdated locally
    share = ShareList(
        game=Game.ETS2,
        profile_name="Sender",
        entries=(ShareEntry(name="have", package_version="2.0"),),
    )
    controller._present(share)
    assert len(warnings) == 1
    controller._present(share)  # "Check again" re-presents the same object
    assert len(warnings) == 1
    other = ShareList(
        game=Game.ETS2,
        profile_name="Other",
        entries=(ShareEntry(name="have", package_version="3.0"),),
    )
    controller._present(other)
    assert len(warnings) == 2


def test_shutdown_waits_on_open_create_dialog(tmp_path: Path, qtbot) -> None:
    controller, _, _, _ = _controller(tmp_path)

    class _Dialog:
        def __init__(self) -> None:
            self.waited: list[int] = []

        def shutdown(self, msecs: int) -> None:
            self.waited.append(msecs)

    dialog = _Dialog()
    controller._create_dialog = dialog
    controller.shutdown(100)
    assert dialog.waited == [100]
