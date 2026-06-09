from __future__ import annotations

import json
from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.gdeflate import GDeflateError, decompress

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "scs_textures"
_INFO = json.loads((_FIXTURES / "info.json").read_text())


@pytest.mark.parametrize("tex", _INFO, ids=[f"tex{t['n']}" for t in _INFO])
def test_decompress_matches_reference(tex: dict) -> None:
    # reference .raw was produced by the original C# GisDeflate, independent of us
    payload = (_FIXTURES / f"tex{tex['n']}.gdeflate").read_bytes()
    want = (_FIXTURES / f"tex{tex['n']}.raw").read_bytes()
    got = decompress(payload)
    assert got == want
    assert len(got) == tex["uncompressed"]


def test_rejects_non_gdeflate() -> None:
    with pytest.raises(GDeflateError):
        decompress(b"\x00\x01not a gdeflate stream")


def test_rejects_truncated() -> None:
    with pytest.raises(GDeflateError):
        decompress(b"\x04\xfb")
