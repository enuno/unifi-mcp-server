"""Unit tests for port forwarding tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.port_forwarding as pf_module
from src.tools.port_forwarding import create_port_forward, delete_port_forward, list_port_forwards
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
# list_port_forwards Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_port_forwards_success(mock_settings):
    """Test successful port forward listing."""
    mock_response = {
        "data": [
            {
                "_id": "pf1",
                "name": "HTTP",
                "dst_port": "80",
                "fwd": "192.168.2.100",
                "fwd_port": "80",
            },
            {
                "_id": "pf2",
                "name": "SSH",
                "dst_port": "22",
                "fwd": "192.168.2.100",
                "fwd_port": "22",
            },
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        result = await list_port_forwards("default", mock_settings)

    assert len(result) == 2
    assert result[0]["name"] == "HTTP"
    assert result[1]["name"] == "SSH"


@pytest.mark.asyncio
async def test_list_port_forwards_pagination(mock_settings):
    """Test port forward listing with pagination."""
    mock_response = {"data": [{"_id": f"pf{i}", "name": f"Rule {i}"} for i in range(10)]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        result = await list_port_forwards("default", mock_settings, limit=3, offset=2)

    assert len(result) == 3
    assert result[0]["_id"] == "pf2"


@pytest.mark.asyncio
async def test_list_port_forwards_empty(mock_settings):
    """Test port forward listing with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        result = await list_port_forwards("default", mock_settings)

    assert result == []


# =============================================================================
# create_port_forward Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_port_forward_tcp_success(mock_settings):
    """Test successful TCP port forward creation."""
    mock_response = {
        "data": [
            {
                "_id": "new_pf1",
                "name": "Web Server",
                "dst_port": "80",
                "fwd": "192.168.2.100",
                "fwd_port": "80",
                "proto": "tcp",
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        result = await create_port_forward(
            site_id="default",
            name="Web Server",
            dst_port=80,
            fwd_ip="192.168.2.100",
            fwd_port=80,
            settings=mock_settings,
            protocol="tcp",
            confirm=True,
        )

    assert result["_id"] == "new_pf1"
    assert result["name"] == "Web Server"


@pytest.mark.asyncio
async def test_create_port_forward_udp_success(mock_settings):
    """Test successful UDP port forward creation."""
    mock_response = {
        "data": [
            {
                "_id": "new_pf2",
                "name": "Game Server",
                "dst_port": "27015",
                "fwd": "192.168.1.50",
                "fwd_port": "27015",
                "proto": "udp",
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        result = await create_port_forward(
            site_id="default",
            name="Game Server",
            dst_port=27015,
            fwd_ip="192.168.1.50",
            fwd_port=27015,
            settings=mock_settings,
            protocol="udp",
            confirm=True,
        )

    assert result["proto"] == "udp"


@pytest.mark.asyncio
async def test_create_port_forward_dry_run(mock_settings):
    """Test port forward creation dry run."""
    result = await create_port_forward(
        site_id="default",
        name="Test Rule",
        dst_port=443,
        fwd_ip="192.168.2.10",
        fwd_port=443,
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_create"]["name"] == "Test Rule"
    assert result["would_create"]["dst_port"] == "443"


@pytest.mark.asyncio
async def test_create_port_forward_no_confirm(mock_settings):
    """Test port forward creation fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await create_port_forward(
            site_id="default",
            name="Test",
            dst_port=80,
            fwd_ip="192.168.2.1",
            fwd_port=80,
            settings=mock_settings,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_create_port_forward_invalid_protocol(mock_settings):
    """Test port forward creation with invalid protocol."""
    with pytest.raises(ValidationError) as excinfo:
        await create_port_forward(
            site_id="default",
            name="Test",
            dst_port=80,
            fwd_ip="192.168.2.1",
            fwd_port=80,
            settings=mock_settings,
            protocol="invalid",
            confirm=True,
        )

    assert "Invalid protocol" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_port_forward_invalid_port(mock_settings):
    """Test port forward creation with invalid port."""
    with pytest.raises(ValidationError) as excinfo:
        await create_port_forward(
            site_id="default",
            name="Test",
            dst_port=99999,
            fwd_ip="192.168.2.1",
            fwd_port=80,
            settings=mock_settings,
            confirm=True,
        )

    assert "port" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_create_port_forward_invalid_ip(mock_settings):
    """Test port forward creation with invalid IP."""
    with pytest.raises(ValidationError) as excinfo:
        await create_port_forward(
            site_id="default",
            name="Test",
            dst_port=80,
            fwd_ip="invalid-ip",
            fwd_port=80,
            settings=mock_settings,
            confirm=True,
        )

    assert "ip" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_create_port_forward_with_source_restriction(mock_settings):
    """Test port forward creation with source IP restriction."""
    mock_response = {"data": [{"_id": "pf1", "name": "Restricted", "src": "10.0.0.0/24"}]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        await create_port_forward(
            site_id="default",
            name="Restricted",
            dst_port=22,
            fwd_ip="192.168.2.1",
            fwd_port=22,
            settings=mock_settings,
            src="10.0.0.0/24",
            confirm=True,
        )

    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["src"] == "10.0.0.0/24"


@pytest.mark.asyncio
async def test_create_port_forward_with_logging(mock_settings):
    """Test port forward creation with logging enabled."""
    mock_response = {"data": [{"_id": "pf1", "name": "Logged", "log": True}]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        await create_port_forward(
            site_id="default",
            name="Logged",
            dst_port=80,
            fwd_ip="192.168.2.1",
            fwd_port=80,
            settings=mock_settings,
            log=True,
            confirm=True,
        )

    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["log"] is True


# =============================================================================
# delete_port_forward Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_port_forward_success(mock_settings):
    """Test successful port forward deletion."""
    mock_get_response = {"data": [{"_id": "pf1", "name": "Test Rule"}]}
    mock_delete_response = {}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client.delete = AsyncMock(return_value=mock_delete_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        result = await delete_port_forward("default", "pf1", mock_settings, confirm=True)

    assert result["success"] is True
    assert result["deleted_rule_id"] == "pf1"


@pytest.mark.asyncio
async def test_delete_port_forward_dry_run(mock_settings):
    """Test port forward deletion dry run."""
    result = await delete_port_forward("default", "pf1", mock_settings, confirm=True, dry_run=True)

    assert result["dry_run"] is True
    assert result["would_delete"] == "pf1"


@pytest.mark.asyncio
async def test_delete_port_forward_not_found(mock_settings):
    """Test deleting non-existent port forward."""
    mock_get_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(pf_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await delete_port_forward("default", "nonexistent", mock_settings, confirm=True)


@pytest.mark.asyncio
async def test_delete_port_forward_no_confirm(mock_settings):
    """Test port forward deletion fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await delete_port_forward("default", "pf1", mock_settings, confirm=False)

    assert "requires confirmation" in str(excinfo.value).lower()
