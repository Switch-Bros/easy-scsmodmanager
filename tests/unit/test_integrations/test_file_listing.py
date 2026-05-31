from pathlib import Path

from easy_scsmodmanager.integrations.scs.file_listing import list_archive_files
from easy_scsmodmanager.integrations.scs.mod_source import DirectoryModSource


def test_lists_directory_source(tmp_path: Path):
    (tmp_path / "map").mkdir()
    (tmp_path / "map" / "europe.mbd").write_bytes(b"x")
    (tmp_path / "manifest.sii").write_bytes(b"x")
    src = DirectoryModSource(tmp_path)
    files = set(list_archive_files(src))
    assert "manifest.sii" in files
    assert "map/europe.mbd" in files


class _FakeListFiles:
    def list_files(self, prefix: str = "") -> list[str]:
        return ["manifest.sii", "map/x.mbd"]


class _FakeIterFiles:
    def iter_files(self) -> list[str]:
        return ["/manifest.sii", "/map/x.mbd"]


def test_uses_list_files_when_present():
    assert "map/x.mbd" in list_archive_files(_FakeListFiles())


def test_uses_iter_files_when_present():
    assert "/map/x.mbd" in list_archive_files(_FakeIterFiles())
