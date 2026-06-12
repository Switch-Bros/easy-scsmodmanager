"""Drives MapCombo export/import on the maps spacer.

Pulled out of MainWindow so the window stays a thin coordinator. The flow is
UI-heavy (file dialogs, message boxes) so it keeps a parent widget for those,
plus the few things it acts on: the active list it reorders, the presenter it
asks for local versions, a way to post a status message, and a way to request
a rescan.

Import is the tricky part: the maps block must reflect the current disk state
before the missing-maps check runs, so import triggers a rescan and defers the
actual apply until the scan finishes. The window calls :meth:`apply_pending`
from its scan-finished handler when :meth:`has_pending` is true.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from easy_scsmodmanager.services.map_combo import (
    MapComboEntry,
    MapComboError,
    missing,
    outdated,
    parse,
    reorder,
    serialize,
)
from easy_scsmodmanager.ui.mod_presenter import ModPresenter
from easy_scsmodmanager.ui.widgets.active_mod_list import ActiveModList
from easy_scsmodmanager.utils.i18n import t


class MapComboController:
    def __init__(
        self,
        *,
        parent: QWidget,
        active_list: ActiveModList,
        presenter: ModPresenter,
        show_status: Callable[[str], None],
        request_rescan: Callable[[], bool],
    ) -> None:
        self._parent = parent
        self._active_list = active_list
        self._presenter = presenter
        self._show_status = show_status
        self._request_rescan = request_rescan
        # a combo waiting to be applied once a fresh scan completes
        self._pending: list[MapComboEntry] | None = None

    def has_pending(self) -> bool:
        return self._pending is not None

    # ------------------------------------------------------------------ #
    # export
    # ------------------------------------------------------------------ #

    def export(self) -> None:
        block = self._active_list.maps_block()
        if not block:
            QMessageBox.information(
                self._parent, t("map_combo.empty_title"), t("map_combo.empty_body")
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self._parent, t("map_combo.save_caption"), "", t("map_combo.file_filter")
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        versions = self._presenter.local_versions()
        entries = [
            MapComboEntry(
                name=m.name,
                display_name=m.display_name,
                package_version=versions.get(m.name, ""),
            )
            for m in block
        ]
        Path(path).write_text(serialize(entries), encoding="utf-8")
        self._show_status(t("map_combo.exported", count=len(entries)))

    # ------------------------------------------------------------------ #
    # import
    # ------------------------------------------------------------------ #

    def import_(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._parent, t("map_combo.open_caption"), "", t("map_combo.file_filter")
        )
        if not path:
            return
        try:
            combo = parse(Path(path).read_text(encoding="utf-8"))
        except (MapComboError, OSError):
            QMessageBox.warning(
                self._parent, t("map_combo.invalid_title"), t("map_combo.invalid_body")
            )
            return
        # rescan first so the maps block reflects the current disk state, then
        # apply the combo from the scan-finished callback. Without this the
        # missing-maps check runs against stale scan data.
        self._pending = combo
        if self._request_rescan():
            self._show_status(t("map_combo.import_scanning"))
        else:
            self.apply_pending()

    def apply_pending(self) -> None:
        combo = self._pending
        self._pending = None
        if combo is None:
            return
        block = self._active_list.maps_block()
        gaps = missing(combo, {m.name for m in block})
        if gaps:
            names = "\n".join(f"- {e.display_name or e.name}" for e in gaps)
            QMessageBox.warning(
                self._parent,
                t("map_combo.missing_title"),
                f"{t('map_combo.missing_body')}\n\n{names}",
            )
            return
        self._active_list.apply_combo_order(reorder(block, combo))
        self._show_status(t("map_combo.imported", count=len(combo)))
        self._warn_outdated(combo)

    def _warn_outdated(self, combo: list[MapComboEntry]) -> None:
        """After import, hint (never block) about maps the combo built newer."""
        stale = outdated(combo, self._presenter.local_versions())
        if not stale:
            return
        rows = "\n".join(
            t(
                "map_combo.outdated_row",
                name=entry.display_name or entry.name,
                local=local,
                combo=entry.package_version,
            )
            for entry, local in stale
        )
        QMessageBox.information(
            self._parent,
            t("common.update_available"),
            f"{t('map_combo.outdated_body')}\n\n{rows}",
        )
