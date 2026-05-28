from __future__ import annotations

import httpx

from easy_scsmodmanager.integrations.steam.workshop_api import (
    WorkshopItem,
    fetch_metadata,
    fetch_preview_image,
)


def _make_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_fetch_metadata_returns_empty_dict_for_empty_input() -> None:
    # Should not even hit the network.
    result = fetch_metadata([])
    assert result == {}


def test_fetch_metadata_parses_steam_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "publishedfileids%5B0%5D=12345" in request.content.decode()
        return httpx.Response(
            200,
            json={
                "response": {
                    "publishedfiledetails": [
                        {
                            "publishedfileid": "12345",
                            "result": 1,
                            "title": "Real Truck Sounds",
                            "description": "Sounds for trucks",
                            "preview_url": "https://example.com/preview.jpg",
                            "time_updated": 1700000000,
                            "creator": "76561198000000000",
                            "file_size": 1234567,
                        },
                    ]
                }
            },
        )

    client = _make_client(handler)
    result = fetch_metadata(["12345"], client=client)

    assert result == {
        "12345": WorkshopItem(
            workshop_id="12345",
            title="Real Truck Sounds",
            description="Sounds for trucks",
            preview_url="https://example.com/preview.jpg",
            time_updated=1700000000,
            creator="76561198000000000",
            file_size=1234567,
        )
    }


def test_fetch_metadata_skips_entries_with_non_ok_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": {
                    "publishedfiledetails": [
                        {"publishedfileid": "1", "result": 1, "title": "Visible"},
                        {"publishedfileid": "2", "result": 9, "title": "Removed"},
                    ]
                }
            },
        )

    client = _make_client(handler)
    result = fetch_metadata(["1", "2"], client=client)

    assert set(result.keys()) == {"1"}


def test_fetch_metadata_batches_large_inputs() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        count = int(body.split("itemcount=")[1].split("&")[0])
        calls.append(count)
        return httpx.Response(200, json={"response": {"publishedfiledetails": []}})

    client = _make_client(handler)
    ids = [str(n) for n in range(120)]  # 120 -> 50 + 50 + 20
    fetch_metadata(ids, client=client)

    assert calls == [50, 50, 20]


def test_fetch_metadata_returns_empty_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = _make_client(handler)
    result = fetch_metadata(["1"], client=client)

    assert result == {}


def test_fetch_preview_image_returns_bytes_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\xff\xd8\xff\xe0fake-jpeg")

    client = _make_client(handler)
    payload = fetch_preview_image("https://example.com/x.jpg", client=client)

    assert payload == b"\xff\xd8\xff\xe0fake-jpeg"


def test_fetch_preview_image_returns_none_on_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = _make_client(handler)
    payload = fetch_preview_image("https://example.com/x.jpg", client=client)

    assert payload is None
