"""Read and surgically edit a multiplayer ``server_packages.sii``.

In-game export marks every mod *required*, so players need a separate profile
per server (forum #44). The fix is to flip ``optional_mod`` per mod in the
exported ``server_packages.sii``. This reads the file (only the
``server_mod_detail`` blocks - the ``server_packages_info`` block carries map
tuples our SII parser does not need) and writes back changing nothing but the
``optional_mod`` tokens, preserving CRLF and every other byte.

The sibling ``server_packages.dat`` (opaque binary map data, referenced by
``roads_data_file_name``) is never opened - not even read.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from easy_scsmodmanager.integrations.sii.parser import SiiParseError, parse_sii

log = logging.getLogger(__name__)

# one server_mod_detail block: capture its nameless id and its (flat) body
_BLOCK_RE = re.compile(r"server_mod_detail\s*:\s*(\S+)\s*\{(.*?)\}", re.S)
_OPTIONAL_RE = re.compile(r"(optional_mod\s*:\s*)(true|false)")


class ServerPackagesError(Exception):
    """The file is not a usable server_packages.sii."""


@dataclass(frozen=True)
class ServerMod:
    nameless_id: str  # physical block id, regenerated on every in-game export
    package_name: str  # logical, stable id (used for future server profiles)
    mod_name: str
    optional: bool
    workshop_mod: bool

    @property
    def display_name(self) -> str:
        return self.mod_name or self.package_name


@dataclass(frozen=True)
class ServerPackages:
    path: Path
    text: str  # original text, CRLF preserved, for the surgical write
    mods: tuple[ServerMod, ...]

    def nameless_for_package(self) -> dict[str, str]:
        """Map logical ``package_name`` -> physical ``nameless_id``.

        package_name is unique per file in practice; if a duplicate shows up we
        log it and keep the rows individually addressable by nameless_id (the
        physical write never relies on this map).
        """
        out: dict[str, str] = {}
        for mod in self.mods:
            if mod.package_name in out:
                log.warning("duplicate package_name in server_packages: %s", mod.package_name)
            out[mod.package_name] = mod.nameless_id
        return out


def read_server_packages(path: Path) -> ServerPackages:
    """Parse a server_packages.sii into its mod list. Raises on an invalid file."""
    text = path.read_bytes().decode("utf-8")
    if "server_packages_info" not in text:
        raise ServerPackagesError("missing server_packages_info")

    mods: list[ServerMod] = []
    for match in _BLOCK_RE.finditer(text):
        nameless_id, body = match.group(1), match.group(2)
        props = _parse_block(nameless_id, body)
        mods.append(
            ServerMod(
                nameless_id=nameless_id,
                package_name=str(props.get("package_name", "")),
                mod_name=str(props.get("mod_name", "")),
                optional=bool(props.get("optional_mod", False)),
                workshop_mod=bool(props.get("workshop_mod", False)),
            )
        )
    if not mods:
        raise ServerPackagesError("no server_mod_detail entries found")
    return ServerPackages(path=path, text=text, mods=tuple(mods))


def _parse_block(nameless_id: str, body: str) -> dict[str, object]:
    # reuse the real SII parser on a single detail block, sidestepping the
    # server_packages_info block (which uses map tuples the parser rejects)
    wrapped = f"SiiNunit\n{{\nserver_mod_detail : {nameless_id} {{{body}}}\n}}\n"
    try:
        return parse_sii(wrapped)[0].properties
    except (SiiParseError, IndexError) as exc:
        raise ServerPackagesError(f"could not parse mod block {nameless_id}: {exc}") from exc


def write_optional_flags(path: Path, text: str, desired_by_nameless_id: dict[str, bool]) -> None:
    """Set ``optional_mod`` per block to the desired value, changing nothing else.

    Backs up the .sii (single file, next to it) first, then writes atomically.
    The .dat is never touched.
    """
    new_text = _BLOCK_RE.sub(lambda m: _apply_block(m, desired_by_nameless_id), text)
    _backup_sii(path)
    _atomic_write(path, new_text.encode("utf-8"))


def _apply_block(match: re.Match[str], desired_by_nameless_id: dict[str, bool]) -> str:
    block, nameless_id = match.group(0), match.group(1)
    if nameless_id not in desired_by_nameless_id:
        return block
    return _set_optional(block, desired_by_nameless_id[nameless_id])


def _set_optional(block: str, value: bool) -> str:
    desired = "true" if value else "false"
    new_block, count = _OPTIONAL_RE.subn(lambda m: m.group(1) + desired, block, count=1)
    if count:
        return new_block  # line present: only the bool token changed
    if not value:
        return block  # missing line + false: default is already false, no-op

    # missing line + true: insert it, matching the block's indent and line ending
    eol = "\r\n" if "\r\n" in block else "\n"
    indent_match = re.search(r"(?:\r?\n)([ \t]+)\S", block)
    indent = indent_match.group(1) if indent_match else " "
    new_line = f"{indent}optional_mod: {desired}"
    # preferred anchor: right before full_name; fallback: before the closing brace
    full_name = re.search(r"[ \t]*full_name\s*:", block)
    pos = full_name.start() if full_name else block.rfind("}")
    return block[:pos] + new_line + eol + block[pos:]


def _backup_sii(path: Path) -> None:
    # single-file backup beside the .sii; never the opaque .dat
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup)
    log.info("backed up %s to %s", path.name, backup.name)


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
