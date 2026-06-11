"""Talks to the ModShare Supabase backend.

All access goes through two RPCs (see packaging/supabase.sql); there is no
direct table access, so the publishable key in this file cannot be used to
enumerate or modify other people's shares. The constants stay empty until
the Supabase project exists - sharing is then reported as not configured
and the UI offers only the file-based paths.
"""

from __future__ import annotations

import httpx

# Fill in once the Supabase project is set up (see packaging/supabase.sql).
SUPABASE_URL = ""
SUPABASE_KEY = ""

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
    except httpx.HTTPError as exc:
        raise ShareConnectionError(str(exc)) from exc
    finally:
        if client is None:
            own.close()
    if response.status_code != 200:
        raise ShareRejectedError(f"{name} -> HTTP {response.status_code}: {response.text[:200]}")
    if not response.content:
        return None
    return response.json()
