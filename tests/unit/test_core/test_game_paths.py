from __future__ import annotations

import sys
from pathlib import Path

import pytest

from easy_scsmodmanager.core.game_paths import (
    GAME_APP_ID,
    Game,
    GameInstall,
    InstallKind,
    detect_game_installs,
    find_game_install_dir,
    game_install_from_override,
    linux_native_documents,
    proton_documents_path,
    windows_documents,
    workshop_dir_path,
)


def test_game_install_from_override_derives_dirs(tmp_path: Path) -> None:
    docs = tmp_path / "ets2docs"
    install = game_install_from_override(Game.ETS2, docs)
    assert install.kind is InstallKind.MANUAL
    assert install.documents_dir == docs
    assert install.profiles_dir == docs / "profiles"
    assert install.mod_dir == docs / "mod"
    assert install.workshop_dir is None


def test_game_install_from_override_keeps_workshop_dir(tmp_path: Path) -> None:
    install = game_install_from_override(Game.ATS, tmp_path / "d", tmp_path / "ws")
    assert install.workshop_dir == tmp_path / "ws"


def test_find_game_install_dir_locates_common_folder(tmp_path: Path) -> None:
    common = tmp_path / "lib" / "steamapps" / "common" / "Euro Truck Simulator 2"
    common.mkdir(parents=True)
    assert find_game_install_dir(Game.ETS2, [tmp_path / "lib"]) == common
    assert find_game_install_dir(Game.ATS, [tmp_path / "lib"]) is None


def test_find_game_install_dir_none_without_libraries(tmp_path: Path) -> None:
    assert find_game_install_dir(Game.ETS2, []) is None


def test_game_app_ids_match_scs_known_values() -> None:
    assert GAME_APP_ID[Game.ETS2] == 227300
    assert GAME_APP_ID[Game.ATS] == 270880


def test_linux_native_documents_builds_xdg_share_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert linux_native_documents(Game.ETS2) == (
        tmp_path / ".local" / "share" / "Euro Truck Simulator 2"
    )
    assert linux_native_documents(Game.ATS) == (
        tmp_path / ".local" / "share" / "American Truck Simulator"
    )


def test_linux_native_documents_respects_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "custom"))

    assert linux_native_documents(Game.ETS2) == (tmp_path / "custom" / "Euro Truck Simulator 2")


def test_proton_documents_path_uses_steam_compatdata_layout(tmp_path: Path) -> None:
    lib = tmp_path / "SteamLibrary"

    expected = (
        lib
        / "steamapps"
        / "compatdata"
        / "227300"
        / "pfx"
        / "drive_c"
        / "users"
        / "steamuser"
        / "Documents"
        / "Euro Truck Simulator 2"
    )
    assert proton_documents_path(lib, Game.ETS2) == expected


def test_workshop_dir_path_uses_app_id_subdir(tmp_path: Path) -> None:
    lib = tmp_path / "SteamLibrary"

    assert workshop_dir_path(lib, Game.ETS2) == (
        lib / "steamapps" / "workshop" / "content" / "227300"
    )
    assert workshop_dir_path(lib, Game.ATS) == (
        lib / "steamapps" / "workshop" / "content" / "270880"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="Posix path semantics")
def test_windows_documents_uses_userprofile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    monkeypatch.delenv("OneDrive", raising=False)

    assert windows_documents(Game.ETS2) == (
        tmp_path / "user" / "Documents" / "Euro Truck Simulator 2"
    )


def test_detect_game_installs_returns_empty_when_nothing_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert detect_game_installs(Game.ETS2, steam_libraries=[]) == []


def test_detect_game_installs_picks_up_linux_native(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    native = tmp_path / ".local" / "share" / "Euro Truck Simulator 2"
    native.mkdir(parents=True)

    installs = detect_game_installs(Game.ETS2, steam_libraries=[])

    assert len(installs) == 1
    assert installs[0] == GameInstall(
        game=Game.ETS2,
        kind=InstallKind.LINUX_NATIVE,
        documents_dir=native,
        workshop_dir=None,
    )


def test_detect_game_installs_picks_up_proton_with_workshop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    lib = tmp_path / "lib"
    docs = proton_documents_path(lib, Game.ETS2)
    docs.mkdir(parents=True)
    workshop = workshop_dir_path(lib, Game.ETS2)
    workshop.mkdir(parents=True)

    installs = detect_game_installs(Game.ETS2, steam_libraries=[lib])

    assert len(installs) == 1
    assert installs[0] == GameInstall(
        game=Game.ETS2,
        kind=InstallKind.PROTON,
        documents_dir=docs,
        workshop_dir=workshop,
    )


def test_detect_game_installs_proton_without_workshop_returns_none_workshop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    lib = tmp_path / "lib"
    docs = proton_documents_path(lib, Game.ATS)
    docs.mkdir(parents=True)

    installs = detect_game_installs(Game.ATS, steam_libraries=[lib])

    assert installs[0].workshop_dir is None


def test_detect_game_installs_finds_native_and_multiple_proton(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    native = tmp_path / "home" / ".local" / "share" / "Euro Truck Simulator 2"
    native.mkdir(parents=True)

    lib_a = tmp_path / "lib_a"
    lib_b = tmp_path / "lib_b"
    proton_documents_path(lib_a, Game.ETS2).mkdir(parents=True)
    proton_documents_path(lib_b, Game.ETS2).mkdir(parents=True)

    installs = detect_game_installs(Game.ETS2, steam_libraries=[lib_a, lib_b])

    kinds = [i.kind for i in installs]
    assert kinds.count(InstallKind.LINUX_NATIVE) == 1
    assert kinds.count(InstallKind.PROTON) == 2


def test_game_install_has_convenience_paths(tmp_path: Path) -> None:
    install = GameInstall(
        game=Game.ETS2,
        kind=InstallKind.PROTON,
        documents_dir=tmp_path / "docs",
        workshop_dir=tmp_path / "ws",
    )

    assert install.profiles_dir == tmp_path / "docs" / "profiles"
    assert install.mod_dir == tmp_path / "docs" / "mod"
