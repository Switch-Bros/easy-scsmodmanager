from pathlib import Path

import pytest

import easy_scsmodmanager.utils.i18n as i18n
from easy_scsmodmanager.utils.i18n import (
    available_languages,
    current_language,
    emoji,
    set_language,
    t,
)


def _fake_i18n_root(tmp_path: Path, codes: list[str]) -> Path:
    for code in codes:
        (tmp_path / code).mkdir(parents=True, exist_ok=True)
        (tmp_path / code / "main.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_returns_english_by_default() -> None:
    set_language("en")
    assert t("app.title") == "Easy SCSModManager"


def test_returns_german_when_switched() -> None:
    set_language("de")
    assert "Gerüst" in t("app.placeholder.scaffold")
    set_language("en")


def test_unknown_key_returns_the_key_for_visibility() -> None:
    set_language("en")
    assert t("this.key.does.not.exist") == "this.key.does.not.exist"


def test_format_placeholders() -> None:
    # No format placeholders in current strings, but the helper should be safe.
    set_language("en")
    assert t("app.title", unused="x") == "Easy SCSModManager"


def test_available_languages_only_lists_shipped_locales() -> None:
    # available_languages() must be exactly the locales that are both registered
    # in languages.json and actually ship a <code>/main.json. Both sides are
    # derived from the package, so adding a translation (en, de, zh, ...) needs
    # no edit here.
    root = i18n._i18n_root()
    shipped = {
        entry.name
        for entry in root.iterdir()
        if entry.is_dir() and root.joinpath(entry.name, "main.json").is_file()
    }
    expected = set(i18n._language_names()) & shipped

    langs = available_languages()
    assert set(langs) == expected
    assert all(langs[code] for code in langs)  # every display name is non-empty
    assert i18n.DEFAULT_LANG in langs  # the default locale always ships


def test_set_language_accepts_any_locale_that_ships_strings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _fake_i18n_root(tmp_path, ["en", "ru"])
    monkeypatch.setattr(i18n, "_i18n_root", lambda: root)

    set_language("ru")
    assert current_language() == "ru"

    set_language("en")  # reset; en ships strings in the fake root too


def test_set_language_rejects_a_locale_without_strings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _fake_i18n_root(tmp_path, ["en"])
    monkeypatch.setattr(i18n, "_i18n_root", lambda: root)

    set_language("en")
    set_language("xx")  # no xx/main.json -> ignored
    assert current_language() == "en"


def test_languages_json_offers_russian_for_the_upcoming_pr() -> None:
    # The RU translation PR should only need to drop in a ru/main.json.
    assert "ru" in i18n._language_names()


def test_emoji_lookup() -> None:
    assert emoji("settings") == "⚙️"
    assert emoji("does_not_exist") == ""
