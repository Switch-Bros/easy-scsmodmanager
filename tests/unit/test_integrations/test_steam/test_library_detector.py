from __future__ import annotations

import sys
from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.steam.library_detector import (
    discover_steam_libraries,
    find_steam_installs,
    read_library_paths_from_vdf,
    steam_install_candidates,
)


def _write_vdf(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_read_library_paths_from_vdf_extracts_multiple_paths(tmp_path: Path) -> None:
    vdf = _write_vdf(
        tmp_path / "libraryfolders.vdf",
        """
"libraryfolders"
{
	"0"
	{
		"path"		"/home/user/.steam/steam"
		"label"		""
	}
	"1"
	{
		"path"		"/mnt/games/SteamLibrary"
		"label"		"games"
	}
}
""".strip(),
    )

    paths = read_library_paths_from_vdf(vdf)

    assert paths == [Path("/home/user/.steam/steam"), Path("/mnt/games/SteamLibrary")]


def test_read_library_paths_from_vdf_handles_single_library(tmp_path: Path) -> None:
    vdf = _write_vdf(
        tmp_path / "libraryfolders.vdf",
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t"/only/one"\n\t}\n}\n',
    )

    paths = read_library_paths_from_vdf(vdf)

    assert paths == [Path("/only/one")]


def test_read_library_paths_from_vdf_returns_empty_for_no_libraries(tmp_path: Path) -> None:
    vdf = _write_vdf(tmp_path / "libraryfolders.vdf", '"libraryfolders"\n{\n}\n')

    paths = read_library_paths_from_vdf(vdf)

    assert paths == []


def test_read_library_paths_from_vdf_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_library_paths_from_vdf(tmp_path / "nope.vdf")


@pytest.mark.skipif(sys.platform == "win32", reason="Linux-specific candidates")
def test_steam_install_candidates_linux_includes_native_steam_dirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    candidates = steam_install_candidates()

    assert tmp_path / ".steam" / "steam" in candidates
    assert tmp_path / ".local" / "share" / "Steam" in candidates
    assert (
        tmp_path / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam"
        in candidates
    )


@pytest.mark.skipif(sys.platform == "win32", reason="Linux env handling")
def test_steam_install_candidates_respects_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "custom-xdg"))

    candidates = steam_install_candidates()

    assert tmp_path / "custom-xdg" / "Steam" in candidates


def test_find_steam_installs_filters_to_existing_paths_with_vdf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real = tmp_path / "real_steam"
    _write_vdf(real / "steamapps" / "libraryfolders.vdf", '"libraryfolders" { }')
    fake = tmp_path / "no_steam_here"

    monkeypatch.setattr(
        "easy_scsmodmanager.integrations.steam.library_detector.steam_install_candidates",
        lambda: [real, fake],
    )

    installs = find_steam_installs()

    assert installs == [real]


def test_discover_steam_libraries_combines_all_installs_and_dedupes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install_a = tmp_path / "a"
    install_b = tmp_path / "b"

    _write_vdf(
        install_a / "steamapps" / "libraryfolders.vdf",
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t"/lib/shared"\n\t}\n\t"1"\n\t{\n\t\t"path"\t"/lib/only-a"\n\t}\n}\n',
    )
    _write_vdf(
        install_b / "steamapps" / "libraryfolders.vdf",
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t"/lib/shared"\n\t}\n\t"1"\n\t{\n\t\t"path"\t"/lib/only-b"\n\t}\n}\n',
    )

    monkeypatch.setattr(
        "easy_scsmodmanager.integrations.steam.library_detector.steam_install_candidates",
        lambda: [install_a, install_b],
    )

    libs = discover_steam_libraries()

    assert sorted(libs) == sorted(
        [Path("/lib/shared"), Path("/lib/only-a"), Path("/lib/only-b")]
    )
