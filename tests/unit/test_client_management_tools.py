"""Unit tests for client management tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.client_management import (
    authorize_guest,
    block_client,
    limit_bandwidth,
    reconnect_client,
    unblock_client,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_clients_data():
    """Sample clients for testing."""
    return [
        {
            "mac": "00:11:22:33:44:55",
            "name": "Laptop-001",
            "ip": "192.168.1.100",
            "is_wired": False,
            "is_guest": False,
        },
        {
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "Phone-001",
            "ip": "192.168.1.101",
            "is_wired": False,
            "is_guest": True,
        },
    ]


@pytest.fixture
def sample_success_response():
    """Sample success response."""
    return {"success": True}


# ============================================================================
# Test: block_client - Client Blocking
# ============================================================================


@pytest.mark.asyncio
async def test_block_client_success(
    settings: Settings, sample_clients_data: list, sample_success_response: dict
) -> None:
    """Test blocking a client successfully."""
    with patch("src.tools.client_management.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_clients_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await block_client("site-123", "00:11:22:33:44:55", settings, confirm=True)

        assert result["success"] is True
        assert result["client_mac"] == "00:11:22:33:44:55"
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_block_client_without_confirmation(settings: Settings) -> None:
    """Test that blocking requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await block_client("site-123", "00:11:22:33:44:55", settings, confirm=False)


@pytest.mark.asyncio
async def test_block_client_dry_run(settings: Settings) -> None:
    """Test blocking client in dry-run mode."""
    result = await block_client("site-123", "00:11:22:33:44:55", settings, confirm=True, dry_run=True)

    assert result["dry_run"] is True
    assert result["would_block"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_block_client_not_found(settings: Settings) -> None:
    """Test blocking non-existent client."""
    with patch("src.tools.client_management.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = []
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await block_client("site-123", "99:99:99:99:99:99", settings, confirm=True)


@pytest.mark.asyncio
async def test_block_client_invalid_mac(settings: Settings) -> None:
    """Test blocking with invalid MAC address."""
    with pytest.raises(ValidationError, match="Invalid MAC address"):
        await block_client("site-123", "invalid-mac", settings, confirm=True)


# ============================================================================
# Test: unblock_client - Client Unblocking
# ============================================================================


@pytest.mark.asyncio
async def test_unblock_client_success(
    settings: Settings, sample_clients_data: list, sample_success_response: dict
) -> None:
    """Test unblocking a client successfully."""
    with patch("src.tools.client_management.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_clients_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await unblock_client("site-123", "00:11:22:33:44:55", settings, confirm=True)

        assert result["success"] is True
        assert result["client_mac"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_unblock_client_without_confirmation(settings: Settings) -> None:
    """Test that unblocking requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await unblock_client("site-123", "00:11:22:33:44:55", settings, confirm=False)


@pytest.mark.asyncio
async def test_unblock_client_dry_run(settings: Settings) -> None:
    """Test unblocking client in dry-run mode."""
    result = await unblock_client("site-123", "00:11:22:33:44:55", settings, confirm=True, dry_run=True)

    assert result["dry_run"] is True
    assert result["would_unblock"] == "00:11:22:33:44:55"


# ============================================================================
# Test: reconnect_client - Client Reconnection
# ============================================================================


@pytest.mark.asyncio
async def test_reconnect_client_success(
    settings: Settings, sample_clients_data: list, sample_success_response: dict
) -> None:
    """Test reconnecting a client successfully."""
    with patch("src.tools.client_management.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_clients_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await reconnect_client("site-123", "00:11:22:33:44:55", settings, confirm=True)

        assert result["success"] is True
        assert result["client_mac"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_reconnect_client_without_confirmation(settings: Settings) -> None:
    """Test that reconnecting requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await reconnect_client("site-123", "00:11:22:33:44:55", settings, confirm=False)


@pytest.mark.asyncio
async def test_reconnect_client_dry_run(settings: Settings) -> None:
    """Test reconnecting client in dry-run mode."""
    result = await reconnect_client("site-123", "00:11:22:33:44:55", settings, confirm=True, dry_run=True)

    assert result["dry_run"] is True
    assert result["would_reconnect"] == "00:11:22:33:44:55"


# ============================================================================
# Test: authorize_guest - Guest Authorization
# ============================================================================


@pytest.mark.asyncio
async def test_authorize_guest_success(
    settings: Settings, sample_clients_data: list, sample_success_response: dict
) -> None:
    """Test authorizing a guest successfully."""
    with patch("src.tools.client_management.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_clients_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await authorize_guest(
            "site-123",
            "aa:bb:cc:dd:ee:ff",
            3600,  # duration in seconds (60 minutes)
            settings,
            confirm=True,
        )

        assert result["success"] is True
        assert result["client_mac"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_authorize_guest_without_confirmation(settings: Settings) -> None:
    """Test that guest authorization requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await authorize_guest("site-123", "aa:bb:cc:dd:ee:ff", 3600, settings, confirm=False)


@pytest.mark.asyncio
async def test_authorize_guest_dry_run(settings: Settings) -> None:
    """Test authorizing guest in dry-run mode."""
    result = await authorize_guest(
        "site-123",
        "aa:bb:cc:dd:ee:ff",
        7200,  # duration in seconds (120 minutes)
        settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_authorize"] == "aa:bb:cc:dd:ee:ff"
    assert result["duration"] == 7200


# ============================================================================
# Test: limit_bandwidth - Bandwidth Limiting
# ============================================================================


@pytest.mark.asyncio
async def test_limit_bandwidth_success(
    settings: Settings, sample_clients_data: list, sample_success_response: dict
) -> None:
    """Test limiting client bandwidth successfully."""
    with patch("src.tools.client_management.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_clients_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await limit_bandwidth(
            "site-123",
            "00:11:22:33:44:55",
            settings,
            download_limit_kbps=5000,
            upload_limit_kbps=1000,
            confirm=True,
        )

        assert result["success"] is True
        assert result["client_mac"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_limit_bandwidth_without_confirmation(settings: Settings) -> None:
    """Test that bandwidth limiting requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await limit_bandwidth(
            "site-123",
            "00:11:22:33:44:55",
            settings,
            download_limit_kbps=5000,
            confirm=False,
        )


@pytest.mark.asyncio
async def test_limit_bandwidth_dry_run(settings: Settings) -> None:
    """Test bandwidth limiting in dry-run mode."""
    result = await limit_bandwidth(
        "site-123",
        "00:11:22:33:44:55",
        settings,
        download_limit_kbps=10000,
        upload_limit_kbps=2000,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_limit"] == "00:11:22:33:44:55"
    assert result["download_limit_kbps"] == 10000
    assert result["upload_limit_kbps"] == 2000


@pytest.mark.asyncio
async def test_limit_bandwidth_invalid_values(settings: Settings) -> None:
    """Test bandwidth limiting with invalid values."""
    with pytest.raises(ValueError, match="must be positive"):
        await limit_bandwidth(
            "site-123",
            "00:11:22:33:44:55",
            settings,
            download_limit_kbps=-1000,
            confirm=True,
        )
