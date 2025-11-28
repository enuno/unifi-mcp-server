"""Unit tests for port forwarding tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.port_forwarding import (
    create_port_forward,
    delete_port_forward,
    list_port_forwards,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_port_forward_data():
    """Sample port forward rule for testing."""
    return {
        "_id": "507f1f77bcf86cd799439012",
        "name": "SSH Forward",
        "dst_port": "22",
        "fwd": "192.168.1.100",
        "fwd_port": "22",
        "proto": "tcp",
        "src": "any",
        "enabled": True,
        "log": False,
    }


@pytest.fixture
def sample_port_forwards_list(sample_port_forward_data):
    """Sample port forwards list for testing."""
    return [
        sample_port_forward_data,
        {
            "_id": "507f1f77bcf86cd799439013",
            "name": "HTTP Forward",
            "dst_port": "80",
            "fwd": "192.168.1.50",
            "fwd_port": "8080",
            "proto": "tcp",
            "src": "any",
            "enabled": True,
            "log": True,
        },
        {
            "_id": "507f1f77bcf86cd799439014",
            "name": "Game Server",
            "dst_port": "25565",
            "fwd": "192.168.1.200",
            "fwd_port": "25565",
            "proto": "tcp_udp",
            "src": "0.0.0.0/0",
            "enabled": False,
            "log": False,
        },
    ]


# ============================================================================
# Test: list_port_forwards - List Port Forwarding Rules
# ============================================================================


@pytest.mark.asyncio
async def test_list_port_forwards_success(
    settings: Settings, sample_port_forwards_list: list
) -> None:
    """Test listing port forwards successfully."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_port_forwards_list}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_port_forwards("site-123", settings)

        assert len(result) == 3
        assert result[0]["name"] == "SSH Forward"
        assert result[1]["name"] == "HTTP Forward"
        mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_list_port_forwards_pagination(
    settings: Settings, sample_port_forwards_list: list
) -> None:
    """Test listing port forwards with limit and offset."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_port_forwards_list}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        # Test limit
        result = await list_port_forwards("site-123", settings, limit=2)
        assert len(result) == 2

        # Test offset
        result = await list_port_forwards("site-123", settings, offset=1, limit=2)
        assert len(result) == 2
        assert result[0]["name"] == "HTTP Forward"  # Second item after offset


# ============================================================================
# Test: create_port_forward - Port Forward Rule Creation
# ============================================================================


@pytest.mark.asyncio
async def test_create_port_forward_success_tcp(
    settings: Settings, sample_port_forward_data: dict
) -> None:
    """Test creating a TCP port forward successfully."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {"data": [sample_port_forward_data]}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_port_forward(
            "site-123",
            "SSH Forward",
            22,
            "192.168.1.100",
            22,
            settings,
            protocol="tcp",
            confirm=True,
        )

        assert result["_id"] == "507f1f77bcf86cd799439012"
        assert result["name"] == "SSH Forward"
        assert result["dst_port"] == "22"
        assert result["fwd"] == "192.168.1.100"
        assert result["proto"] == "tcp"

        # Verify payload
        call_args = mock_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "SSH Forward"
        assert json_data["dst_port"] == "22"  # Converted to string
        assert json_data["fwd"] == "192.168.1.100"
        assert json_data["fwd_port"] == "22"  # Converted to string
        assert json_data["proto"] == "tcp"


@pytest.mark.asyncio
async def test_create_port_forward_success_udp(settings: Settings) -> None:
    """Test creating a UDP port forward successfully."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {
            "data": [
                {
                    "_id": "507f1f77bcf86cd799439015",
                    "name": "DNS Forward",
                    "dst_port": "53",
                    "fwd": "192.168.1.10",
                    "fwd_port": "53",
                    "proto": "udp",
                    "src": "any",
                    "enabled": True,
                }
            ]
        }
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_port_forward(
            "site-123",
            "DNS Forward",
            53,
            "192.168.1.10",
            53,
            settings,
            protocol="udp",
            confirm=True,
        )

        assert result["proto"] == "udp"
        assert result["name"] == "DNS Forward"


@pytest.mark.asyncio
async def test_create_port_forward_success_tcp_udp(settings: Settings) -> None:
    """Test creating a TCP+UDP port forward successfully."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {
            "data": [
                {
                    "_id": "507f1f77bcf86cd799439016",
                    "name": "Game Server",
                    "dst_port": "25565",
                    "fwd": "192.168.1.200",
                    "fwd_port": "25565",
                    "proto": "tcp_udp",
                    "src": "any",
                    "enabled": True,
                }
            ]
        }
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_port_forward(
            "site-123",
            "Game Server",
            25565,
            "192.168.1.200",
            25565,
            settings,
            protocol="tcp_udp",
            confirm=True,
        )

        assert result["proto"] == "tcp_udp"


@pytest.mark.asyncio
async def test_create_port_forward_with_source_ip(settings: Settings) -> None:
    """Test creating port forward with source IP restriction."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {
            "data": [
                {
                    "_id": "507f1f77bcf86cd799439017",
                    "name": "Restricted SSH",
                    "dst_port": "22",
                    "fwd": "192.168.1.100",
                    "fwd_port": "22",
                    "proto": "tcp",
                    "src": "203.0.113.0/24",
                    "enabled": True,
                }
            ]
        }
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_port_forward(
            "site-123",
            "Restricted SSH",
            22,
            "192.168.1.100",
            22,
            settings,
            src="203.0.113.0/24",  # CIDR notation
            confirm=True,
        )

        assert result["src"] == "203.0.113.0/24"

        # Verify payload
        call_args = mock_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["src"] == "203.0.113.0/24"


@pytest.mark.asyncio
async def test_create_port_forward_invalid_dst_port_zero(settings: Settings) -> None:
    """Test creating port forward with invalid destination port (0)."""
    with pytest.raises(ValidationError, match="Invalid port"):
        await create_port_forward(
            "site-123",
            "Invalid Port",
            0,  # Invalid: must be 1-65535
            "192.168.1.100",
            22,
            settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_port_forward_invalid_dst_port_too_high(
    settings: Settings,
) -> None:
    """Test creating port forward with destination port > 65535."""
    with pytest.raises(ValidationError, match="Invalid port"):
        await create_port_forward(
            "site-123",
            "Invalid Port",
            65536,  # Invalid: must be <= 65535
            "192.168.1.100",
            22,
            settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_port_forward_invalid_fwd_port(settings: Settings) -> None:
    """Test creating port forward with invalid forward port."""
    with pytest.raises(ValidationError, match="Invalid port"):
        await create_port_forward(
            "site-123",
            "Invalid Forward Port",
            22,
            "192.168.1.100",
            -1,  # Invalid: must be positive
            settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_port_forward_invalid_ip(settings: Settings) -> None:
    """Test creating port forward with invalid IP address."""
    with pytest.raises(ValidationError, match="Invalid IP"):
        await create_port_forward(
            "site-123",
            "Invalid IP",
            22,
            "999.999.999.999",  # Invalid IP address
            22,
            settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_port_forward_invalid_protocol(settings: Settings) -> None:
    """Test creating port forward with invalid protocol."""
    with pytest.raises(ValidationError, match="Invalid protocol"):
        await create_port_forward(
            "site-123",
            "Invalid Protocol",
            22,
            "192.168.1.100",
            22,
            settings,
            protocol="invalid",  # Must be: tcp, udp, tcp_udp
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_port_forward_dry_run(settings: Settings) -> None:
    """Test creating port forward in dry-run mode."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_port_forward(
            "site-123",
            "Test Forward",
            80,
            "192.168.1.50",
            8080,
            settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert "would_create" in result
        assert result["would_create"]["name"] == "Test Forward"
        assert result["would_create"]["dst_port"] == "80"
        assert result["would_create"]["fwd"] == "192.168.1.50"

        # Verify no API call was made
        mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_port_forward_without_confirmation(settings: Settings) -> None:
    """Test that port forward creation requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await create_port_forward(
            "site-123",
            "Test Forward",
            80,
            "192.168.1.50",
            8080,
            settings,
            confirm=False,  # Must be True
        )


@pytest.mark.asyncio
async def test_create_port_forward_with_logging(settings: Settings) -> None:
    """Test creating port forward with logging enabled."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {
            "data": [
                {
                    "_id": "507f1f77bcf86cd799439018",
                    "name": "Logged Forward",
                    "dst_port": "443",
                    "fwd": "192.168.1.50",
                    "fwd_port": "443",
                    "proto": "tcp",
                    "src": "any",
                    "enabled": True,
                    "log": True,
                }
            ]
        }
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_port_forward(
            "site-123",
            "Logged Forward",
            443,
            "192.168.1.50",
            443,
            settings,
            log=True,
            confirm=True,
        )

        assert result["log"] is True

        # Verify payload
        call_args = mock_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["log"] is True


# ============================================================================
# Test: delete_port_forward - Port Forward Rule Deletion
# ============================================================================


@pytest.mark.asyncio
async def test_delete_port_forward_success(
    settings: Settings, sample_port_forwards_list: list
) -> None:
    """Test deleting a port forward rule successfully."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_port_forwards_list}
        mock_client.delete.return_value = {"success": True}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await delete_port_forward(
            "site-123", "507f1f77bcf86cd799439012", settings, confirm=True
        )

        assert result["success"] is True
        assert result["deleted_rule_id"] == "507f1f77bcf86cd799439012"
        mock_client.get.assert_called_once()
        mock_client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_port_forward_not_found(settings: Settings) -> None:
    """Test deleting non-existent port forward rule."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": []}  # No rules
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await delete_port_forward(
                "site-123", "nonexistent-rule-id", settings, confirm=True
            )


@pytest.mark.asyncio
async def test_delete_port_forward_dry_run(settings: Settings) -> None:
    """Test deleting port forward in dry-run mode."""
    with patch("src.tools.port_forwarding.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await delete_port_forward(
            "site-123",
            "507f1f77bcf86cd799439012",
            settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_delete"] == "507f1f77bcf86cd799439012"

        # Verify no API calls were made
        mock_client.get.assert_not_called()
        mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_port_forward_without_confirmation(settings: Settings) -> None:
    """Test that port forward deletion requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await delete_port_forward(
            "site-123",
            "507f1f77bcf86cd799439012",
            settings,
            confirm=False,  # Must be True
        )
