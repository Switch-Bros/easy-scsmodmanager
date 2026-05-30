"""Walks the filesystem to enumerate installed mods.

A mod payload can land on disk in any of these shapes:

* ``mod/<name>.scs``                    - ZIP-based or HashFS .scs
* ``mod/<name>.zip``                    - ZIP-based with .zip suffix
* ``mod/<name>/manifest.sii``           - already extracted directory
* ``workshop/content/<appid>/<id>/<name>.scs``     - workshop ZIP/HashFS
* ``workshop/content/<appid>/<id>/<slot>/...``     - workshop directory slot
* ``workshop/content/<appid>/<id>/versions.sii``   - selects the active slot

We dispatch every payload through :class:`ModSource` so the rest of the
pipeline (manifest parsing, icon extraction, description text) stays
format-agnostic.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from easy_scsmodmanager.core.game_paths import GameInstall
from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.scs.aem_reader import AemReader
from easy_scsmodmanager.integrations.scs.detector import ScsFormat, detect_format
from easy_scsmodmanager.integrations.scs.hashfs_reader import open_hashfs
from easy_scsmodmanager.integrations.scs.manifest_bundle import (
    ManifestBundle,
    MissingManifest,
    read_bundle,
)
from easy_scsmodmanager.integrations.scs.mod_source import DirectoryModSource
from easy_scsmodmanager.integrations.scs.raw_zip_reader import RawZipReader
from easy_scsmodmanager.integrations.scs.workshop_versions import (
    is_helper_slot_name,
    pick_active_slot,
    read_versions_sii,
)
from easy_scsmodmanager.integrations.scs.zip_reader import ZipScsReader

if TYPE_CHECKING:
    from easy_scsmodmanager.core.db.scan_cache import ScanCache

log = logging.getLogger(__name__)

MANIFEST_ENTRY = "manifest.sii"
ARCHIVE_SUFFIXES = (".scs", ".zip")


@dataclass(frozen=True)
class ScannedMod:
    path: Path
    format: ScsFormat
    manifest: ModManifest | None
    error: str | None
    description: str | None = None


# ---------------------------------------------------------------------------
# Public scanners
# ---------------------------------------------------------------------------


def scan_game_install(
    install: GameInstall,
    cache: ScanCache | None = None,
    game_version: str | None = None,
) -> list[ScannedMod]:
    """Scan the install's mod/ directory and workshop tree."""
    mods = scan_mod_directory(install.mod_dir, cache=cache)
    if install.workshop_dir is not None:
        mods.extend(
            scan_workshop_directory(install.workshop_dir, cache=cache, game_version=game_version)
        )
    return mods


def scan_mod_directory(directory: Path, cache: ScanCache | None = None) -> list[ScannedMod]:
    """Scan a flat directory for ``.scs`` / ``.zip`` files and unpacked
    mod directories (those that contain ``manifest.sii`` at the root)."""
    if not directory.is_dir():
        return []
    return [_scan_one(p, cache=cache) for p in _mod_candidates(directory)]


def scan_workshop_directory(
    directory: Path,
    cache: ScanCache | None = None,
    game_version: str | None = None,
) -> list[ScannedMod]:
    """Scan a Steam workshop content tree.

    Per ``<workshop-id>/`` we resolve the active slot via versions.sii
    so that only the version the game would actually load shows up.
    Helper slots (``150``, ``153_content``, ``downgrade_info_package``)
    are filtered out even when versions.sii is absent.
    """
    if not directory.is_dir():
        return []
    results: list[ScannedMod] = []
    for workshop_id_dir in sorted(p for p in directory.iterdir() if p.is_dir()):
        payload = _resolve_workshop_payload(workshop_id_dir, game_version)
        if payload is not None:
            results.append(_scan_one(payload, cache=cache))
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mod_candidates(directory: Path) -> list[Path]:
    """Returns the union of archive files and mod directories worth scanning."""
    entries: list[Path] = []
    for child in directory.iterdir():
        if (child.is_file() and child.suffix.lower() in ARCHIVE_SUFFIXES) or (
            child.is_dir() and (child / MANIFEST_ENTRY).is_file()
        ):
            entries.append(child)
    entries.sort(key=lambda p: p.name.lower())
    return entries


def _resolve_workshop_payload(
    workshop_id_dir: Path,
    game_version: str | None,
) -> Path | None:
    """Pick which payload inside a workshop_id/ directory to scan."""
    slots = read_versions_sii(workshop_id_dir)
    active_name = pick_active_slot(slots, game_version)

    if active_name is not None:
        target = _payload_for_slot(workshop_id_dir, active_name)
        if target is not None:
            return target

    return _fallback_workshop_payload(workshop_id_dir)


def _payload_for_slot(workshop_id_dir: Path, slot_name: str) -> Path | None:
    """Try the three layouts SCS publishes a slot under."""
    candidates = (
        workshop_id_dir / f"{slot_name}.scs",
        workshop_id_dir / f"{slot_name}.zip",
        workshop_id_dir / slot_name,
    )
    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.is_dir() and not (candidate / MANIFEST_ENTRY).is_file():
            continue
        return candidate
    return None


def _fallback_workshop_payload(workshop_id_dir: Path) -> Path | None:
    """Used when versions.sii does not list a slot we can find on disk.

    Looks for the most plausible single payload inside the workshop dir
    and skips helper-named entries that often clutter the directory.
    """
    # 1. Standard slot names that workshop tooling uses as the latest.
    for preferred in ("universal", "latest"):
        target = _payload_for_slot(workshop_id_dir, preferred)
        if target is not None:
            return target

    # 2. First non-helper archive file at the root.
    for entry in sorted(workshop_id_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_file() or entry.suffix.lower() not in ARCHIVE_SUFFIXES:
            continue
        if is_helper_slot_name(entry.stem):
            continue
        return entry

    # 3. First non-helper directory that has manifest.sii.
    for entry in sorted(workshop_id_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or is_helper_slot_name(entry.name):
            continue
        if (entry / MANIFEST_ENTRY).is_file():
            return entry

    return None


def _scan_one(path: Path, cache: ScanCache | None = None) -> ScannedMod:
    if cache is not None:
        cached = cache.get(path)
        if cached is not None:
            return cached.mod

    if path.is_dir():
        result, icon, description = _scan_directory(path)
    elif path.is_file():
        result, icon, description = _scan_archive(path)
    else:
        result = ScannedMod(
            path=path, format=ScsFormat.UNKNOWN, manifest=None, error="path does not exist"
        )
        icon, description = None, None

    _store_if_caching(cache, path, result, icon, description)
    return result


def _scan_directory(directory: Path) -> tuple[ScannedMod, bytes | None, str | None]:
    """Scan an unpacked mod directory (with manifest.sii at its root)."""
    try:
        with DirectoryModSource(directory) as source:
            bundle = read_bundle(source)
    except MissingManifest as exc:
        return _error_mod(directory, ScsFormat.UNKNOWN, str(exc)), None, None
    except Exception as exc:
        log.debug("directory mod %s failed: %s", directory, exc)
        return _error_mod(directory, ScsFormat.UNKNOWN, str(exc)), None, None
    return (
        ScannedMod(
            path=directory,
            format=ScsFormat.UNKNOWN,  # directory has no container format
            manifest=bundle.manifest,
            error=None,
            description=bundle.description_text,
        ),
        bundle.icon_bytes,
        bundle.description_text,
    )


def _scan_archive(path: Path) -> tuple[ScannedMod, bytes | None, str | None]:
    """Scan a .scs / .zip file by detecting the container format first."""
    try:
        fmt = detect_format(path)
    except OSError as exc:
        log.debug("could not read %s: %s", path, exc)
        return _error_mod(path, ScsFormat.UNKNOWN, str(exc)), None, None

    # Some workshop mods ship a .zip with no SCS magic header but a
    # standard ZIP local-file-header. Treat unknown .zip files as ZIP.
    if fmt == ScsFormat.UNKNOWN and path.suffix.lower() == ".zip" and zipfile.is_zipfile(path):
        fmt = ScsFormat.ZIP

    if fmt == ScsFormat.ZIP:
        return _scan_zip(path, fmt)
    if fmt in (ScsFormat.HASHFS_V1, ScsFormat.HASHFS_V2):
        return _scan_hashfs(path, fmt)
    if fmt == ScsFormat.AEM:
        return _scan_aem(path, fmt)
    return _error_mod(path, fmt, "Unknown SCS container format"), None, None


def _scan_aem(scs_path: Path, fmt: ScsFormat) -> tuple[ScannedMod, bytes | None, str | None]:
    # AEM! container: manifest is raw-deflate, textures/icon stored verbatim.
    try:
        with AemReader(scs_path) as reader:
            bundle = read_bundle(reader)
    except MissingManifest:
        return _error_mod(scs_path, fmt, f"missing {MANIFEST_ENTRY}"), None, None
    except Exception as exc:
        log.debug("aem read failed for %s: %s", scs_path, exc)
        return _error_mod(scs_path, fmt, str(exc)), None, None
    return _bundle_result(scs_path, fmt, bundle)


def _scan_zip(scs_path: Path, fmt: ScsFormat) -> tuple[ScannedMod, bytes | None, str | None]:
    try:
        with ZipScsReader(scs_path) as reader:
            bundle = read_bundle(reader)
    except MissingManifest:
        return _recover_fake_locked_zip(scs_path, fmt, f"missing {MANIFEST_ENTRY}")
    except Exception as exc:
        log.debug("failed to read manifest from %s: %s", scs_path, exc)
        return _recover_fake_locked_zip(scs_path, fmt, str(exc))
    return _bundle_result(scs_path, fmt, bundle)


def _recover_fake_locked_zip(
    scs_path: Path, fmt: ScsFormat, prior_error: str
) -> tuple[ScannedMod, bytes | None, str | None]:
    """Second pass for zips the stdlib reader refused.

    Some .scs carry a set encryption flag and an odd method label while the
    payload is ordinary raw-deflate. RawZipReader scans the local headers and
    inflates directly, giving us the manifest and the icon it names. If that
    also fails we fall back to scavenging a preview image.
    """
    try:
        with RawZipReader(scs_path) as raw:
            bundle = read_bundle(raw)
    except MissingManifest:
        return (
            _error_mod(scs_path, fmt, f"missing {MANIFEST_ENTRY}"),
            _scavenge_zip_icon(scs_path),
            None,
        )
    except Exception as exc:
        log.debug("raw-zip recovery failed for %s: %s", scs_path, exc)
        return _error_mod(scs_path, fmt, prior_error), _scavenge_zip_icon(scs_path), None
    return _bundle_result(scs_path, fmt, bundle)


def _bundle_result(
    scs_path: Path, fmt: ScsFormat, bundle: ManifestBundle
) -> tuple[ScannedMod, bytes | None, str | None]:
    return (
        ScannedMod(
            path=scs_path,
            format=fmt,
            manifest=bundle.manifest,
            error=None,
            description=bundle.description_text,
        ),
        bundle.icon_bytes,
        bundle.description_text,
    )


_ZIP_ICON_CANDIDATES = (
    "icon.jpg",
    "icon.png",
    "mod_icon.jpg",
    "mod_icon.png",
    "preview.jpg",
    "preview.png",
    "thumbnail.jpg",
)


def _scavenge_zip_icon(scs_path: Path) -> bytes | None:
    """Pull an icon out of a ZIP even when the manifest is unreadable.

    Map mods that encrypt manifest.sii usually leave icon.jpg / mod_icon.jpg
    in the clear next to it - just enough for an in-game thumbnail. We
    walk a fixed candidate list rather than parse manifest references.
    """
    try:
        with ZipScsReader(scs_path) as reader:
            for name in _ZIP_ICON_CANDIDATES:
                if reader.has(name):
                    try:
                        return reader.read_bytes(name)
                    except Exception:
                        continue
            # Last resort: scan the namelist for any image at the root.
            for entry in reader.list_files():
                if "/" in entry:
                    continue
                lower = entry.lower()
                if lower.endswith((".jpg", ".jpeg", ".png")):
                    try:
                        return reader.read_bytes(entry)
                    except Exception:
                        continue
    except Exception as exc:
        log.debug("zip icon scavenge failed for %s: %s", scs_path, exc)
    return None


def _scan_hashfs(scs_path: Path, fmt: ScsFormat) -> tuple[ScannedMod, bytes | None, str | None]:
    # Pure-Python HashFS reader (v1 + v2) - no external binary, works in every build.
    try:
        with open_hashfs(scs_path) as reader:
            bundle = read_bundle(reader)
    except MissingManifest:
        return _error_mod(scs_path, fmt, f"missing {MANIFEST_ENTRY}"), None, None
    except Exception as exc:
        log.debug("hashfs read failed for %s: %s", scs_path, exc)
        return _error_mod(scs_path, fmt, str(exc)), None, None
    return _bundle_result(scs_path, fmt, bundle)


def _error_mod(path: Path, fmt: ScsFormat, message: str) -> ScannedMod:
    return ScannedMod(path=path, format=fmt, manifest=None, error=message, description=None)


def _store_if_caching(
    cache: ScanCache | None,
    path: Path,
    mod: ScannedMod,
    icon_bytes: bytes | None,
    description: str | None,
) -> None:
    if cache is None:
        return
    try:
        cache.put(path, mod, icon_bytes=icon_bytes, description=description)
    except Exception as exc:
        log.debug("cache write failed for %s: %s", path, exc)
