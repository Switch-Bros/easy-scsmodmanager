"""Stable mod identity derived purely from a path.

The internal mod name is the token ETS2 writes into ``active_mods[]``. It is
the only identity that survives across sessions (the display name changes,
the icon changes). It is fully determined by the path on disk, so it lives
here as pure functions with no dependency on ScannedMod - which keeps both
the scanner and the matcher able to import it without an import cycle.
"""

from __future__ import annotations

from pathlib import Path


def workshop_id_for_path(path: Path) -> str | None:
    """Detect the workshop published-file-id from a scanned mod path.

    Recognises ``.../workshop/content/<appid>/<workshop_id>/...``.
    Returns the numeric workshop id as a string, or None if the path
    does not live inside a workshop tree.
    """
    parts = path.parts
    if "workshop" not in parts or "content" not in parts:
        return None
    try:
        content_idx = parts.index("content")
    except ValueError:
        return None
    if content_idx + 2 >= len(parts):
        return None
    workshop_id = parts[content_idx + 2]
    if workshop_id.isdigit():
        return workshop_id
    return None


def mod_name_for_path(path: Path) -> str:
    """The name this mod takes in ``active_mods[]`` - the stable identity.

    Workshop mods become ``mod_workshop_package.<16-char upper hex>`` of the
    published-file-id; everything else uses the file/directory stem.
    """
    ws_id = workshop_id_for_path(path)
    if ws_id is not None:
        return f"mod_workshop_package.{int(ws_id):016X}"
    return path.stem


WORKSHOP_NAME_PREFIX = "mod_workshop_package."
_WORKSHOP_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id={id}"


def workshop_id_from_active_name(name: str) -> str | None:
    """``mod_workshop_package.000000003A4B7C12`` -> ``"978025490"``.

    ETS2 stores workshop ids in active_mods[] as a 16-char zero-padded
    hex tail after the fixed prefix. Returns the decimal id, or None if
    the name does not match that shape.
    """
    if not name.startswith(WORKSHOP_NAME_PREFIX):
        return None
    try:
        return str(int(name[len(WORKSHOP_NAME_PREFIX) :], 16))
    except ValueError:
        return None


def workshop_url_from_active_name(name: str) -> str | None:
    """Steam Workshop page for a workshop active-mod name, else None."""
    ws_id = workshop_id_from_active_name(name)
    if ws_id is None:
        return None
    return _WORKSHOP_URL.format(id=ws_id)
