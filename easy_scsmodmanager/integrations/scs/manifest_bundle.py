"""Pulls manifest + icon + description bytes from any :class:`ModSource`.

manifest.sii points to its icon and description files by relative path
(``icon: "tandempack.jpg"``, ``description_file: "fvinge.txt"``), but
many older modders just drop ``icon.jpg`` and ``description.txt`` at
the root without referencing them. Try both, fall through gracefully
when a mod ships neither.
"""

from __future__ import annotations

from dataclasses import dataclass

from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.scs.mod_source import ModSource
from easy_scsmodmanager.integrations.sii.parser import parse_sii

MANIFEST_ENTRY = "manifest.sii"
DEFAULT_ICON_NAMES = ("icon.jpg", "icon.png", "mod_icon.jpg", "mod_icon.png", "preview.jpg")
DEFAULT_DESCRIPTION_NAMES = ("description.txt", "mod_description.txt", "readme.txt")
MAX_DESCRIPTION_BYTES = 64 * 1024  # 64 KiB plenty for a mod readme


@dataclass(frozen=True)
class ManifestBundle:
    manifest: ModManifest
    icon_bytes: bytes | None
    description_text: str | None


class MissingManifest(ValueError):
    pass


def read_bundle(source: ModSource) -> ManifestBundle:
    """Parse manifest.sii from ``source`` and pull icon + description.

    Raises :class:`MissingManifest` when ``manifest.sii`` is not present.
    """
    if not source.has(MANIFEST_ENTRY):
        raise MissingManifest(f"missing {MANIFEST_ENTRY}")
    text = source.read_text(MANIFEST_ENTRY)
    units = parse_sii(text)
    manifest = ModManifest.from_sii_units(units)
    return ManifestBundle(
        manifest=manifest,
        icon_bytes=_read_icon(source, manifest),
        description_text=_read_description(source, manifest),
    )


def _read_icon(source: ModSource, manifest: ModManifest) -> bytes | None:
    candidates: list[str] = []
    if manifest.icon:
        candidates.append(manifest.icon)
    candidates.extend(name for name in DEFAULT_ICON_NAMES if name not in candidates)
    for name in candidates:
        if source.has(name):
            try:
                return source.read_bytes(name)
            except Exception:
                continue
    return None


def _read_description(source: ModSource, manifest: ModManifest) -> str | None:
    candidates: list[str] = []
    if manifest.description_file:
        candidates.append(manifest.description_file)
    candidates.extend(name for name in DEFAULT_DESCRIPTION_NAMES if name not in candidates)
    for name in candidates:
        if not source.has(name):
            continue
        try:
            payload = source.read_bytes(name)
        except Exception:
            continue
        # Mod authors sometimes include large changelog readmes; truncate
        # so the cache and UI do not have to deal with megabytes of text.
        if len(payload) > MAX_DESCRIPTION_BYTES:
            payload = payload[:MAX_DESCRIPTION_BYTES]
        # Encoding in the wild ranges from UTF-8 to ISO-8859-1 to CP1252.
        # errors=replace keeps the column from blowing up.
        return payload.decode("utf-8", errors="replace")
    return None
