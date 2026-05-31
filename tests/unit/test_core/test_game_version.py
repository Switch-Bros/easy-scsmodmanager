from __future__ import annotations

from pathlib import Path

from easy_scsmodmanager.core.game_version import read_game_version

_REAL_LINE = "00:00:00.061 : [ufs] Loaded pack set version 1.59.1.3 created at 1778607514\n"


def test_reads_version_from_real_line(tmp_path: Path) -> None:
    (tmp_path / "game.log.txt").write_text(
        "00:00:00.000 : [sys] start\n" + _REAL_LINE + "more\n", encoding="utf-8"
    )
    assert read_game_version(tmp_path) == "1.59.1.3"


def test_missing_log_returns_none(tmp_path: Path) -> None:
    assert read_game_version(tmp_path) is None


def test_log_without_version_line_returns_none(tmp_path: Path) -> None:
    (tmp_path / "game.log.txt").write_text("nothing useful here\n", encoding="utf-8")
    assert read_game_version(tmp_path) is None
