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
    assert tmp_path / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" in candidates


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

    assert sorted(libs) == sorted([Path("/lib/shared"), Path("/lib/only-a"), Path("/lib/only-b")])


def test_registry_steam_path_prefers_hkcu_steampath(monkeypatch: pytest.MonkeyPatch) -> None:
    from easy_scsmodmanager.integrations.steam import library_detector as ld

    def fake_read(hive: str, subkey: str, name: str, *, expand: bool = False) -> str | None:
        if hive == "HKCU" and name == "SteamPath":
            return r"D:\Steam"
        return None

    monkeypatch.setattr(ld, "read_string", fake_read)

    assert ld._registry_steam_path() == Path(r"D:\Steam")


def test_registry_steam_path_falls_back_to_hklm_installpath(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from easy_scsmodmanager.integrations.steam import library_detector as ld

    def fake_read(hive: str, subkey: str, name: str, *, expand: bool = False) -> str | None:
        if hive == "HKLM" and name == "InstallPath":
            return r"C:\Program Files (x86)\Steam"
        return None

    monkeypatch.setattr(ld, "read_string", fake_read)

    assert ld._registry_steam_path() == Path(r"C:\Program Files (x86)\Steam")


def test_registry_steam_path_keeps_forward_slashes(monkeypatch: pytest.MonkeyPatch) -> None:
    from easy_scsmodmanager.integrations.steam import library_detector as ld

    monkeypatch.setattr(ld, "read_string", lambda *a, **k: "D:/Steam")

    assert ld._registry_steam_path() == Path("D:/Steam")


def test_registry_steam_path_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    from easy_scsmodmanager.integrations.steam import library_detector as ld

    monkeypatch.setattr(ld, "read_string", lambda *a, **k: None)

    assert ld._registry_steam_path() is None


def test_windows_candidates_put_registry_first(monkeypatch: pytest.MonkeyPatch) -> None:
    from easy_scsmodmanager.integrations.steam import library_detector as ld

    monkeypatch.setattr(ld, "_registry_steam_path", lambda: Path(r"R:\SteamFromRegistry"))
    monkeypatch.setenv("ProgramFiles(x86)", r"C:\Program Files (x86)")
    monkeypatch.delenv("ProgramFiles", raising=False)
    monkeypatch.delenv("ProgramW6432", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)

    cands = ld._windows_candidates()

    assert cands[0] == Path(r"R:\SteamFromRegistry")
    assert Path(r"C:\Program Files (x86)") / "Steam" in cands


def test_windows_candidates_skip_registry_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    from easy_scsmodmanager.integrations.steam import library_detector as ld

    monkeypatch.setattr(ld, "_registry_steam_path", lambda: None)
    monkeypatch.setenv("ProgramFiles(x86)", r"C:\Program Files (x86)")
    monkeypatch.delenv("ProgramFiles", raising=False)
    monkeypatch.delenv("ProgramW6432", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)

    cands = ld._windows_candidates()

    assert cands == [Path(r"C:\Program Files (x86)") / "Steam"]


def test_discover_logs_no_install(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    from easy_scsmodmanager.integrations.steam import library_detector as ld

    monkeypatch.setattr(ld, "find_steam_installs", lambda: [])
    with caplog.at_level(logging.INFO):
        ld.discover_steam_libraries()

    assert any("no Steam install found" in r.message for r in caplog.records)


def test_discover_logs_installs_and_libraries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    from easy_scsmodmanager.integrations.steam import library_detector as ld

    install = tmp_path / "steam"
    _write_vdf(
        install / "steamapps" / "libraryfolders.vdf",
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t"/lib/one"\n\t}\n}\n',
    )
    monkeypatch.setattr(ld, "find_steam_installs", lambda: [install])
    with caplog.at_level(logging.INFO):
        ld.discover_steam_libraries()

    joined = " ".join(r.message for r in caplog.records)
    assert "Steam installs:" in joined
    assert "Steam libraries:" in joined
