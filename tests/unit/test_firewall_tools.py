"""Unit tests for firewall rules management tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.firewall import (
    create_firewall_rule,
    delete_firewall_rule,
    list_firewall_rules,
    update_firewall_rule,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_firewall_rules():
    """Sample firewall rules for testing."""
    return [
        {
            "_id": "rule-001",
            "name": "Allow HTTPS",
            "action": "accept",
            "enabled": True,
            "protocol": "tcp",
            "dst_port": 443,
            "src_address": "192.168.1.0/24",
            "dst_address": "0.0.0.0/0",
        },
        {
            "_id": "rule-002",
            "name": "Block Malicious IPs",
            "action": "drop",
            "enabled": True,
            "src_address": "10.0.0.0/8",
            "dst_address": "0.0.0.0/0",
        },
        {
            "_id": "rule-003",
            "name": "Allow SSH",
            "action": "accept",
            "enabled": False,
            "protocol": "tcp",
            "dst_port": 22,
        },
    ]


@pytest.fixture
def sample_rule_response():
    """Sample firewall rule creation response."""
    return {
        "_id": "rule-new-123",
        "name": "Test Rule",
        "action": "accept",
        "enabled": True,
        "protocol": "tcp",
        "dst_port": 8080,
    }


# ============================================================================
# Test: list_firewall_rules - Read-only Rule Listing
# ============================================================================


@pytest.mark.asyncio
async def test_list_firewall_rules_success(
    settings: Settings, sample_firewall_rules: list
) -> None:
    """Test listing firewall rules successfully."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_firewall_rules
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_firewall_rules("site-123", settings)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["name"] == "Allow HTTPS"
        assert result[1]["action"] == "drop"
        mock_client.authenticate.assert_called_once()
        mock_client.get.assert_called_once_with("/ea/sites/site-123/rest/firewallrule")


@pytest.mark.asyncio
async def test_list_firewall_rules_with_pagination(
    settings: Settings, sample_firewall_rules: list
) -> None:
    """Test listing firewall rules with pagination."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_firewall_rules
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_firewall_rules("site-123", settings, limit=2, offset=1)

        assert len(result) == 2
        assert result[0]["name"] == "Block Malicious IPs"
        assert result[1]["name"] == "Allow SSH"


@pytest.mark.asyncio
async def test_list_firewall_rules_empty(settings: Settings) -> None:
    """Test listing when no firewall rules exist."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = []
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_firewall_rules("site-123", settings)

        assert result == []


# ============================================================================
# Test: create_firewall_rule - Rule Creation with Security Validation
# ============================================================================


@pytest.mark.asyncio
async def test_create_firewall_rule_success(
    settings: Settings, sample_rule_response: dict
) -> None:
    """Test creating a firewall rule successfully."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = [sample_rule_response]
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_firewall_rule(
            site_id="site-123",
            name="Test Rule",
            action="accept",
            settings=settings,
            protocol="tcp",
            port=8080,
            confirm=True,
        )

        assert result["name"] == "Test Rule"
        assert result["action"] == "accept"
        assert result["dst_port"] == 8080
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_create_firewall_rule_without_confirmation(settings: Settings) -> None:
    """Test that rule creation requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await create_firewall_rule(
            site_id="site-123",
            name="Test Rule",
            action="accept",
            settings=settings,
            confirm=False,
        )


@pytest.mark.asyncio
async def test_create_firewall_rule_dry_run(settings: Settings) -> None:
    """Test creating a firewall rule in dry-run mode."""
    result = await create_firewall_rule(
        site_id="site-123",
        name="Test Rule",
        action="drop",
        settings=settings,
        source="192.168.1.0/24",
        destination="10.0.0.0/8",
        protocol="tcp",
        port=443,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_create"]["name"] == "Test Rule"
    assert result["would_create"]["action"] == "drop"
    assert result["would_create"]["src_address"] == "192.168.1.0/24"
    assert result["would_create"]["protocol"] == "tcp"


@pytest.mark.asyncio
async def test_create_firewall_rule_invalid_action(settings: Settings) -> None:
    """Test creating a rule with invalid action."""
    with pytest.raises(ValueError, match="Invalid action"):
        await create_firewall_rule(
            site_id="site-123",
            name="Bad Rule",
            action="invalid_action",
            settings=settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_firewall_rule_invalid_protocol(settings: Settings) -> None:
    """Test creating a rule with invalid protocol."""
    with pytest.raises(ValueError, match="Invalid protocol"):
        await create_firewall_rule(
            site_id="site-123",
            name="Bad Rule",
            action="accept",
            settings=settings,
            protocol="invalid_protocol",
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_firewall_rule_with_all_parameters(
    settings: Settings, sample_rule_response: dict
) -> None:
    """Test creating a rule with all optional parameters."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = [sample_rule_response]
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_firewall_rule(
            site_id="site-123",
            name="Complete Rule",
            action="reject",
            settings=settings,
            source="192.168.1.100",
            destination="10.0.0.50",
            protocol="udp",
            port=53,
            enabled=False,
            confirm=True,
        )

        assert result is not None
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "Complete Rule"
        assert json_data["action"] == "reject"
        assert json_data["enabled"] is False


# ============================================================================
# Test: update_firewall_rule - Rule Modification
# ============================================================================


@pytest.mark.asyncio
async def test_update_firewall_rule_success(
    settings: Settings, sample_firewall_rules: list, sample_rule_response: dict
) -> None:
    """Test updating a firewall rule successfully."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_firewall_rules
        mock_client.put.return_value = [sample_rule_response]
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await update_firewall_rule(
            site_id="site-123",
            rule_id="rule-001",
            settings=settings,
            name="Updated Rule",
            action="drop",
            confirm=True,
        )

        assert result is not None
        mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_update_firewall_rule_without_confirmation(settings: Settings) -> None:
    """Test that rule update requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await update_firewall_rule(
            site_id="site-123",
            rule_id="rule-001",
            settings=settings,
            name="Updated Rule",
            confirm=False,
        )


@pytest.mark.asyncio
async def test_update_firewall_rule_dry_run(
    settings: Settings, sample_firewall_rules: list
) -> None:
    """Test updating a rule in dry-run mode."""
    result = await update_firewall_rule(
        site_id="site-123",
        rule_id="rule-001",
        settings=settings,
        name="Updated Rule",
        enabled=False,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_update"]["name"] == "Updated Rule"
    assert result["would_update"]["enabled"] is False


@pytest.mark.asyncio
async def test_update_firewall_rule_not_found(settings: Settings) -> None:
    """Test updating a non-existent rule."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = []
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await update_firewall_rule(
                site_id="site-123",
                rule_id="nonexistent",
                settings=settings,
                name="Updated Rule",
                confirm=True,
            )


@pytest.mark.asyncio
async def test_update_firewall_rule_invalid_action(settings: Settings) -> None:
    """Test updating a rule with invalid action."""
    with pytest.raises(ValueError, match="Invalid action"):
        await update_firewall_rule(
            site_id="site-123",
            rule_id="rule-001",
            settings=settings,
            action="invalid",
            confirm=True,
        )


@pytest.mark.asyncio
async def test_update_firewall_rule_invalid_protocol(settings: Settings) -> None:
    """Test updating a rule with invalid protocol."""
    with pytest.raises(ValueError, match="Invalid protocol"):
        await update_firewall_rule(
            site_id="site-123",
            rule_id="rule-001",
            settings=settings,
            protocol="invalid",
            confirm=True,
        )


# ============================================================================
# Test: delete_firewall_rule - Rule Deletion
# ============================================================================


@pytest.mark.asyncio
async def test_delete_firewall_rule_success(
    settings: Settings, sample_firewall_rules: list
) -> None:
    """Test deleting a firewall rule successfully."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_firewall_rules
        mock_client.delete.return_value = {"success": True}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await delete_firewall_rule(
            site_id="site-123", rule_id="rule-001", settings=settings, confirm=True
        )

        assert result["success"] is True
        assert result["deleted_rule_id"] == "rule-001"
        mock_client.delete.assert_called_once_with("/ea/sites/site-123/rest/firewallrule/rule-001")


@pytest.mark.asyncio
async def test_delete_firewall_rule_without_confirmation(settings: Settings) -> None:
    """Test that rule deletion requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await delete_firewall_rule(
            site_id="site-123", rule_id="rule-001", settings=settings, confirm=False
        )


@pytest.mark.asyncio
async def test_delete_firewall_rule_dry_run(settings: Settings) -> None:
    """Test deleting a rule in dry-run mode."""
    result = await delete_firewall_rule(
        site_id="site-123", rule_id="rule-001", settings=settings, confirm=True, dry_run=True
    )

    assert result["dry_run"] is True
    assert result["would_delete"] == "rule-001"


@pytest.mark.asyncio
async def test_delete_firewall_rule_not_found(settings: Settings) -> None:
    """Test deleting a non-existent rule."""
    with patch("src.tools.firewall.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = []
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await delete_firewall_rule(
                site_id="site-123", rule_id="nonexistent", settings=settings, confirm=True
            )
