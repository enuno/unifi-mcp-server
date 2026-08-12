"""Unit tests for application tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.application as app_module
from src.tools.application import get_application_info


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    settings.get_integration_path = MagicMock(side_effect=lambda x: f"/integration/v1/{x}")
    return settings


def _make_client(response, authenticated=True):
    client = MagicMock()
    client.is_authenticated = authenticated
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# =============================================================================
# get_application_info Tests
#
# The documented route is /v1/info and the documented response is a single
# key: {"applicationVersion": "9.1.0"}. See issue #108 — the previous
# /application/info path 404s everywhere, and the version/build/capabilities
# shape it parsed came from nowhere real.
# =============================================================================


@pytest.mark.asyncio
async def test_get_application_info_documented_payload(mock_settings):
    """The documented single-key response resolves on the documented path."""
    mock_client = _make_client({"applicationVersion": "9.1.0"})

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    assert result["application_version"] == "9.1.0"
    mock_client.get.assert_called_once_with("/integration/v1/info")


@pytest.mark.asyncio
async def test_get_application_info_data_wrapped(mock_settings):
    """A data-wrapped variant of the same payload also resolves."""
    mock_client = _make_client({"data": {"applicationVersion": "9.2.5"}})

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    assert result["application_version"] == "9.2.5"


@pytest.mark.asyncio
async def test_get_application_info_unauthenticated(mock_settings):
    """An unauthenticated client authenticates before the request."""
    mock_client = _make_client({"applicationVersion": "9.1.0"}, authenticated=False)

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    mock_client.authenticate.assert_called_once()
    assert result["application_version"] == "9.1.0"


@pytest.mark.asyncio
async def test_get_application_info_passes_extra_keys_through(mock_settings):
    """Undocumented keys a controller chooses to send are not dropped."""
    mock_client = _make_client({"applicationVersion": "9.3.0", "deploymentType": "console"})

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    assert result["application_version"] == "9.3.0"
    assert result["deploymentType"] == "console"


@pytest.mark.asyncio
async def test_get_application_info_empty_response(mock_settings):
    """An empty reply reports the promised key as None rather than raising."""
    mock_client = _make_client({})

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    assert result == {"application_version": None}
