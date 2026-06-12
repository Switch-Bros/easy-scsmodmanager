# SPDX-License-Identifier: GPL-3.0-or-later
"""Hygiene guard for the bundled translation catalogues.

The workflow: English is the source of truth and German is maintained by the
core team, so both ship complete. Every other language is a community
translation that may lag behind - a missing key simply falls back to English at
runtime (see ``t()``), which is exactly how a translator spots what is new.

So the invariants are asymmetric:

1. The core languages (en, de) carry the exact same key set, no empty values,
   and no two keys sharing one (stripped) value - shared wording lives under a
   single ``common.*`` key instead of being copy-pasted.
2. Every other shipped language may be a *subset* of English (partial is fine)
   but must not carry orphan keys absent from English (those never render and
   are almost always typos or stale leftovers) and must not be empty strings.

The duplicate check is exact after ``strip()`` and case-sensitive, so
"Author" and "Author:" stay legitimately separate.
"""

from __future__ import annotations

import json
from collections import defaultdict

import easy_scsmodmanager.utils.i18n as i18n

DEFAULT_LANG = i18n.DEFAULT_LANG
# English is the reference; German is the second core language we keep complete.
CORE_LANGS = ("en", "de")


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


def test_core_languages_share_the_reference_key_set() -> None:
    # en is the reference; de must mirror it key-for-key so both core languages
    # stay complete. Community languages are checked separately (subset is fine).
    expected = set(_load(DEFAULT_LANG))
    for lang in CORE_LANGS:
        keys = set(_load(lang))
        missing = expected - keys
        extra = keys - expected
        assert not missing and not extra, f"{lang}: missing={missing}, extra={extra}"


def test_translations_carry_no_orphan_keys() -> None:
    # A non-core language may omit keys (they fall back to English), but a key
    # that English does not have never renders - flag it as a typo / stale key.
    expected = set(_load(DEFAULT_LANG))
    for lang in _shipped_languages():
        if lang in CORE_LANGS:
            continue
        orphans = set(_load(lang)) - expected
        assert not orphans, f"{lang}: keys absent from English: {orphans}"


def test_no_duplicate_values_in_core_languages() -> None:
    # The common.* dedup discipline only applies to the languages we author; a
    # community language legitimately repeats English-equal wording.
    for lang in CORE_LANGS:
        dups = _value_duplicates(_load(lang))
        assert not dups, f"{lang}: these values are shared by several keys: {dups}"


def test_no_empty_values() -> None:
    for lang in _shipped_languages():
        empty = [key for key, value in _load(lang).items() if value == ""]
        assert not empty, f"{lang}: empty values for {empty}"


def test_duplicate_detector_fires_on_an_intentional_duplicate() -> None:
    # Negative control: a crafted duplicate must be reported, otherwise the
    # guard above could pass vacuously.
    crafted = {"a.one": "Same", "a.two": " Same ", "a.three": "Unique"}
    assert _value_duplicates(crafted) == {"Same": ["a.one", "a.two"]}


def test_partial_translation_is_allowed_but_orphan_keys_are_not() -> None:
    # Documents the policy: a community language may translate only some of the
    # English keys (the rest fall back to English), yet a key English lacks is
    # always rejected. Drives the "translators just add a partial PR" workflow.
    reference = set(_load(DEFAULT_LANG))
    partial = dict(list(_load(DEFAULT_LANG).items())[:3])  # a strict subset
    assert not (set(partial) - reference)  # subset -> no orphans -> allowed
    assert set(partial) != reference  # and it really is incomplete
    assert {"made.up.key": "x"}.keys() - reference  # an orphan would be caught
