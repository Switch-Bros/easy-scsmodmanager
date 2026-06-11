"""Drives the Share menu: create code, redeem, file export/import, profile pull.

Mirrors MapComboController: explicit callables instead of a MainWindow import,
so the whole flow is testable with plain fakes. Owns the two dialogs, the
network threads and the apply step (write + group pins + reload).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from easy_scsmodmanager.core.game_paths import Game
from easy_scsmodmanager.core.load_order import GROUPS
from easy_scsmodmanager.services.mod_share import (
    FILE_SUFFIX,
    ModShareError,
    ModShareVersionError,
    ShareDiff,
    ShareList,
    build_from_profile,
    diff,
    from_payload,
    parse,
    serialize,
    to_active_mods,
    to_payload,
)
from easy_scsmodmanager.services.profile_reader import ActiveMod, Profile, read_profile
from easy_scsmodmanager.services.profile_writer import save_active_mods
from easy_scsmodmanager.ui.dialogs.share_create_dialog import ShareCreateDialog
from easy_scsmodmanager.ui.dialogs.share_import_dialog import ShareImportDialog
from easy_scsmodmanager.ui.threads.share_thread import ShareFetchThread
from easy_scsmodmanager.utils.i18n import t

log = logging.getLogger(__name__)

# Share entries carry load-order GROUP IDs (the same values the group pins /
# category_overrides store, e.g. "trucks", "maps"). Ids from foreign or newer
# share lists may be unknown here and must be skipped, never pinned.
_KNOWN_GROUP_IDS = frozenset(g.id for g in GROUPS)


class _MatcherLike(Protocol):
    def lookup(self, active: ActiveMod) -> object | None: ...


class ModShareController:
    def __init__(
        self,
        *,
        parent: QWidget | None,
        current_game: Callable[[], Game],
        current_profile: Callable[[], Profile | None],
        profile_sii_path: Callable[[], Path | None],
        matcher: Callable[[], _MatcherLike | None],
        local_versions: Callable[[], dict[str, str]],
        group_token_for: Callable[[ActiveMod], str],
        # receives a group id already validated against GROUPS, so
        # MainWindow._apply_group_pin can be wired in directly
        apply_group_pin: Callable[[ActiveMod, str], None],
        show_status: Callable[[str], None],
        request_rescan: Callable[[], bool],
        reload_profile: Callable[[], None],
    ) -> None:
        self._parent = parent
        self._current_game = current_game
        self._current_profile = current_profile
        self._profile_sii_path = profile_sii_path
        self._matcher = matcher
        self._local_versions = local_versions
        self._group_token_for = group_token_for
        self._apply_group_pin = apply_group_pin
        self._show_status = show_status
        self._request_rescan = request_rescan
        self._reload_profile = reload_profile
        self._import_dialog: ShareImportDialog | None = None
        self._create_dialog: ShareCreateDialog | None = None
        # one popup per share list, even if "check again" re-presents it
        self._warned_outdated_for: ShareList | None = None
        # freshness marker: results from any other thread are stale
        self._fetch_thread: ShareFetchThread | None = None
        # hard refs for every in-flight thread; a superseded lookup must stay
        # alive until it finishes or Python may GC a running QThread (abort)
        self._fetch_threads: set[ShareFetchThread] = set()

    # ------------------------------------------------------------------ #
    # menu entry points
    # ------------------------------------------------------------------ #

    def create_code(self) -> None:
        share = self._build_share()
        if share is None:
            return
        dialog = ShareCreateDialog(
            game=share.game.value,
            profile_name=share.profile_name,
            payload=to_payload(share),
            parent=self._parent,
        )
        self._create_dialog = dialog  # shutdown() must reach a running upload
        try:
            dialog.exec()
        finally:
            self._create_dialog = None

    def redeem_code(self) -> None:
        self._open_import("code")

    def export_file(self) -> None:
        share = self._build_share()
        if share is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self._parent,
            t("mod_share.import.save_caption"),
            "",
            t("mod_share.import.file_filter"),
        )
        if not path:
            return
        if not path.lower().endswith(FILE_SUFFIX):
            path += FILE_SUFFIX
        try:
            Path(path).write_text(serialize(share), encoding="utf-8")
        except OSError as exc:
            log.exception("share export failed for %s", path)
            self._show_status(t("status_bar.save_failed", error=str(exc)))
            return
        self._show_status(t("mod_share.import.exported", count=len(share.entries)))

    def import_file(self) -> None:
        self._open_import("file")

    def from_profile(self) -> None:
        self._open_import("profile")

    def shutdown(self, msecs: int) -> None:
        """Wait for in-flight lookups/uploads so app close cannot destroy live threads."""
        if self._create_dialog is not None:
            self._create_dialog.shutdown(msecs)
        for thread in list(self._fetch_threads):
            if thread.isRunning():
                thread.wait(msecs)

    def on_scan_finished(self) -> None:
        """Re-diff the open import dialog after a rescan (recheck flow)."""
        dialog = self._import_dialog
        if dialog is None or not dialog.isVisible():
            return
        share = dialog.current_share()
        if share is not None:
            self._present(share)

    # ------------------------------------------------------------------ #
    # import dialog wiring
    # ------------------------------------------------------------------ #

    def _open_import(self, source: str) -> None:
        if self._import_dialog is None:
            dialog = ShareImportDialog(self._parent)
            dialog.code_lookup_requested.connect(self._on_code_lookup)
            dialog.file_requested.connect(self._on_pick_file)
            dialog.profile_requested.connect(self._on_pick_profile)
            dialog.recheck_requested.connect(self._on_recheck)
            dialog.apply_requested.connect(self._on_apply)
            self._import_dialog = dialog
        self._import_dialog.reset()  # a reopened dialog must not keep an old preview
        profile = self._current_profile()
        self._import_dialog.set_target_profile(profile.profile_name if profile else "")
        self._import_dialog.set_source(source)
        self._import_dialog.show()
        self._import_dialog.raise_()

    def _on_code_lookup(self, code: str) -> None:
        assert self._import_dialog is not None
        self._import_dialog.show_lookup_busy()
        thread = ShareFetchThread(code)
        thread.succeeded.connect(
            lambda payload, th=thread: self._on_payload(payload, source_thread=th)
        )
        thread.failed.connect(
            lambda kind, th=thread: self._on_lookup_failed(kind, source_thread=th)
        )
        self._fetch_threads.add(thread)
        thread.finished.connect(lambda th=thread: self._fetch_threads.discard(th))
        self._fetch_thread = thread
        thread.start()

    def _on_payload(self, payload: dict, *, source_thread: object) -> None:
        if source_thread is not self._fetch_thread:
            return  # a newer lookup superseded this one
        try:
            self._present(from_payload(payload))
        except ModShareVersionError:
            self._show_import_error(t("mod_share.error.future_version"))
        except ModShareError:
            self._show_import_error(t("mod_share.error.rejected"))

    def _on_lookup_failed(self, kind: str, *, source_thread: object) -> None:
        if source_thread is not self._fetch_thread:
            return
        self._show_import_error(t(f"mod_share.error.{kind}"))

    def _on_pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._parent,
            t("mod_share.import.open_caption"),
            "",
            t("mod_share.import.file_filter"),
        )
        if not path:
            return
        self._load_share_file(path)

    def _load_share_file(self, path: str) -> None:
        # the user switched sources: a still-running code lookup is stale now
        # and must never overwrite this file's preview
        self._fetch_thread = None
        try:
            self._present(parse(Path(path).read_text(encoding="utf-8")))
        except ModShareVersionError:
            self._show_import_error(t("mod_share.error.future_version"))
        except (ModShareError, OSError, UnicodeDecodeError):
            self._show_import_error(t("mod_share.error.invalid_file"))

    def _on_pick_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._parent,
            t("mod_share.import.open_profile_caption"),
            "",
            t("mod_share.import.profile_filter"),
        )
        if not path:
            return
        self._load_foreign_profile(path)

    def _load_foreign_profile(self, path: str) -> None:
        self._fetch_thread = None  # same staleness rule as _load_share_file
        try:
            foreign = read_profile(Path(path))
        except Exception:  # noqa: BLE001 - any parse/crypto failure reads the same to the user
            log.warning("could not read foreign profile %s", path, exc_info=True)
            self._show_import_error(t("mod_share.error.bad_profile"))
            return
        share = build_from_profile(foreign, self._current_game(), versions={}, groups={})
        if not share.entries:
            self._show_import_error(t("mod_share.error.bad_profile"))
            return
        self._present(share)

    def _on_recheck(self) -> None:
        if not self._request_rescan():
            self.on_scan_finished()

    def _on_apply(self) -> None:
        dialog = self._import_dialog
        if dialog is None:
            return
        share = dialog.current_share()
        if share is None:
            return
        if self._apply(share, include_missing=dialog.include_missing()):
            dialog.close()

    # ------------------------------------------------------------------ #
    # core logic (unit-tested directly)
    # ------------------------------------------------------------------ #

    def _build_share(self) -> ShareList | None:
        profile = self._current_profile()
        if profile is None or not profile.active_mods:
            QMessageBox.information(
                self._parent, t("mod_share.empty_title"), t("mod_share.empty_body")
            )
            return None
        groups = {m.name: token for m in profile.active_mods if (token := self._group_token_for(m))}
        return build_from_profile(
            profile, self._current_game(), versions=self._local_versions(), groups=groups
        )

    def _installed_map(self, share: ShareList) -> dict[str, str | None]:
        matcher = self._matcher()
        out: dict[str, str | None] = {}
        for entry in share.entries:
            scanned = (
                matcher.lookup(ActiveMod(name=entry.name, display_name=entry.display_name))
                if matcher is not None
                else None
            )
            if scanned is None:
                out[entry.name] = None
            else:
                manifest = getattr(scanned, "manifest", None)
                out[entry.name] = (
                    manifest.package_version
                    if manifest is not None and manifest.package_version
                    else ""
                )
        return out

    def _present(self, share: ShareList) -> None:
        assert self._import_dialog is not None
        result = diff(share, installed=self._installed_map(share))
        self._import_dialog.show_share(
            share, result, game_matches=share.game is self._current_game()
        )
        self._warn_outdated(share, result)

    def _apply(self, share: ShareList, *, include_missing: bool) -> bool:
        path = self._profile_sii_path()
        if path is None:
            return False
        result = diff(share, installed=self._installed_map(share))
        skip = set() if include_missing else result.missing_names()
        mods = to_active_mods(share, skip=skip)
        try:
            save_active_mods(path, mods)
        except (OSError, ValueError) as exc:
            log.exception("share apply failed for %s", path)
            self._show_import_error(t("status_bar.save_failed", error=str(exc)))
            return False
        for entry in result.found:
            if entry.group in _KNOWN_GROUP_IDS:
                self._apply_group_pin(
                    ActiveMod(name=entry.name, display_name=entry.display_name), entry.group
                )
        self._reload_profile()
        self._show_status(t("mod_share.import.applied", count=len(mods)))
        return True

    def _warn_outdated(self, share: ShareList, result: ShareDiff) -> None:
        if not result.outdated or share is self._warned_outdated_for:
            return  # already warned for this share; "check again" re-presents it
        self._warned_outdated_for = share
        rows = "\n".join(
            t(
                "mod_share.import.outdated_row",
                name=entry.display_name or entry.name,
                local=local,
                share=entry.package_version,
            )
            for entry, local in result.outdated
        )
        QMessageBox.information(
            self._parent,
            t("mod_share.import.outdated_title"),
            f"{t('mod_share.import.outdated_body')}\n\n{rows}",
        )

    def _show_import_error(self, message: str) -> None:
        if self._import_dialog is not None:
            self._import_dialog.show_error(message)
