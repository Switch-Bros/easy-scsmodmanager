"""Persistent set of favourited mods.

Kept in its own SQLite file under data (not cache) so clearing the scan cache
never drops a user's favourites. The key is the mod's stable name (the token it
takes in active_mods[]), so a favourite survives icon/display-name changes and
is unique across workshop mods that share a file stem.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def default_favorites_path() -> Path:
    """``$XDG_DATA_HOME/easy-scsmodmanager/favorites.db`` or HOME fallback."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path(os.environ.get("HOME", "~")).expanduser() / ".local" / "share"
    return base / "easy-scsmodmanager" / "favorites.db"


class FavoritesStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(db_path))
        self._con.execute("CREATE TABLE IF NOT EXISTS favorite (mod_key TEXT PRIMARY KEY)")
        self._con.commit()

    def is_favorite(self, mod_key: str) -> bool:
        row = self._con.execute("SELECT 1 FROM favorite WHERE mod_key = ?", (mod_key,)).fetchone()
        return row is not None

    def set_favorite(self, mod_key: str, favorite: bool) -> None:
        if favorite:
            self._con.execute(
                "INSERT INTO favorite (mod_key) VALUES (?) ON CONFLICT(mod_key) DO NOTHING",
                (mod_key,),
            )
        else:
            self._con.execute("DELETE FROM favorite WHERE mod_key = ?", (mod_key,))
        self._con.commit()

    def all(self) -> set[str]:
        return {row[0] for row in self._con.execute("SELECT mod_key FROM favorite")}

    def close(self) -> None:
        self._con.close()
