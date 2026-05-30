"""Translation lookup. One JSON per language in its own folder, flat dotted keys.

Layout (mirrors SLM)::

    resources/i18n/
        languages.json      # global: code -> display name (with flag)
        emoji.json          # global: name -> emoji glyph
        en/main.json        # flat "a.b.c": "text"
        de/main.json

If a key is missing, the key itself is returned so the bug is visible in the UI.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from importlib import resources

DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "de")

_I18N_PACKAGE = "easy_scsmodmanager.resources.i18n"

log = logging.getLogger(__name__)


def _detect_language() -> str:
    env = os.environ.get("ESCSMM_LANG") or os.environ.get("LANG") or ""
    code = env.split(".")[0].split("_")[0].lower()
    if code in SUPPORTED_LANGS:
        return code
    return DEFAULT_LANG


def _read_json(*parts: str) -> dict:
    try:
        data = resources.files(_I18N_PACKAGE).joinpath(*parts).read_text(encoding="utf-8")
        return json.loads(data)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        log.warning("Failed to load i18n resource %s: %s", "/".join(parts), exc)
        return {}


@lru_cache(maxsize=4)
def _load(lang: str) -> dict[str, str]:
    return _read_json(lang, "main.json")


@lru_cache(maxsize=1)
def _emoji_table() -> dict[str, str]:
    return _read_json("emoji.json").get("emoji", {})


@lru_cache(maxsize=1)
def _language_names() -> dict[str, str]:
    return _read_json("languages.json").get("languages", {})


_active_lang = _detect_language()


def set_language(lang: str) -> None:
    global _active_lang
    if lang in SUPPORTED_LANGS:
        _active_lang = lang
    else:
        log.warning("Unsupported language %s, keeping %s", lang, _active_lang)


def current_language() -> str:
    """The active language code (e.g. 'de')."""
    return _active_lang


def t(key: str, **kwargs: object) -> str:
    table = _load(_active_lang)
    value = table.get(key)
    if value is None and _active_lang != DEFAULT_LANG:
        value = _load(DEFAULT_LANG).get(key)
    if value is None:
        return key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value


def emoji(name: str) -> str:
    """Emoji glyph for a name from emoji.json, or '' if the name is unknown."""
    return _emoji_table().get(name, "")


def available_languages() -> dict[str, str]:
    """Selectable languages as ``code -> display name``.

    Driven by languages.json order, restricted to codes that actually ship a
    ``<code>/main.json`` - so the settings dropdown never offers a language we
    have no strings for.
    """
    root = resources.files(_I18N_PACKAGE)
    result: dict[str, str] = {}
    for code, name in _language_names().items():
        if root.joinpath(code, "main.json").is_file():
            result[code] = name
    return result
