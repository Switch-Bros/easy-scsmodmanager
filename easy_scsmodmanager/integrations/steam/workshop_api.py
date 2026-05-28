"""Steam Workshop public-API client.

Steam exposes published-file metadata at::

    POST https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/

with form fields::

    itemcount=N
    publishedfileids[0]=<id>
    publishedfileids[1]=<id>
    ...

The endpoint is unauthenticated and returns title, description,
preview image URL, creator id and last-updated timestamp for each
file. We use it as a fallback source for the data SCS workshop mods
hide inside encrypted manifests or simply do not bundle (preview
image).

The preview image itself sits on the Steam CDN behind ``preview_url``
- we fetch it separately so the bulk metadata call stays small.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

DETAILS_ENDPOINT = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
BATCH_LIMIT = 50  # Steam tolerates more but smaller batches recover faster on failure
REQUEST_TIMEOUT = 20.0


@dataclass(frozen=True)
class WorkshopItem:
    workshop_id: str
    title: str | None
    description: str | None
    preview_url: str | None
    time_updated: int  # unix epoch, 0 when unknown
    creator: str | None
    file_size: int  # bytes, 0 when unknown


def fetch_metadata(
    workshop_ids: list[str],
    *,
    client: httpx.Client | None = None,
) -> dict[str, WorkshopItem]:
    """Synchronously fetch metadata for the given workshop ids.

    Splits the request into batches of :data:`BATCH_LIMIT`. Returns a
    dict keyed on workshop id; missing ids are absent from the result
    (Steam responds with ``result=9`` for unknown ids).
    """
    if not workshop_ids:
        return {}

    owned_client = client is None
    if client is None:
        client = httpx.Client(timeout=REQUEST_TIMEOUT)

    try:
        results: dict[str, WorkshopItem] = {}
        for batch in _chunks(workshop_ids, BATCH_LIMIT):
            results.update(_fetch_batch(client, batch))
        return results
    finally:
        if owned_client:
            client.close()


def fetch_preview_image(
    preview_url: str,
    *,
    client: httpx.Client | None = None,
) -> bytes | None:
    """Download one preview image from the Steam CDN.

    Returns ``None`` when the request fails. We keep failure quiet
    because the caller falls back to the placeholder icon.
    """
    owned_client = client is None
    if client is None:
        client = httpx.Client(timeout=REQUEST_TIMEOUT)
    try:
        try:
            response = client.get(preview_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.debug("preview fetch failed for %s: %s", preview_url, exc)
            return None
        return response.content
    finally:
        if owned_client:
            client.close()


def _chunks(seq: list[str], size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _fetch_batch(client: httpx.Client, ids: list[str]) -> dict[str, WorkshopItem]:
    form: dict[str, str] = {"itemcount": str(len(ids))}
    for idx, wid in enumerate(ids):
        form[f"publishedfileids[{idx}]"] = wid

    try:
        response = client.post(DETAILS_ENDPOINT, data=form)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("workshop metadata fetch failed: %s", exc)
        return {}

    payload = response.json()
    details = payload.get("response", {}).get("publishedfiledetails", [])
    out: dict[str, WorkshopItem] = {}
    for entry in details:
        wid = str(entry.get("publishedfileid", "") or "")
        if not wid:
            continue
        if entry.get("result") != 1:
            # 1 = OK, 9 = not found / private, others = error
            continue
        out[wid] = WorkshopItem(
            workshop_id=wid,
            title=entry.get("title") or None,
            description=entry.get("description") or None,
            preview_url=entry.get("preview_url") or None,
            time_updated=int(entry.get("time_updated") or 0),
            creator=entry.get("creator") or None,
            file_size=int(entry.get("file_size") or 0),
        )
    return out
