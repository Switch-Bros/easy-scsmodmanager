from easy_scsmodmanager.utils.i18n import (
    available_languages,
    emoji,
    set_language,
    t,
)


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
    langs = available_languages()
    # de and en ship a main.json; the other languages.json entries do not.
    assert set(langs) == {"de", "en"}
    assert "Deutsch" in langs["de"]
    assert "English" in langs["en"]


def test_emoji_lookup() -> None:
    assert emoji("settings") == "⚙️"
    assert emoji("does_not_exist") == ""
