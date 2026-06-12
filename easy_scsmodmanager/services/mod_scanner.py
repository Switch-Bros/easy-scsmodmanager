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

import hashlib
import logging
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from easy_scsmodmanager.core.game_paths import GameInstall
from easy_scsmodmanager.core.models.mod_manifest import ModManifest
from easy_scsmodmanager.integrations.scs.aem_reader import AemReader
from easy_scsmodmanager.integrations.scs.detector import ScsFormat, detect_format
from easy_scsmodmanager.integrations.scs.file_listing import list_archive_files
from easy_scsmodmanager.integrations.scs.hashfs_reader import open_hashfs
from easy_scsmodmanager.integrations.scs.manifest_bundle import (
    ManifestBundle,
    MissingManifest,
    read_bundle,
)
from easy_scsmodmanager.integrations.scs.map_detect import contains_map
from easy_scsmodmanager.integrations.scs.mod_source import DirectoryModSource
from easy_scsmodmanager.integrations.scs.raw_zip_reader import RawZipReader
from easy_scsmodmanager.integrations.scs.workshop_versions import (
    is_helper_slot_name,
    pick_active_slot,
    read_versions_sii,
)
from easy_scsmodmanager.integrations.scs.zip_reader import ZipScsReader
from easy_scsmodmanager.services.mod_identity import mod_name_for_path

if TYPE_CHECKING:
    from easy_scsmodmanager.core.db.scan_cache import ScanCache

log = logging.getLogger(__name__)

# called once per mod as it is scanned - same hook that logs "scanning <path>"
OnScan = Callable[[Path], None]

MANIFEST_ENTRY = "manifest.sii"
ARCHIVE_SUFFIXES = (".scs", ".zip")


@dataclass(frozen=True)
class ScannedMod:
    path: Path
    format: ScsFormat
    manifest: ModManifest | None
    error: str | None
    description: str | None = None
    is_map: bool = False
    # the archive's ``def/`` file paths, captured once at scan time. Powers
    # conflict detection (mods overwriting the same def file) and the physics
    # content signal. Empty for mods we could not list.
    def_files: tuple[str, ...] = ()
    # when the payload landed on this filesystem - the st_ctime, captured once
    # at scan time. This is "Date installed": creation time on Windows,
    # inode-change time on Linux, and (unlike st_mtime) never an inherited
    # upstream build timestamp. 0.0 when the path could not be stat'd, which
    # sorts such a mod to the start of the DATE order instead of raising.
    installed_at: float = 0.0

    @property
    def mod_name(self) -> str:
        """Stable identity (the ``active_mods[]`` token), derived from the path.

        Computed rather than stored: it is fully determined by the path, so a
        cache column would be redundant and could go stale if the derivation
        changes. Use this everywhere a mod must be matched across sessions
        (conflicts, combo export/import).
        """
        return mod_name_for_path(self.path)


# ---------------------------------------------------------------------------
# Public scanners
# ---------------------------------------------------------------------------


def scan_game_install(
    install: GameInstall,
    cache: ScanCache | None = None,
    game_version: str | None = None,
    on_scan: OnScan | None = None,
    owned_dlc: frozenset[str] | None = None,
) -> list[ScannedMod]:
    """Scan the install's mod/ directory and workshop tree.

    ``owned_dlc`` gates the 1.48 dlc_ normalisation (see ``_strip_dlc_prefix``);
    ``None`` means the install dir was not found, so dlc_ folders are ungated.
    """
    if owned_dlc is None:
        log.info("install dir unknown - dlc_ package folders are ungated for this scan")
    mods = scan_mod_directory(install.mod_dir, cache=cache, on_scan=on_scan, owned_dlc=owned_dlc)
    if install.workshop_dir is not None:
        mods.extend(
            scan_workshop_directory(
                install.workshop_dir,
                cache=cache,
                game_version=game_version,
                on_scan=on_scan,
                owned_dlc=owned_dlc,
            )
        )
    return mods


def scan_mod_directory(
    directory: Path,
    cache: ScanCache | None = None,
    on_scan: OnScan | None = None,
    owned_dlc: frozenset[str] | None = None,
) -> list[ScannedMod]:
    """Scan a flat directory for ``.scs`` / ``.zip`` files and unpacked
    mod directories (those that contain ``manifest.sii`` at the root)."""
    if not directory.is_dir():
        return []
    return [
        _scan_one(p, cache=cache, on_scan=on_scan, owned_dlc=owned_dlc)
        for p in _mod_candidates(directory)
    ]


def scan_workshop_directory(
    directory: Path,
    cache: ScanCache | None = None,
    game_version: str | None = None,
    on_scan: OnScan | None = None,
    owned_dlc: frozenset[str] | None = None,
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
            results.append(_scan_one(payload, cache=cache, on_scan=on_scan, owned_dlc=owned_dlc))
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


def _scan_one(
    path: Path,
    cache: ScanCache | None = None,
    on_scan: OnScan | None = None,
    owned_dlc: frozenset[str] | None = None,
) -> ScannedMod:
    # logged before any work so a hang leaves the culprit's path as the last line
    log.info("scanning %s", path)
    if on_scan is not None:
        on_scan(path)  # same point as the log line - the single progress hook
    dlc_fp = dlc_fingerprint(owned_dlc)
    if cache is not None:
        cached = cache.get(path, dlc_fp=dlc_fp)
        if cached is not None:
            return cached.mod

    if path.is_dir():
        result, icon, description = _scan_directory(path, owned_dlc)
    elif path.is_file():
        result, icon, description = _scan_archive(path, owned_dlc)
    else:
        result = ScannedMod(
            path=path, format=ScsFormat.UNKNOWN, manifest=None, error="path does not exist"
        )
        icon, description = None, None

    result = replace(result, installed_at=installed_at_for(path))
    _store_if_caching(cache, path, result, icon, description, dlc_fp)
    return result


def installed_at_for(path: Path) -> float:
    """The payload's install timestamp - its st_ctime, or 0.0 if unreadable.

    st_ctime is when the file last entered/changed on this filesystem (creation
    time on Windows), so it tracks the install/download moment rather than the
    mod's upstream build date the way st_mtime does for copied local mods.
    """
    try:
        return path.stat().st_ctime
    except OSError:
        return 0.0


def _strip_base_prefix(path: str) -> str:
    """Drop a leading ``base/`` package segment (SCS 1.48 layout).

    A mod whose content lives under a top-level ``base/`` folder mounts in-game
    as if it were at the root, so ``base/def/x`` must be seen as ``def/x``.
    Segment match, never substring: ``base_vehicle/...`` is left untouched.
    """
    p = path.lstrip("/")
    if p == "base":
        return ""  # the bare directory entry, nothing left after stripping
    return p[len("base/") :] if p.startswith("base/") else p


def _strip_dlc_prefix(path: str, owned_dlc: frozenset[str] | None) -> str:
    """Drop a leading ``dlc_<name>/`` segment when that DLC is owned.

    SCS 1.48 mods may put content under ``dlc_<name>/`` which the game mounts
    at the root, but only if the matching game DLC (``dlc_<name>.scs`` in the
    install) is present. ``owned_dlc`` is the set of owned DLC tokens; ``None``
    means the install could not be located, so we ungate (and the caller logs
    it). Segment match: ``dlcfoo/`` (no underscore) is never touched.
    """
    first, sep, rest = path.partition("/")
    if sep and first.startswith("dlc_") and (owned_dlc is None or first in owned_dlc):
        return rest
    return path


def _map_and_defs(
    files: list[str], owned_dlc: frozenset[str] | None = None
) -> tuple[bool, tuple[str, ...]]:
    """is_map flag + the ``def/`` file paths from a single listing.

    Reads the archive once and derives both signals so a 1-GB map is not
    walked twice (Performance: this listing also feeds conflict detection).
    """
    # normalise the 1.48 package layers ONCE, before both signals derive from
    # them, so a base/- or dlc_<name>/-packaged mod is seen by map, physics and
    # conflict detection. dict.fromkeys dedupes deterministically (order kept):
    # a mod carrying both def/a and base/def/a collapses to one def/a, which the
    # 1.3.5 per-file conflict tooltip would otherwise list twice.
    normalized = list(
        dict.fromkeys(
            s for f in files if (s := _strip_dlc_prefix(_strip_base_prefix(f), owned_dlc))
        )
    )
    is_map = contains_map(normalized)
    # drop directory entries ("def/", "def/vehicle/"): two mods sharing the same
    # folder structure would otherwise read as a conflict (forum #33).
    def_files = tuple(p for p in normalized if p.startswith("def/") and not p.endswith("/"))
    return is_map, def_files


def owned_dlc_tokens(install_dir: Path | None) -> frozenset[str] | None:
    """The set of owned DLC tokens (``dlc_mighty_griffin`` ...) for an install.

    These are the stems of the ``dlc_*.scs`` files in the game directory - the
    DLCs the user actually owns. ``None`` when the install dir is unknown, which
    tells the scanner to ungate dlc_ normalisation.
    """
    if install_dir is None:
        return None
    try:
        return frozenset(p.stem for p in install_dir.glob("dlc_*.scs"))
    except OSError:
        return None


def dlc_fingerprint(owned_dlc: frozenset[str] | None) -> str:
    """A short stable fingerprint of the owned-DLC set for cache validity.

    A DLC purchase changes this, so the cache treats prior entries as stale and
    re-scans (the dlc_ gating may now reveal more def files).
    """
    if owned_dlc is None:
        return "none"
    joined = ",".join(sorted(owned_dlc)).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()[:16]


def _scan_directory(
    directory: Path, owned_dlc: frozenset[str] | None = None
) -> tuple[ScannedMod, bytes | None, str | None]:
    """Scan an unpacked mod directory (with manifest.sii at its root)."""
    try:
        with DirectoryModSource(directory) as source:
            bundle = read_bundle(source)
            is_map, def_files = _map_and_defs(list_archive_files(source), owned_dlc)
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
            is_map=is_map,
            def_files=def_files,
        ),
        bundle.icon_bytes,
        bundle.description_text,
    )


def _scan_archive(
    path: Path, owned_dlc: frozenset[str] | None = None
) -> tuple[ScannedMod, bytes | None, str | None]:
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
        return _scan_zip(path, fmt, owned_dlc)
    if fmt in (ScsFormat.HASHFS_V1, ScsFormat.HASHFS_V2):
        return _scan_hashfs(path, fmt, owned_dlc)
    if fmt == ScsFormat.AEM:
        return _scan_aem(path, fmt, owned_dlc)
    return _error_mod(path, fmt, "Unknown SCS container format"), None, None


def _scan_aem(
    scs_path: Path, fmt: ScsFormat, owned_dlc: frozenset[str] | None = None
) -> tuple[ScannedMod, bytes | None, str | None]:
    # AEM! container: manifest is raw-deflate, textures/icon stored verbatim.
    try:
        with AemReader(scs_path) as reader:
            bundle = read_bundle(reader)
            return _bundle_result_with_map(scs_path, fmt, bundle, reader, owned_dlc)
    except MissingManifest:
        return _error_mod(scs_path, fmt, f"missing {MANIFEST_ENTRY}"), None, None
    except Exception as exc:
        log.debug("aem read failed for %s: %s", scs_path, exc)
        return _error_mod(scs_path, fmt, str(exc)), None, None


def _scan_zip(
    scs_path: Path, fmt: ScsFormat, owned_dlc: frozenset[str] | None = None
) -> tuple[ScannedMod, bytes | None, str | None]:
    try:
        with ZipScsReader(scs_path) as reader:
            bundle = read_bundle(reader)
            return _bundle_result_with_map(scs_path, fmt, bundle, reader, owned_dlc)
    except MissingManifest:
        return _recover_fake_locked_zip(scs_path, fmt, f"missing {MANIFEST_ENTRY}", owned_dlc)
    except Exception as exc:
        log.debug("failed to read manifest from %s: %s", scs_path, exc)
        return _recover_fake_locked_zip(scs_path, fmt, str(exc), owned_dlc)


def _recover_fake_locked_zip(
    scs_path: Path,
    fmt: ScsFormat,
    prior_error: str,
    owned_dlc: frozenset[str] | None = None,
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
            return _bundle_result_with_map(scs_path, fmt, bundle, raw, owned_dlc)
    except MissingManifest:
        return (
            _error_mod(scs_path, fmt, f"missing {MANIFEST_ENTRY}"),
            _scavenge_zip_icon(scs_path),
            None,
        )
    except Exception as exc:
        log.debug("raw-zip recovery failed for %s: %s", scs_path, exc)
        return _error_mod(scs_path, fmt, prior_error), _scavenge_zip_icon(scs_path), None


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


def _bundle_result_with_map(
    scs_path: Path,
    fmt: ScsFormat,
    bundle: ManifestBundle,
    source: object,
    owned_dlc: frozenset[str] | None = None,
) -> tuple[ScannedMod, bytes | None, str | None]:
    is_map, def_files = _map_and_defs(list_archive_files(source), owned_dlc)
    mod, icon, desc = _bundle_result(scs_path, fmt, bundle)
    return replace(mod, is_map=is_map, def_files=def_files), icon, desc


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


def _scan_hashfs(
    scs_path: Path, fmt: ScsFormat, owned_dlc: frozenset[str] | None = None
) -> tuple[ScannedMod, bytes | None, str | None]:
    # Pure-Python HashFS reader (v1 + v2) - no external binary, works in every build.
    try:
        with open_hashfs(scs_path) as reader:
            bundle = read_bundle(reader)
            return _bundle_result_with_map(scs_path, fmt, bundle, reader, owned_dlc)
    except MissingManifest:
        return _error_mod(scs_path, fmt, f"missing {MANIFEST_ENTRY}"), None, None
    except Exception as exc:
        log.debug("hashfs read failed for %s: %s", scs_path, exc)
        return _error_mod(scs_path, fmt, str(exc)), None, None


def _error_mod(path: Path, fmt: ScsFormat, message: str) -> ScannedMod:
    return ScannedMod(path=path, format=fmt, manifest=None, error=message, description=None)


def _store_if_caching(
    cache: ScanCache | None,
    path: Path,
    mod: ScannedMod,
    icon_bytes: bytes | None,
    description: str | None,
    dlc_fp: str | None = None,
) -> None:
    if cache is None:
        return
    try:
        cache.put(path, mod, icon_bytes=icon_bytes, description=description, dlc_fp=dlc_fp)
    except Exception as exc:
        log.debug("cache write failed for %s: %s", path, exc)
