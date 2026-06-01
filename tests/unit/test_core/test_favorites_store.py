from pathlib import Path

from easy_scsmodmanager.core.favorites_store import FavoritesStore


def test_not_favorite_by_default(tmp_path: Path) -> None:
    fav = FavoritesStore(tmp_path / "fav.db")
    assert fav.is_favorite("cool_truck") is False


def test_set_and_unset(tmp_path: Path) -> None:
    fav = FavoritesStore(tmp_path / "fav.db")
    fav.set_favorite("cool_truck", True)
    assert fav.is_favorite("cool_truck") is True
    fav.set_favorite("cool_truck", False)
    assert fav.is_favorite("cool_truck") is False


def test_all_lists_only_current_favorites(tmp_path: Path) -> None:
    fav = FavoritesStore(tmp_path / "fav.db")
    fav.set_favorite("a", True)
    fav.set_favorite("b", True)
    fav.set_favorite("b", False)
    assert fav.all() == {"a"}


def test_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "fav.db"
    fav = FavoritesStore(path)
    fav.set_favorite("kept", True)
    fav.close()
    assert FavoritesStore(path).is_favorite("kept") is True
