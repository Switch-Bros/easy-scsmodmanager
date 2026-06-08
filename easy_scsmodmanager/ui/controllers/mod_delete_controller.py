"""Confirm-and-trash flow for deleting local mods.

Only non-Workshop mods are deletable; the rest of a mixed selection is skipped
and called out in the dialog. The confirm button is DANGER-styled and Cancel is
the default, so an Enter reflex never deletes. The actual file move goes through
mod_trash (OS trash, no hard delete); model surgery (drop from the in-memory
list, the cache and the active list) is handed back to the window via callback.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QWidget

from easy_scsmodmanager.services.mod_identity import workshop_id_for_path
from easy_scsmodmanager.services.mod_scanner import ScannedMod
from easy_scsmodmanager.services.mod_trash import active_profiles_for, move_path_to_trash
from easy_scsmodmanager.services.profile_reader import Profile
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.utils.i18n import t

_MAX_LISTED = 8


class ModDeleteController:
    def __init__(
        self,
        *,
        parent: QWidget,
        profiles: Callable[[], list[Profile]],
        display_name_for: Callable[[ScannedMod], str],
        on_mods_deleted: Callable[[list[ScannedMod]], None],
        show_status: Callable[[str, int], None],
    ) -> None:
        self._parent = parent
        self._profiles = profiles
        self._name = display_name_for
        self._on_deleted = on_mods_deleted
        self._show_status = show_status

    def request_delete(self, mods: list[ScannedMod]) -> None:
        locals_ = [m for m in mods if workshop_id_for_path(m.path) is None]
        skipped = len(mods) - len(locals_)
        if not locals_:
            return

        profiles = self._profiles()
        affected = {m.path: active_profiles_for(m, profiles) for m in locals_}
        if not self._confirm(locals_, affected, skipped):
            return

        deleted: list[ScannedMod] = []
        for mod in locals_:
            if move_path_to_trash(mod.path):
                deleted.append(mod)
            else:
                QMessageBox.warning(
                    self._parent,
                    t("dialog.delete.title_one"),
                    t("dialog.delete.failed", name=self._name(mod)),
                )

        if deleted:
            self._on_deleted(deleted)
            self._show_status(t("dialog.delete.done", count=len(deleted)), 5000)

    # ---- dialog -------------------------------------------------------- #

    def _confirm(
        self,
        mods: list[ScannedMod],
        affected: dict[Path, list[str]],
        skipped: int,
    ) -> bool:
        box = QMessageBox(self._parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.RichText)
        if len(mods) == 1:
            box.setWindowTitle(t("dialog.delete.title_one"))
        else:
            box.setWindowTitle(t("dialog.delete.title_many", count=len(mods)))
        box.setText(self._body_html(mods, affected, skipped))

        confirm = box.addButton(t("dialog.delete.confirm"), QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(t("dialog.delete.cancel"), QMessageBox.ButtonRole.RejectRole)
        confirm.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.DANGER}; color: {Theme.ON_DANGER};"
            f" border-radius: 3px; padding: 4px 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Theme.DANGER_HOVER}; }}"
        )
        box.setDefaultButton(cancel)  # Enter never deletes
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() is confirm

    def _body_html(
        self,
        mods: list[ScannedMod],
        affected: dict[Path, list[str]],
        skipped: int,
    ) -> str:
        parts: list[str] = []
        # 1) what happens
        if len(mods) == 1:
            parts.append(_escape(t("dialog.delete.body_one", name=self._name(mods[0]))))
        else:
            parts.append(_escape(t("dialog.delete.body_many")))
            shown = mods[:_MAX_LISTED]
            items = "".join(f"<li>{_escape(self._name(m))}</li>" for m in shown)
            rest = len(mods) - len(shown)
            if rest > 0:
                items += f"<li>{_escape(t('dialog.delete.more', count=rest))}</li>"
            parts.append(f"<ul>{items}</ul>")

        # 2) warning block - only if at least one mod is active somewhere
        warned = [m for m in mods if affected.get(m.path)]
        if warned:
            distinct = {p for m in warned for p in affected[m.path]}
            lines = [
                f"<b style='color:{Theme.WARNING}'>{_escape(t('dialog.delete.warn_heading'))}</b>"
            ]
            for m in warned:
                profiles = '", "'.join(affected[m.path])
                if len(mods) == 1:
                    lines.append(_escape(f'"{profiles}"'))
                else:
                    lines.append(
                        _escape(
                            t("dialog.delete.warn_entry", name=self._name(m), profiles=profiles)
                        )
                    )
            hint = "warn_hint_one" if len(distinct) == 1 else "warn_hint_many"
            lines.append(_escape(t(f"dialog.delete.{hint}")))
            parts.append("<br>".join(lines))

        # 3) workshop hint
        if skipped > 0:
            parts.append(
                f"<span style='color:{Theme.TEXT_DIM}'>"
                f"{_escape(t('dialog.delete.workshop_skipped', count=skipped))}</span>"
            )

        return "<br><br>".join(parts)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
