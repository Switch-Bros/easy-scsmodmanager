"""Persistent per-mod category overrides.

Kept in their own SQLite file so clearing the scan cache never drops a
user's manual corrections. mod_key is the mod's path stem.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def default_overrides_path() -> Path:
    """``$XDG_DATA_HOME/easy-scsmodmanager/overrides.db`` or HOME fallback.

    Deliberately under data, not cache: wiping the scan cache must never drop
    a user's manual category corrections.
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path(os.environ.get("HOME", "~")).expanduser() / ".local" / "share"
    return base / "easy-scsmodmanager" / "overrides.db"


def default_group_overrides_path() -> Path:
    """``$XDG_DATA_HOME/easy-scsmodmanager/group_overrides.db`` or HOME fallback.

    Separate from overrides.db: group overrides only affect active-list
    grouping, not the grid badge/filter.
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path(os.environ.get("HOME", "~")).expanduser() / ".local" / "share"
    return base / "easy-scsmodmanager" / "group_overrides.db"


class CategoryOverrides:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(db_path))
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS category_override "
            "(mod_key TEXT PRIMARY KEY, token TEXT NOT NULL)"
        )
        self._con.commit()

    def get(self, mod_key: str) -> str | None:
        row = self._con.execute(
            "SELECT token FROM category_override WHERE mod_key = ?", (mod_key,)
        ).fetchone()
        return row[0] if row else None

    def set(self, mod_key: str, token: str) -> None:
        self._con.execute(
            "INSERT INTO category_override (mod_key, token) VALUES (?, ?) "
            "ON CONFLICT(mod_key) DO UPDATE SET token = excluded.token",
            (mod_key, token),
        )
        self._con.commit()

    def clear(self, mod_key: str) -> None:
        self._con.execute("DELETE FROM category_override WHERE mod_key = ?", (mod_key,))
        self._con.commit()

    def close(self) -> None:
        self._con.close()
