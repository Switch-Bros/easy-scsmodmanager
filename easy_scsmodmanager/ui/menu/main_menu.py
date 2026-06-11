"""Builds the main window's menu bar.

Pulled out of MainWindow so the window class stays focused on coordination.
The actions bind straight to the window's handlers, so the builder takes the
window itself (typed under TYPE_CHECKING to avoid an import cycle).
"""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QApplication

from easy_scsmodmanager.core.game_paths import GAME_DIRECTORY_NAME, Game
from easy_scsmodmanager.utils.i18n import current_language, t

if TYPE_CHECKING:
    from easy_scsmodmanager.ui.main_window import MainWindow

GITHUB_REPO_URL = "https://github.com/Switch-Bros/easy-scsmodmanager"
GITHUB_ISSUES_URL = f"{GITHUB_REPO_URL}/issues"

# Help -> Docs entries; opened as GitHub blob URLs (no need to ship the docs in
# the AppImage/exe - the browser fetches the language folder from GitHub).
_DOCS = (
    ("manual", "USER_MANUAL.md"),
    ("tips", "TIPS_AND_TRICKS.md"),
    ("shortcuts", "KEYBOARD_SHORTCUTS.md"),
    ("faq", "FAQ.md"),
)


def _open_doc(filename: str) -> None:
    lang = current_language()
    webbrowser.open(f"{GITHUB_REPO_URL}/blob/main/docs/{lang}/{filename}")


def build_menu_bar(window: MainWindow) -> None:
    menu_bar = window.menuBar()

    file_menu = menu_bar.addMenu(t("menu.file"))
    refresh = QAction(t("menu.file.refresh"), window)
    refresh.setShortcut("F5")
    refresh.triggered.connect(window._on_refresh)
    file_menu.addAction(refresh)

    clear_cache = QAction(t("menu.file.clear_cache"), window)
    clear_cache.triggered.connect(window._on_clear_cache)
    file_menu.addAction(clear_cache)

    settings = QAction(t("menu.file.settings"), window)
    settings.triggered.connect(window._on_open_settings)
    file_menu.addAction(settings)

    file_menu.addSeparator()
    quit_action = QAction(t("menu.file.quit"), window)
    quit_action.setShortcut("Ctrl+Q")
    quit_action.triggered.connect(QApplication.instance().quit)
    file_menu.addAction(quit_action)

    _build_game_menu(window)

    tools_menu = menu_bar.addMenu(t("menu.tools"))
    extract = QAction(t("menu.tools.extract"), window)
    extract.triggered.connect(window._on_open_extract)
    tools_menu.addAction(extract)

    open_logs = QAction(t("menu.tools.open_log_folder"), window)
    open_logs.triggered.connect(window._on_open_log_folder)
    tools_menu.addAction(open_logs)

    share_menu = menu_bar.addMenu(t("menu.share"))
    share = window._share_controller
    share_actions = (
        ("create_code", share.create_code),
        ("redeem_code", share.redeem_code),
        ("export_file", share.export_file),
        ("import_file", share.import_file),
        ("from_profile", share.from_profile),
    )
    for key, handler in share_actions:
        action = QAction(t(f"menu.share.{key}"), window)
        action.triggered.connect(handler)
        share_menu.addAction(action)

    help_menu = menu_bar.addMenu(t("menu.help"))
    about = QAction(t("menu.help.about"), window)
    about.triggered.connect(window._show_about)
    help_menu.addAction(about)

    docs_menu = help_menu.addMenu(t("menu.help.docs"))
    if docs_menu is not None:
        for key, filename in _DOCS:
            doc_action = QAction(t(f"menu.help.docs.{key}"), window)
            doc_action.triggered.connect(lambda _checked=False, f=filename: _open_doc(f))
            docs_menu.addAction(doc_action)

    issues = QAction(t("menu.help.report_issue"), window)
    issues.triggered.connect(lambda: webbrowser.open(GITHUB_ISSUES_URL))
    help_menu.addAction(issues)

    updates = QAction(t("menu.help.check_updates"), window)
    updates.triggered.connect(window._on_check_updates)
    help_menu.addAction(updates)


def _build_game_menu(window: MainWindow) -> None:
    """A 'Game' menu with one radio entry per game; only installed ones enabled.

    Stashes the actions on the window so it can re-sync the checkmark after a
    cancelled switch.
    """
    game_menu = window.menuBar().addMenu(t("menu.game"))
    group = QActionGroup(window)
    group.setExclusive(True)
    available = window.available_games()
    actions: dict[Game, QAction] = {}
    for game in Game:
        action = QAction(GAME_DIRECTORY_NAME[game], window)
        action.setCheckable(True)
        action.setChecked(game is window._game)
        action.setEnabled(game in available)
        action.triggered.connect(lambda _checked=False, g=game: window._switch_game(g))
        group.addAction(action)
        game_menu.addAction(action)
        actions[game] = action
    window._game_actions = actions
