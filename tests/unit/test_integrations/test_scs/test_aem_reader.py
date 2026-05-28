from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from easy_scsmodmanager.integrations.scs.aem_reader import AemReader


def _raw_deflate(data: bytes) -> bytes:
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(data) + co.flush()


def _make_aem(path: Path, entries: dict[str, bytes], pad: int = 8) -> Path:
    # mimic the AEM container: [AEM!][zero pad][uint32 name_len][name][content]
    # with .sii stored as raw-deflate and everything else stored verbatim.
    buf = bytearray()
    for name, content in entries.items():
        buf += b"AEM!"
        buf += b"\x00" * pad
        nb = name.encode("ascii")
        buf += struct.pack("<I", len(nb))
        buf += nb
        buf += _raw_deflate(content) if name.lower().endswith(".sii") else content
    path.write_bytes(bytes(buf))
    return path


def test_reads_raw_deflate_manifest(tmp_path: Path) -> None:
    text = b'SiiNunit\n{\nmod_package : .p {\ndisplay_name: "AEM Map"\n}\n}\n'
    scs = _make_aem(
        tmp_path / "aem.scs",
        {"material/x.dds": b"\x00\x01\x02", "manifest.sii": text},
    )

    with AemReader(scs) as reader:
        assert reader.read_bytes("manifest.sii") == text


def test_read_text_decodes_manifest(tmp_path: Path) -> None:
    scs = _make_aem(tmp_path / "aem.scs", {"manifest.sii": b"SiiNunit\n{}\n"})

    with AemReader(scs) as reader:
        assert reader.read_text("manifest.sii") == "SiiNunit\n{}\n"


def test_reads_stored_icon_verbatim(tmp_path: Path) -> None:
    jpg = b"\xff\xd8\xff\xe0" + b"jpegbody" * 3 + b"\xff\xd9"
    scs = _make_aem(
        tmp_path / "aem.scs",
        {"manifest.sii": b"SiiNunit\n{}\n", "icon.jpg": jpg},
    )

    with AemReader(scs) as reader:
        assert reader.read_bytes("icon.jpg") == jpg


def test_has_finds_entry_and_misses_unknown(tmp_path: Path) -> None:
    scs = _make_aem(tmp_path / "aem.scs", {"manifest.sii": b"SiiNunit\n{}\n"})

    with AemReader(scs) as reader:
        assert reader.has("manifest.sii") is True
        assert reader.has("nope.sii") is False


def test_read_bytes_raises_keyerror_for_missing(tmp_path: Path) -> None:
    scs = _make_aem(tmp_path / "aem.scs", {"manifest.sii": b"x"})

    with AemReader(scs) as reader, pytest.raises(KeyError):
        reader.read_bytes("does-not-exist")


def test_stray_aem_inside_texture_does_not_split_entry(tmp_path: Path) -> None:
    # a 4-byte AEM! can occur by chance inside a big binary texture; it must
    # not be treated as a boundary (no zero pad + plausible name + ascii after).
    texture = b"\x01\x02AEM!\x99\x88\x77garbagebytes\xab\xcd"
    scs = _make_aem(
        tmp_path / "aem.scs",
        {"material/x.dds": texture, "manifest.sii": b'SiiNunit\n{display_name: "Ok"}\n'},
    )

    with AemReader(scs) as reader:
        assert reader.read_bytes("material/x.dds") == texture
        assert "display_name" in reader.read_text("manifest.sii")


def test_tolerates_variable_zero_padding(tmp_path: Path) -> None:
    # the real container leaves a variable run of zero bytes after AEM!;
    # the index must skip it however long it is.
    scs = _make_aem(tmp_path / "aem.scs", {"manifest.sii": b"SiiNunit\n{ok}\n"}, pad=24)

    with AemReader(scs) as reader:
        assert reader.read_text("manifest.sii") == "SiiNunit\n{ok}\n"
