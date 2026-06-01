from __future__ import annotations

import logging
import sys
from importlib import resources

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from easy_scsmodmanager import __app_name__
from easy_scsmodmanager.core.settings_store import SettingsStore
from easy_scsmodmanager.ui.font_helper import FontHelper
from easy_scsmodmanager.ui.main_window import MainWindow
from easy_scsmodmanager.utils.i18n import set_language
from easy_scsmodmanager.utils.logging_setup import setup_logging


def _app_icon() -> QIcon:
    res = resources.files("easy_scsmodmanager.resources") / "icon.png"
    with resources.as_file(res) as path:
        return QIcon(str(path))


def _apply_saved_language(store: SettingsStore) -> None:
    """Apply the persisted language before any widget is built.

    ``t()`` resolves at widget construction, so the language must be set
    before MainWindow exists; switching it later needs a restart.
    """
    lang = store.get_language()
    if lang:
        set_language(lang)


def run(argv: list[str]) -> int:
    setup_logging()
    log = logging.getLogger(__name__)
    log.info("Starting %s", __app_name__)

    app = QApplication(argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName("Switch-Bros")
    app.setWindowIcon(_app_icon())

    store = SettingsStore()
    _apply_saved_language(store)
    FontHelper.apply_app_font(app, size=10)

    window = MainWindow(game=store.get_active_game(), auto_scan=True)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run(sys.argv))
