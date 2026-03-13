"""Unit tests for ISAPIClient detection config methods and retry logic."""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.isapi.client import ISAPIClient


MINIMAL_XML = "<MotionDetection><enabled>true</enabled></MotionDetection>"


@pytest.fixture
def client() -> ISAPIClient:
    return ISAPIClient(host="192.168.1.1", port=80, username="admin", password="pass")


# ---------------------------------------------------------------------------
# get_detection_config — success
# ---------------------------------------------------------------------------


async def test_get_detection_config_success_returns_xml(client: ISAPIClient) -> None:
    """GET detection config returns the raw XML string on 200."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = MINIMAL_XML
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await client.get_detection_config(1, "MotionDetection")

    assert result == MINIMAL_XML
    mock_http_client.get.assert_called_once_with(
        "http://192.168.1.1:80/ISAPI/Smart/MotionDetection/channels/1"
    )


# ---------------------------------------------------------------------------
# put_detection_config — success
# ---------------------------------------------------------------------------


async def test_put_detection_config_success_returns_none(client: ISAPIClient) -> None:
    """PUT detection config returns None on 200."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.put = AsyncMock(return_value=mock_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await client.put_detection_config(1, "MotionDetection", MINIMAL_XML)

    assert result is None
    mock_http_client.put.assert_called_once_with(
        "http://192.168.1.1:80/ISAPI/Smart/MotionDetection/channels/1",
        headers={"Content-Type": "text/xml"},
        content=MINIMAL_XML.encode(),
    )


# ---------------------------------------------------------------------------
# Retry logic — GET
# ---------------------------------------------------------------------------


async def test_get_detection_config_timeout_retries_once_then_raises(
    client: ISAPIClient,
) -> None:
    """GET: first TimeoutException triggers one retry; second raises."""
    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with pytest.raises(httpx.TimeoutException):
            await client.get_detection_config(1, "MotionDetection")

    assert mock_http_client.get.call_count == 2


async def test_get_detection_config_first_timeout_second_success(
    client: ISAPIClient,
) -> None:
    """GET: first TimeoutException triggers retry; second call succeeds."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = MINIMAL_XML
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(
        side_effect=[httpx.TimeoutException("timeout"), mock_response]
    )
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await client.get_detection_config(1, "MotionDetection")

    assert result == MINIMAL_XML
    assert mock_http_client.get.call_count == 2


async def test_get_detection_config_non_timeout_error_raises_immediately(
    client: ISAPIClient,
) -> None:
    """GET: non-timeout HTTP error (404) raises immediately — no retry."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response,
        )
    )

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_detection_config(1, "MotionDetection")

    assert mock_http_client.get.call_count == 1


# ---------------------------------------------------------------------------
# Retry logic — PUT
# ---------------------------------------------------------------------------


async def test_put_detection_config_timeout_retries_once_then_raises(
    client: ISAPIClient,
) -> None:
    """PUT: first TimeoutException triggers one retry; second raises."""
    mock_http_client = AsyncMock()
    mock_http_client.put = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with pytest.raises(httpx.TimeoutException):
            await client.put_detection_config(1, "MotionDetection", MINIMAL_XML)

    assert mock_http_client.put.call_count == 2


# ---------------------------------------------------------------------------
# URL pattern — all detection types
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Gap 1: ISAPI-01 + ISAPI-04 — DigestAuth instance and verify=False
# ---------------------------------------------------------------------------


def test_client_uses_digest_auth_and_no_tls_verify() -> None:
    """ISAPIClient uses DigestAuth and disables TLS verification for self-signed NVR certs."""
    isapi_client = ISAPIClient(host="192.168.1.1", port=80, username="admin", password="secret")

    assert isinstance(isapi_client._auth, httpx.DigestAuth)
    assert isapi_client._client_kwargs["verify"] is False
    assert isapi_client._client_kwargs["auth"] is isapi_client._auth


# ---------------------------------------------------------------------------
# Gap 2: ISAPI-02 — Timeout settings
# ---------------------------------------------------------------------------


def test_client_timeout_settings() -> None:
    """ISAPIClient configures Timeout with connect=5.0 and read=10.0."""
    isapi_client = ISAPIClient(host="192.168.1.1", port=80, username="admin", password="secret")

    timeout = isapi_client._client_kwargs["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 5.0
    assert timeout.read == 10.0


# ---------------------------------------------------------------------------
# Gap 3: ISAPI-03/PUT — non-timeout error raises immediately without retry
# ---------------------------------------------------------------------------


async def test_put_detection_config_non_timeout_error_raises_immediately(
    client: ISAPIClient,
) -> None:
    """PUT: non-timeout HTTP error (404) raises immediately — no retry."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response,
        )
    )

    mock_http_client = AsyncMock()
    mock_http_client.put = AsyncMock(return_value=mock_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with pytest.raises(httpx.HTTPStatusError):
            await client.put_detection_config(1, "MotionDetection", MINIMAL_XML)

    assert mock_http_client.put.call_count == 1


# ---------------------------------------------------------------------------
# URL pattern — all detection types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "detection_type",
    ["MotionDetection", "LineDetection", "FieldDetection", "shelteralarm"],
)
async def test_detection_url_pattern(
    client: ISAPIClient, detection_type: str
) -> None:
    """URL is built as /ISAPI/Smart/{detection_type}/channels/{channel_no}."""
    expected_url = (
        f"http://192.168.1.1:80/ISAPI/Smart/{detection_type}/channels/3"
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = MINIMAL_XML
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        await client.get_detection_config(3, detection_type)

    mock_http_client.get.assert_called_once_with(expected_url)
