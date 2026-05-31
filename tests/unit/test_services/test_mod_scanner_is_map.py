import zipfile
from pathlib import Path

from easy_scsmodmanager.services.mod_scanner import _scan_archive


def _zip(path: Path, names: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for n, d in names.items():
            zf.writestr(n, d)
    return path


def test_scan_marks_map_archive(tmp_path: Path):
    p = _zip(
        tmp_path / "m.scs",
        {
            "manifest.sii": b'SiiNunit{\nmod_package: .p {\ndisplay_name: "M"\ncategory[]: "other"\n}\n}',
            "map/europe.mbd": b"x",
        },
    )
    mod, _icon, _desc = _scan_archive(p)
    assert mod.is_map is True


def test_scan_non_map_archive(tmp_path: Path):
    p = _zip(
        tmp_path / "m.scs",
        {
            "manifest.sii": b'SiiNunit{\nmod_package: .p {\ndisplay_name: "M"\ncategory[]: "sound"\n}\n}',
            "def/x.sii": b"x",
        },
    )
    mod, _icon, _desc = _scan_archive(p)
    assert mod.is_map is False
