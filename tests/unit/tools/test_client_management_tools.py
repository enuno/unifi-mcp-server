"""Unit tests for client management tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.client_management as cm_module
from src.tools.client_management import (
    authorize_guest,
    block_client,
    limit_bandwidth,
    reconnect_client,
    unblock_client,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError


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
    return settings


# =============================================================================
# block_client Tests
# =============================================================================


@pytest.mark.asyncio
async def test_block_client_success(mock_settings):
    """Test successful client blocking."""
    mock_clients_response = {
        "data": [
            {
                "_id": "client1",
                "mac": "00:11:22:33:44:55",
                "hostname": "Test Client",
            }
        ]
    }
    mock_block_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_clients_response)
    mock_client.post = AsyncMock(return_value=mock_block_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await block_client(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["client_mac"] == "00:11:22:33:44:55"
    assert result["message"] == "Client blocked from network"
    mock_client.post.assert_called_once()

    # Verify the correct command was sent
    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["cmd"] == "block-sta"
    assert json_data["mac"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_block_client_dry_run(mock_settings):
    """Test client blocking dry run."""
    result = await block_client(
        site_id="default",
        client_mac="00:11:22:33:44:55",
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_block"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_block_client_no_confirm(mock_settings):
    """Test client blocking fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await block_client(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_block_client_not_found(mock_settings):
    """Test blocking a non-existent client."""
    mock_clients_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_clients_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await block_client(
                site_id="default",
                client_mac="aa:bb:cc:dd:ee:ff",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_block_client_invalid_mac(mock_settings):
    """Test client blocking with invalid MAC address."""
    with pytest.raises(ValidationError) as excinfo:
        await block_client(
            site_id="default",
            client_mac="invalid-mac",
            settings=mock_settings,
            confirm=True,
        )

    assert "mac" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()


# =============================================================================
# unblock_client Tests
# =============================================================================


@pytest.mark.asyncio
async def test_unblock_client_success(mock_settings):
    """Test successful client unblocking."""
    mock_unblock_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_unblock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await unblock_client(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["client_mac"] == "00:11:22:33:44:55"
    assert result["message"] == "Client unblocked"
    mock_client.post.assert_called_once()

    # Verify the correct command was sent
    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["cmd"] == "unblock-sta"
    assert json_data["mac"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_unblock_client_dry_run(mock_settings):
    """Test client unblocking dry run."""
    result = await unblock_client(
        site_id="default",
        client_mac="00:11:22:33:44:55",
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_unblock"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_unblock_client_no_confirm(mock_settings):
    """Test client unblocking fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await unblock_client(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


# =============================================================================
# reconnect_client Tests
# =============================================================================


@pytest.mark.asyncio
async def test_reconnect_client_success(mock_settings):
    """Test successful client reconnection."""
    mock_clients_response = {
        "data": [
            {
                "_id": "client1",
                "mac": "00:11:22:33:44:55",
                "hostname": "Test Client",
            }
        ]
    }
    mock_reconnect_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_clients_response)
    mock_client.post = AsyncMock(return_value=mock_reconnect_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await reconnect_client(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["client_mac"] == "00:11:22:33:44:55"
    assert result["message"] == "Client forced to reconnect"
    mock_client.post.assert_called_once()

    # Verify the correct command was sent
    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["cmd"] == "kick-sta"
    assert json_data["mac"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_reconnect_client_dry_run(mock_settings):
    """Test client reconnection dry run."""
    result = await reconnect_client(
        site_id="default",
        client_mac="00:11:22:33:44:55",
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_reconnect"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_reconnect_client_no_confirm(mock_settings):
    """Test client reconnection fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await reconnect_client(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_reconnect_client_not_found(mock_settings):
    """Test reconnecting a non-existent client."""
    mock_clients_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_clients_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await reconnect_client(
                site_id="default",
                client_mac="aa:bb:cc:dd:ee:ff",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_reconnect_client_invalid_mac(mock_settings):
    """Test client reconnection with invalid MAC address."""
    with pytest.raises(ValidationError) as excinfo:
        await reconnect_client(
            site_id="default",
            client_mac="invalid-mac",
            settings=mock_settings,
            confirm=True,
        )

    assert "mac" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()


# =============================================================================
# authorize_guest Tests
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_guest_success(mock_settings):
    """Spec shape: AUTHORIZE_GUEST_ACCESS, duration seconds -> timeLimitMinutes."""

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value={"meta": {"rc": "ok"}})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await authorize_guest(
            site_id="default",
            client_id="00:11:22:33:44:55",
            duration=3600,
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["client_id"] == "00:11:22:33:44:55"
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/integration/v1/sites/default/clients/00:11:22:33:44:55/actions"
    assert call_args[1]["json_data"] == {
        "action": "AUTHORIZE_GUEST_ACCESS",
        "timeLimitMinutes": 60,
    }


@pytest.mark.asyncio
async def test_authorize_guest_with_limits(mock_settings):
    """Limits ride at the top level (spec tx/rxRateLimitKbps, dataUsageLimitMBytes)."""

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value={"meta": {"rc": "ok"}})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await authorize_guest(
            site_id="default",
            client_id="00:11:22:33:44:55",
            duration=7200,
            settings=mock_settings,
            upload_limit_kbps=1024,
            download_limit_kbps=2048,
            data_usage_limit_mbytes=512,
            confirm=True,
        )

    assert result["success"] is True
    json_data = mock_client.post.call_args[1]["json_data"]
    assert json_data == {
        "action": "AUTHORIZE_GUEST_ACCESS",
        "timeLimitMinutes": 120,
        "txRateLimitKbps": 1024,
        "rxRateLimitKbps": 2048,
        "dataUsageLimitMBytes": 512,
    }


@pytest.mark.asyncio
async def test_authorize_guest_dry_run(mock_settings):
    """Test guest authorization dry run."""
    result = await authorize_guest(
        site_id="default",
        client_id="00:11:22:33:44:55",
        duration=3600,
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_authorize"] == "00:11:22:33:44:55"
    assert result["duration"] == 3600


@pytest.mark.asyncio
async def test_authorize_guest_no_confirm(mock_settings):
    """Test guest authorization fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await authorize_guest(
            site_id="default",
            client_id="00:11:22:33:44:55",
            duration=3600,
            settings=mock_settings,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_authorize_guest_empty_client_id(mock_settings):
    """client_id must be non-empty (MAC or Integration API UUID accepted)."""
    with pytest.raises(ValueError) as excinfo:
        await authorize_guest(
            site_id="default",
            client_id="   ",
            duration=3600,
            settings=mock_settings,
            confirm=True,
        )

    assert "client_id" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_limit_bandwidth_download_only(mock_settings):
    """No Integration API equivalent - must fail fast with migration guidance."""
    with pytest.raises(NotImplementedError, match="no Integration API"):
        await limit_bandwidth(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            upload_limit_kbps=1024,
            download_limit_kbps=2048,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_limit_bandwidth_both(mock_settings):
    """No Integration API equivalent - must fail fast with migration guidance."""
    with pytest.raises(NotImplementedError, match="no Integration API"):
        await limit_bandwidth(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            upload_limit_kbps=1024,
            download_limit_kbps=2048,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_limit_bandwidth_upload_only(mock_settings):
    """No Integration API equivalent - must fail fast with migration guidance."""
    with pytest.raises(NotImplementedError, match="no Integration API"):
        await limit_bandwidth(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            upload_limit_kbps=1024,
            download_limit_kbps=2048,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_limit_bandwidth_dry_run(mock_settings):
    """Test bandwidth limit dry run."""
    result = await limit_bandwidth(
        site_id="default",
        client_mac="00:11:22:33:44:55",
        settings=mock_settings,
        upload_limit_kbps=1000,
        download_limit_kbps=5000,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_limit"] == "00:11:22:33:44:55"
    assert result["upload_limit_kbps"] == 1000
    assert result["download_limit_kbps"] == 5000


@pytest.mark.asyncio
async def test_limit_bandwidth_no_confirm(mock_settings):
    """Test bandwidth limit fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await limit_bandwidth(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            download_limit_kbps=5000,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_limit_bandwidth_invalid_mac(mock_settings):
    """Test bandwidth limit with invalid MAC address."""
    with pytest.raises(ValidationError) as excinfo:
        await limit_bandwidth(
            site_id="default",
            client_mac="invalid-mac",
            settings=mock_settings,
            download_limit_kbps=5000,
            confirm=True,
        )

    assert "mac" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_limit_bandwidth_invalid_download_limit(mock_settings):
    """Test bandwidth limit with invalid download limit value."""
    with pytest.raises(ValueError) as excinfo:
        await limit_bandwidth(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            download_limit_kbps=-100,
            confirm=True,
        )

    assert "positive" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_limit_bandwidth_invalid_upload_limit(mock_settings):
    """Test bandwidth limit with invalid upload limit value."""
    with pytest.raises(ValueError) as excinfo:
        await limit_bandwidth(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            upload_limit_kbps=0,
            confirm=True,
        )

    assert "positive" in str(excinfo.value).lower()


# =============================================================================
# Edge Cases and Additional Tests
# =============================================================================


@pytest.mark.asyncio
async def test_block_client_list_response(mock_settings):
    """Test blocking client when response is auto-unwrapped list."""
    # Client now auto-unwraps data, so response might be a list directly
    mock_clients_response = [
        {"_id": "client1", "mac": "00:11:22:33:44:55", "hostname": "Test Client"}
    ]
    mock_block_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_clients_response)
    mock_client.post = AsyncMock(return_value=mock_block_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await block_client(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_reconnect_client_list_response(mock_settings):
    """Test reconnecting client when response is auto-unwrapped list."""
    mock_clients_response = [
        {"_id": "client1", "mac": "00:11:22:33:44:55", "hostname": "Test Client"}
    ]
    mock_reconnect_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_clients_response)
    mock_client.post = AsyncMock(return_value=mock_reconnect_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await reconnect_client(
            site_id="default",
            client_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_block_client_multiple_clients(mock_settings):
    """Test blocking finds correct client among multiple."""
    mock_clients_response = {
        "data": [
            {"_id": "client1", "mac": "00:11:22:33:44:55", "hostname": "Client 1"},
            {"_id": "client2", "mac": "aa:bb:cc:dd:ee:ff", "hostname": "Client 2"},
            {"_id": "client3", "mac": "11:22:33:44:55:66", "hostname": "Client 3"},
        ]
    }
    mock_block_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_clients_response)
    mock_client.post = AsyncMock(return_value=mock_block_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await block_client(
            site_id="default",
            client_mac="aa:bb:cc:dd:ee:ff",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["client_mac"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_authorize_guest_minimal(mock_settings):
    """duration=0 omits timeLimitMinutes (controller default applies)."""

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value={"meta": {"rc": "ok"}})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(cm_module, "UniFiClient", return_value=mock_client):
        result = await authorize_guest(
            site_id="default",
            client_id="00:11:22:33:44:55",
            duration=0,
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    json_data = mock_client.post.call_args[1]["json_data"]
    assert json_data == {"action": "AUTHORIZE_GUEST_ACCESS"}

