"""Persistent cache for Steam Workshop API responses.

Reuses the same SQLite database as ``ScanCache`` so users have a single
``scan_cache.db`` to inspect or delete. The ``workshop_meta`` table is
created by the ScanCache migration at user_version 3.

Each entry stores the metadata Steam returns (title, description,
preview image URL) plus the optionally-downloaded preview bytes. We
never delete entries; they age out implicitly when the database is
rebuilt.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkshopMetaEntry:
    workshop_id: str
    title: str | None
    description: str | None
    preview_url: str | None
    preview_bytes: bytes | None
    time_updated: int
    fetched_at: float


class WorkshopMetaCache:
    """Thin DAO over the workshop_meta table of an existing connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, workshop_id: str) -> WorkshopMetaEntry | None:
        row = self._conn.execute(
            "SELECT * FROM workshop_meta WHERE workshop_id = ?",
            (workshop_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_entry(row)

    def get_many(self, workshop_ids: list[str]) -> dict[str, WorkshopMetaEntry]:
        if not workshop_ids:
            return {}
        placeholders = ",".join("?" for _ in workshop_ids)
        rows = self._conn.execute(
            f"SELECT * FROM workshop_meta WHERE workshop_id IN ({placeholders})",
            workshop_ids,
        ).fetchall()
        return {row["workshop_id"]: _row_to_entry(row) for row in rows}

    def put_metadata(
        self,
        workshop_id: str,
        *,
        title: str | None,
        description: str | None,
        preview_url: str | None,
        time_updated: int,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO workshop_meta (
                    workshop_id, title, description, preview_url,
                    time_updated, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(workshop_id) DO UPDATE SET
                    title        = excluded.title,
                    description  = excluded.description,
                    preview_url  = excluded.preview_url,
                    time_updated = excluded.time_updated,
                    fetched_at   = excluded.fetched_at
                """,
                (
                    workshop_id,
                    title,
                    description,
                    preview_url,
                    time_updated,
                    time.time(),
                ),
            )

    def put_preview_bytes(self, workshop_id: str, preview_bytes: bytes) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE workshop_meta SET preview_bytes = ? WHERE workshop_id = ?",
                (preview_bytes, workshop_id),
            )

    def workshop_ids_without_preview(self, workshop_ids: list[str]) -> list[str]:
        """Returns the subset of ids that have metadata but no preview bytes."""
        if not workshop_ids:
            return []
        placeholders = ",".join("?" for _ in workshop_ids)
        rows = self._conn.execute(
            f"""
            SELECT workshop_id FROM workshop_meta
            WHERE workshop_id IN ({placeholders})
              AND preview_bytes IS NULL
              AND preview_url IS NOT NULL
            """,
            workshop_ids,
        ).fetchall()
        return [row["workshop_id"] for row in rows]


def _row_to_entry(row: sqlite3.Row) -> WorkshopMetaEntry:
    preview = row["preview_bytes"]
    return WorkshopMetaEntry(
        workshop_id=row["workshop_id"],
        title=row["title"],
        description=row["description"],
        preview_url=row["preview_url"],
        preview_bytes=bytes(preview) if preview is not None else None,
        time_updated=row["time_updated"] or 0,
        fetched_at=row["fetched_at"],
    )
