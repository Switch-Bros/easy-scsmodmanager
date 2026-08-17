"""Everything a mod loses, on screen instead of in a tooltip.

The hover tooltip caps at twelve rows and vanishes the moment the pointer
moves, which is useless for a load order with eighty shadowed files. This
dialog shows the same data uncapped, selectable, and switchable between the
mod that was right-clicked and every marked mod at once.

It is handed a finished report plus the display-name map - no presenter, no
scan - so it stays testable. The saved log and the clipboard always carry the
complete report; the radio only changes what is on screen.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from easy_scsmodmanager.services.conflict_detect import Severity
from easy_scsmodmanager.ui.conflict_text import (
    GLYPH_FREQUENT,
    GLYPH_FULL,
    GLYPH_PARTIAL,
    ReportEntry,
    frequent_lines,
    override_lines,
    report_text,
)
from easy_scsmodmanager.ui.theme import Theme
from easy_scsmodmanager.ui.widgets.active_list_widgets import conflict_legend_html
from easy_scsmodmanager.utils.i18n import t

# rows are indented under their header so the file column lines up
_ROW_INDENT_PX = 16


class ConflictDialog(QDialog):
    """Full conflict details for one mod or for the whole load order."""

    def __init__(
        self,
        entries: Sequence[ReportEntry],
        names: Mapping[str, str],
        *,
        focus_name: str,
        version: str,
        game: str,
        profile: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entries = list(entries)
        self._names = names
        self._focus_name = focus_name
        self._version = version
        self._game = game
        self._profile = profile

        self.setWindowTitle(t("conflict_dialog.title"))
        self.setMinimumSize(480, 360)
        self.resize(720, 540)
        self.setStyleSheet(f"background-color: {Theme.BACKGROUND}; color: {Theme.TEXT};")

        root = QVBoxLayout(self)
        root.setSpacing(8)

        scope = QHBoxLayout()
        self._scope_this = QRadioButton(
            t("conflict_dialog.scope_this", name=self._focus_display_name())
        )
        self._scope_all = QRadioButton(t("conflict_dialog.scope_all"))
        self._scope_this.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self._scope_this)
        group.addButton(self._scope_all)
        self._scope_all.toggled.connect(lambda _checked: self._render())
        scope.addWidget(self._scope_this)
        scope.addWidget(self._scope_all)
        scope.addStretch(1)
        root.addLayout(scope)

        legend = QLabel(conflict_legend_html())
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setStyleSheet(f"color: {Theme.TEXT_DIM}; font-size: 10px;")
        root.addWidget(legend)

        self._view = QTextEdit()
        self._view.setReadOnly(True)
        mono = QFont()
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setFamily("monospace")
        self._view.setFont(mono)
        self._view.setStyleSheet(
            f"background-color: {Theme.SURFACE}; color: {Theme.TEXT}; "
            f"border: {Theme.BORDER_WIDTH}px solid {Theme.SURFACE}; border-radius: 4px;"
        )
        root.addWidget(self._view, 1)

        buttons = QDialogButtonBox()
        save = QPushButton(t("conflict_dialog.save_file"))
        save.clicked.connect(self._on_save)
        buttons.addButton(save, QDialogButtonBox.ButtonRole.ActionRole)
        copy = QPushButton(t("common.copy"))
        copy.clicked.connect(self._on_copy)
        buttons.addButton(copy, QDialogButtonBox.ButtonRole.ActionRole)
        close = QPushButton(t("common.close"))
        close.clicked.connect(self.reject)
        buttons.addButton(close, QDialogButtonBox.ButtonRole.RejectRole)
        root.addWidget(buttons)

        self._render()

    def shown_text(self) -> str:
        """What the user currently reads, markup stripped (for tests)."""
        return self._view.toPlainText()

    # ------------------------------------------------------------------ #
    # rendering
    # ------------------------------------------------------------------ #

    def _focus_display_name(self) -> str:
        for e in self._entries:
            if e.name == self._focus_name:
                return e.display_name
        return self._names.get(self._focus_name, self._focus_name)

    def _visible_entries(self) -> list[ReportEntry]:
        if self._scope_all.isChecked():
            return self._entries
        return [e for e in self._entries if e.name == self._focus_name]

    def _render(self) -> None:
        visible = self._visible_entries()
        if not visible:
            self._view.setHtml(
                f'<div align="center" style="color:{Theme.TEXT_DIM}">'
                f"{escape(t('conflict_dialog.empty'))}</div>"
            )
            return
        blocks = [self._entry_html(e) for e in visible]
        self._view.setHtml("<br>".join(blocks))

    def _entry_html(self, entry: ReportEntry) -> str:
        parts = [f"<div><b>{escape(entry.display_name)}</b></div>"]
        if entry.override is not None:
            glyph, colour = (
                (GLYPH_FULL, Theme.DANGER)
                if entry.override.severity is Severity.FULL
                else (GLYPH_PARTIAL, Theme.WARNING)
            )
            lines, _ = override_lines(entry.override, self._names)
            parts.append(_header_html(glyph, colour, lines[0]))
            parts.extend(_row_html(line) for line in lines[1:])
        if entry.frequent is not None:
            lines, _ = frequent_lines(entry.frequent, also=entry.override is not None)
            parts.append(_header_html(GLYPH_FREQUENT, Theme.TEXT_DIM, lines[0]))
            parts.extend(_row_html(line) for line in lines[1:])
        return "".join(parts)

    # ------------------------------------------------------------------ #
    # export
    # ------------------------------------------------------------------ #

    def _report_text(self) -> str:
        # the timestamp belongs to the export, not to when the dialog opened
        return report_text(
            self._entries,
            self._names,
            version=self._version,
            game=self._game,
            profile=self._profile,
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def _default_file_name(self) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d")
        return f"escsmm-conflicts-{self._game.lower()}-{stamp}.txt"

    def _on_copy(self) -> None:
        clip = QGuiApplication.clipboard()
        if clip is not None:
            clip.setText(self._report_text())

    def _on_save(self) -> None:
        # always the whole report - the radio is for reading, not for exporting
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("conflict_dialog.save_caption"),
            self._default_file_name(),
            t("conflict_dialog.file_filter"),
        )
        if not path:
            return
        if not path.lower().endswith(".txt"):
            path += ".txt"
        try:
            Path(path).write_text(self._report_text(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(
                self, t("conflict_dialog.title"), t("conflict_dialog.save_failed", error=exc)
            )
            return
        QMessageBox.information(
            self, t("conflict_dialog.title"), t("conflict_dialog.saved", path=path)
        )


def _header_html(glyph: str, colour: str, text: str) -> str:
    # colour rides on the glyph only; the header says the severity in words too
    return f'<div><span style="color:{colour}">{glyph}</span> {escape(text)}</div>'


def _row_html(text: str) -> str:
    # pre-wrap keeps the padding around the arrow that the row format builds in;
    # plain HTML would collapse it and the columns would drift
    return (
        f'<div style="margin-left:{_ROW_INDENT_PX}px; white-space:pre-wrap">'
        f"{escape(text)}</div>"
    )
