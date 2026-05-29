from __future__ import annotations

import logging

from easy_scsmodmanager.utils.logging_setup import setup_logging


def test_quiets_noisy_http_loggers() -> None:
    setup_logging()

    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING
