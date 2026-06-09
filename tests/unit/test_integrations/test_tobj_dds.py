from __future__ import annotations

import json
from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.tobj_dds import TobjMeta, reconstruct_dds

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "scs_textures"
_INFO = json.loads((_FIXTURES / "info.json").read_text())


@pytest.mark.parametrize("tex", _INFO, ids=[f"tex{t['n']}" for t in _INFO])
def test_reconstruct_matches_trucklib_dds(tex: dict) -> None:
    # reference .dds was produced by the original TruckLib.HashFs, independent of us
    tobj = (_FIXTURES / f"tex{tex['n']}.tobj12").read_bytes()
    payload = (_FIXTURES / f"tex{tex['n']}.gdeflate").read_bytes()
    want = (_FIXTURES / f"tex{tex['n']}.dds").read_bytes()
    got = reconstruct_dds(tobj, payload, compressed=tex["compressed"])
    assert got == want


def test_dds_has_dx10_header() -> None:
    tobj = (_FIXTURES / "tex0.tobj12").read_bytes()
    payload = (_FIXTURES / "tex0.gdeflate").read_bytes()
    dds = reconstruct_dds(tobj, payload, compressed=True)
    assert dds[:4] == b"DDS "
    assert dds[84:88] == b"DX10"  # FourCC in the pixel format


def test_tobj_meta_parses_dimensions() -> None:
    # width/height stored as value-1; a 128x128 texture reads back as 128
    meta = TobjMeta(b"\x7f\x00\x7f\x00\x87\x04\x80\x09\x27\x01\x00\x00")
    assert meta.width == 128
    assert meta.height == 128
    assert meta.mip == 8


def test_rejects_short_metadata() -> None:
    with pytest.raises(ValueError, match="12 bytes"):
        TobjMeta(b"\x00\x00\x00")
