"""Mock-based unit tests for the service -> external arXiv API boundary."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.services import arxiv_fetch
from app.services.arxiv_fetch import ArxivFetchError, fetch_arxiv_papers


ATOM_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <title>Mocking External API Boundaries</title>
    <summary>A deterministic service-layer unit test.</summary>
    <published>2024-01-03T23:45:00Z</published>
    <updated>2024-02-04T10:30:00Z</updated>
    <author><name>Ada Lovelace</name></author>
    <category term="cs.SE"/>
    <link title="abstract" href="https://arxiv.org/abs/2401.01234"/>
    <link title="pdf" href="https://arxiv.org/pdf/2401.01234"/>
  </entry>
</feed>
"""


@asynccontextmanager
async def _no_rate_limit():
    """Replace Redis/local rate limiting so the unit test has no infrastructure dependency."""
    yield


def _response(*, status_code: int, text: str) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = text
    return response


@pytest.mark.asyncio
async def test_fetch_service_uses_mock_http_client_and_parses_atom_response() -> None:
    """The service sends the expected request and converts the mocked response."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(status_code=200, text=ATOM_RESPONSE)

    with patch.object(arxiv_fetch, "_global_request_slot", _no_rate_limit):
        papers = await fetch_arxiv_papers(
            'all:"mock testing"',
            max_results=250,
            start=-3,
            client=client,
        )

    assert papers[0]["arxiv_id"] == "2401.01234"
    assert papers[0]["title"] == "Mocking External API Boundaries"
    assert papers[0]["authors"] == ["Ada Lovelace"]

    client.get.assert_awaited_once()
    request_url = client.get.await_args.args[0]
    query = parse_qs(urlparse(request_url).query)
    assert query["search_query"] == ['all:"mock testing"']
    assert query["start"] == ["0"]
    assert query["max_results"] == ["100"]
    assert client.get.await_args.kwargs["headers"]["Accept"] == "application/atom+xml"
    client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_service_maps_mocked_429_to_retryable_domain_error() -> None:
    """HTTP details are translated into a retryable service-layer exception."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(status_code=429, text="rate limited")

    with (
        patch.object(arxiv_fetch, "_global_request_slot", _no_rate_limit),
        pytest.raises(ArxivFetchError) as captured,
    ):
        await fetch_arxiv_papers("cat:cs.SE", client=client)

    assert captured.value.retryable is True
    assert captured.value.status_code == 429
    client.get.assert_awaited_once()
    client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_service_rejects_invalid_xml_from_mock_client() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(status_code=200, text="<not-valid-xml")

    with (
        patch.object(arxiv_fetch, "_global_request_slot", _no_rate_limit),
        pytest.raises(ArxivFetchError, match="invalid XML") as captured,
    ):
        await fetch_arxiv_papers("cat:cs.AI", client=client)

    assert captured.value.retryable is True
    client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_service_maps_mock_timeout_without_network_access() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.ReadTimeout("mock timeout")

    with (
        patch.object(arxiv_fetch, "_global_request_slot", _no_rate_limit),
        pytest.raises(ArxivFetchError, match="timed out") as captured,
    ):
        await fetch_arxiv_papers("cat:cs.CL", client=client)

    assert captured.value.retryable is True
    client.get.assert_awaited_once()
    client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_service_maps_mocked_404_to_non_retryable_domain_error() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(status_code=404, text="not found")

    with (
        patch.object(arxiv_fetch, "_global_request_slot", _no_rate_limit),
        pytest.raises(ArxivFetchError) as captured,
    ):
        await fetch_arxiv_papers("id:missing", client=client)

    assert captured.value.retryable is False
    assert captured.value.status_code == 404
    client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_service_maps_mock_http_transport_error() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.ConnectError("mock connection failure")

    with (
        patch.object(arxiv_fetch, "_global_request_slot", _no_rate_limit),
        pytest.raises(ArxivFetchError, match="request failed") as captured,
    ):
        await fetch_arxiv_papers("cat:cs.IR", client=client)

    assert captured.value.retryable is True
    client.get.assert_awaited_once()
    client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_service_closes_internally_created_mock_client() -> None:
    """Resource ownership remains in the service when the client is not injected."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(
        status_code=200,
        text='<feed xmlns="http://www.w3.org/2005/Atom"/>',
    )

    with (
        patch.object(arxiv_fetch, "_global_request_slot", _no_rate_limit),
        patch.object(arxiv_fetch.settings, "arxiv_contact_email", "teacher@example.com"),
        patch.object(arxiv_fetch.httpx, "AsyncClient", return_value=client) as client_factory,
    ):
        papers = await fetch_arxiv_papers("cat:cs.SE")

    assert papers == []
    client_factory.assert_called_once()
    client.get.assert_awaited_once()
    assert client.get.await_args.kwargs["headers"]["From"] == "teacher@example.com"
    client.aclose.assert_awaited_once()
