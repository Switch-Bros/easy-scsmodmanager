"""share_api against a mocked PostgREST endpoint."""

import httpx
import pytest

from easy_scsmodmanager.integrations.supabase import share_api
from easy_scsmodmanager.integrations.supabase.share_api import (
    ShareConnectionError,
    ShareNotConfiguredError,
    ShareNotFoundError,
    ShareRejectedError,
)


@pytest.fixture(autouse=True)
def _configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(share_api, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(share_api, "SUPABASE_KEY", "sb_publishable_test")


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_create_share_returns_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/create_share"
        assert request.headers["apikey"] == "sb_publishable_test"
        return httpx.Response(200, json="AB2CD3")

    code = share_api.create_share("ets2", "Sender", {"mods": []}, client=_client(handler))
    assert code == "AB2CD3"


def test_create_share_rejection_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "payload too large"})

    with pytest.raises(ShareRejectedError):
        share_api.create_share("ets2", "x", {}, client=_client(handler))


def test_fetch_share_returns_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/get_share"
        return httpx.Response(200, json={"format": "easy-scsmodmanager-modshare"})

    payload = share_api.fetch_share("AB2CD3", client=_client(handler))
    assert payload["format"] == "easy-scsmodmanager-modshare"


def test_fetch_share_null_means_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=None)

    with pytest.raises(ShareNotFoundError):
        share_api.fetch_share("AB2CD3", client=_client(handler))


def test_network_error_maps_to_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(ShareConnectionError):
        share_api.fetch_share("AB2CD3", client=_client(handler))


def test_unconfigured_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(share_api, "SUPABASE_URL", "")
    with pytest.raises(ShareNotConfiguredError):
        share_api.fetch_share("AB2CD3")
    assert share_api.is_configured() is False


def test_non_json_body_maps_to_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>gateway error</html>")

    with pytest.raises(ShareRejectedError):
        share_api.fetch_share("AB2CD3", client=_client(handler))
