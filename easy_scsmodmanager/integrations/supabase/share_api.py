"""Talks to the ModShare Supabase backend.

All access goes through two RPCs (see packaging/supabase.sql); there is no
direct table access, so the publishable key in this file cannot be used to
enumerate or modify other people's shares. The constants stay empty until
the Supabase project exists - sharing is then reported as not configured
and the UI offers only the file-based paths.
"""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)

# Supabase project for the ModShare backend (see packaging/supabase.sql).
# The key is the publishable "anon" key on purpose: access is RPC-only with RLS
# fully locking the table, so it carries no privilege beyond the two functions.
SUPABASE_URL = "https://tlpkfflnyfmkhakhuqrw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRscGtmZmxueWZta2hha2h1cXJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEyMDU3MTQsImV4cCI6MjA5Njc4MTcxNH0.H_yEouxIl8WlTwJNRih2cZSZx5d2XQfbBztXvmHdA5c"

_TIMEOUT_S = 10.0


class ShareApiError(Exception):
    """Base for everything the share backend can throw at us."""


class ShareNotConfiguredError(ShareApiError):
    """URL/key constants are empty - online sharing is off."""


class ShareConnectionError(ShareApiError):
    """Network-level failure (DNS, timeout, refused...)."""


class ShareNotFoundError(ShareApiError):
    """No share behind that code (unknown or expired)."""


class ShareRejectedError(ShareApiError):
    """The server said no (validation, size limit, rate limit)."""


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def create_share(
    game: str,
    profile_name: str,
    payload: dict,
    *,
    client: httpx.Client | None = None,
) -> str:
    """Upload a ModShare payload, return the 6-char code."""
    body = {"p_game": game, "p_profile_name": profile_name, "p_payload": payload}
    result = _rpc("create_share", body, client)
    if not isinstance(result, str) or not result:
        raise ShareRejectedError(f"unexpected create_share result: {result!r}")
    return result


def fetch_share(code: str, *, client: httpx.Client | None = None) -> dict:
    """Fetch the payload behind ``code``. Raises ShareNotFoundError if gone."""
    result = _rpc("get_share", {"p_code": code}, client)
    if not isinstance(result, dict):
        raise ShareNotFoundError(code)
    return result


def _rpc(name: str, body: dict, client: httpx.Client | None) -> object:
    if not is_configured():
        raise ShareNotConfiguredError()
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    own = client or httpx.Client(timeout=_TIMEOUT_S)
    try:
        response = own.post(f"{SUPABASE_URL}/rest/v1/rpc/{name}", json=body, headers=headers)
        if response.status_code != 200:
            raise ShareRejectedError(
                f"{name} -> HTTP {response.status_code}: {response.text[:200]}"
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ShareRejectedError(f"{name}: non-JSON response body") from exc
    except httpx.HTTPError as exc:
        log.debug("share rpc %s failed: %s", name, exc)
        raise ShareConnectionError(str(exc)) from exc
    finally:
        if client is None:
            own.close()
