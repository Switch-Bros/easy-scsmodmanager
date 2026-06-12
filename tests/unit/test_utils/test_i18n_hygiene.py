# SPDX-License-Identifier: GPL-3.0-or-later
"""Hygiene guard for the bundled translation catalogues.

Three invariants keep the i18n files lean and consistent:

1. No two keys in one language may carry the same (stripped) value - shared
   wording lives under a single ``common.*`` key instead of being copy-pasted.
2. Every shipped language exposes the exact same key set, so adding a
   translation has to mirror the others key-for-key.
3. No value is the empty string.

The duplicate check is exact after ``strip()`` and case-sensitive, so
"Author" and "Author:" stay legitimately separate.
"""

from __future__ import annotations

import json
from collections import defaultdict

import easy_scsmodmanager.utils.i18n as i18n

DEFAULT_LANG = i18n.DEFAULT_LANG


def _shipped_languages() -> list[str]:
    """Locale codes that actually ship a ``<code>/main.json`` in the package."""
    root = i18n._i18n_root()
    return sorted(
        entry.name
        for entry in root.iterdir()
        if entry.is_dir() and root.joinpath(entry.name, "main.json").is_file()
    )


def _load(lang: str) -> dict[str, str]:
    root = i18n._i18n_root()
    return json.loads(root.joinpath(lang, "main.json").read_text(encoding="utf-8"))


def _value_duplicates(mapping: dict[str, str]) -> dict[str, list[str]]:
    """Stripped value -> the keys that share it, only for values used > once."""
    by_value: dict[str, list[str]] = defaultdict(list)
    for key, value in mapping.items():
        by_value[value.strip()].append(key)
    return {value: keys for value, keys in by_value.items() if len(keys) > 1}


def test_no_duplicate_values_per_language() -> None:
    for lang in _shipped_languages():
        dups = _value_duplicates(_load(lang))
        assert not dups, f"{lang}: these values are shared by several keys: {dups}"


def test_key_sets_identical_across_languages() -> None:
    expected = set(_load(DEFAULT_LANG))
    for lang in _shipped_languages():
        keys = set(_load(lang))
        missing = expected - keys
        extra = keys - expected
        assert not missing and not extra, f"{lang}: missing={missing}, extra={extra}"


def test_no_empty_values() -> None:
    for lang in _shipped_languages():
        empty = [key for key, value in _load(lang).items() if value == ""]
        assert not empty, f"{lang}: empty values for {empty}"


def test_duplicate_detector_fires_on_an_intentional_duplicate() -> None:
    # Negative control: a crafted duplicate must be reported, otherwise the
    # guard above could pass vacuously.
    crafted = {"a.one": "Same", "a.two": " Same ", "a.three": "Unique"}
    assert _value_duplicates(crafted) == {"Same": ["a.one", "a.two"]}
