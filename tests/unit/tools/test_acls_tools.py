"""Tests for ACL tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.acls import (
    create_acl_rule,
    delete_acl_rule,
    get_acl_rule,
    list_acl_rules,
    update_acl_rule,
)
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    settings.request_timeout = 30.0
    settings.site_manager_enabled = False
    settings.get_headers = MagicMock(return_value={"X-API-Key": "test-key"})
    settings.get_integration_path = MagicMock(
        side_effect=lambda endpoint: f"/integration/v1/{endpoint}"
    )
    return settings


def _prepare_client(mock_client: AsyncMock) -> AsyncMock:
    """Mock resolve_site_id so tests can assert literal paths."""
    mock_client.resolve_site_id = AsyncMock(side_effect=lambda s: s)
    return mock_client


@pytest.mark.asyncio
async def test_list_acl_rules_success(mock_settings):
    mock_response = {
        "data": [
            {
                "_id": "acl-1",
                "site_id": "default",
                "name": "Block IoT to LAN",
                "enabled": True,
                "action": "deny",
                "source_type": "network",
                "source_id": "net-iot",
                "destination_type": "network",
                "destination_id": "net-lan",
                "priority": 10,
            },
            {
                "_id": "acl-2",
                "site_id": "default",
                "name": "Allow DNS",
                "enabled": True,
                "action": "allow",
                "protocol": "udp",
                "dst_port": 53,
                "priority": 20,
            },
        ]
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await list_acl_rules("default", mock_settings)

        assert len(result) == 2
        assert result[0]["id"] == "acl-1"
        assert result[0]["name"] == "Block IoT to LAN"
        assert result[0]["action"] == "deny"
        assert result[1]["id"] == "acl-2"
        mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_list_acl_rules_with_filter(mock_settings):
    mock_response = {
        "data": [
            {
                "_id": "acl-1",
                "site_id": "default",
                "name": "Block Rule",
                "enabled": True,
                "action": "deny",
                "priority": 10,
            }
        ]
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await list_acl_rules("default", mock_settings, filter_expr="action==deny")

        assert len(result) == 1
        assert result[0]["action"] == "deny"
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["filter"] == "action==deny"


@pytest.mark.asyncio
async def test_list_acl_rules_pagination(mock_settings):
    mock_response = {
        "data": [
            {
                "_id": "acl-5",
                "site_id": "default",
                "name": "Rule 5",
                "enabled": True,
                "action": "allow",
                "priority": 50,
            }
        ]
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await list_acl_rules("default", mock_settings, limit=10, offset=4)

        assert len(result) == 1
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["params"]["offset"] == 4


@pytest.mark.asyncio
async def test_list_acl_rules_empty(mock_settings):
    mock_response = {"data": []}

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await list_acl_rules("default", mock_settings)

        assert result == []


@pytest.mark.asyncio
async def test_get_acl_rule_success(mock_settings):
    mock_response = {
        "data": {
            "_id": "acl-1",
            "site_id": "default",
            "name": "Block IoT",
            "enabled": True,
            "action": "deny",
            "source_type": "network",
            "source_id": "net-iot",
            "destination_type": "network",
            "destination_id": "net-lan",
            "protocol": "all",
            "priority": 10,
            "description": "Isolate IoT devices",
            "byte_count": 1024000,
            "packet_count": 500,
        }
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = _prepare_client(AsyncMock())
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await get_acl_rule("default", "acl-1", mock_settings)

        assert result["id"] == "acl-1"
        assert result["name"] == "Block IoT"
        assert result["description"] == "Isolate IoT devices"
        assert result["byte_count"] == 1024000
        mock_client.get.assert_called_once_with("/integration/v1/sites/default/acl-rules/acl-1")


@pytest.mark.asyncio
async def test_get_acl_rule_direct_response(mock_settings):
    mock_response = {
        "_id": "acl-1",
        "site_id": "default",
        "name": "Direct Rule",
        "enabled": True,
        "action": "allow",
        "priority": 50,
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await get_acl_rule("default", "acl-1", mock_settings)

        assert result["id"] == "acl-1"
        assert result["name"] == "Direct Rule"


@pytest.mark.asyncio
async def test_create_acl_rule_success(mock_settings):
    mock_response = {
        "data": {
            "_id": "acl-new",
            "site_id": "default",
            "name": "New ACL Rule",
            "enabled": True,
            "action": "allow",
            "priority": 100,
        }
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        with patch("src.tools.acls.audit_action", new_callable=AsyncMock) as mock_audit:
            mock_client = AsyncMock()
            mock_client.is_authenticated = False
            mock_client.authenticate = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await create_acl_rule(
                "default",
                "New ACL Rule",
                "allow",
                mock_settings,
                confirm=True,
            )

            assert result["id"] == "acl-new"
            assert result["name"] == "New ACL Rule"
            mock_client.post.assert_called_once()
            mock_audit.assert_called_once()


@pytest.mark.asyncio
async def test_create_acl_rule_dry_run(mock_settings):
    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = _prepare_client(AsyncMock())
        mock_client.is_authenticated = True
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        # Legacy source/destination/port kwargs are accepted but silently
        # dropped from the payload (the integration API rejects them).
        result = await create_acl_rule(
            "default",
            "Test Rule",
            "BLOCK",
            mock_settings,
            source_type="network",
            source_network="10.0.0.0/24",
            destination_type="ip",
            destination_network="192.168.1.0/24",
            protocol="tcp",
            dst_port=443,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["payload"]["name"] == "Test Rule"
        assert result["payload"]["action"] == "BLOCK"
        assert result["payload"]["type"] == "IPV4"
        assert result["payload"]["enabled"] is True
        assert "sourceType" not in result["payload"]
        assert "dstPort" not in result["payload"]
        mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_acl_rule_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await create_acl_rule(
            "default",
            "Test Rule",
            "deny",
            mock_settings,
            confirm=False,
        )
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_acl_rule_legacy_params_ignored(mock_settings):
    """Legacy source/destination/port filters are accepted for backwards
    compatibility but dropped from the payload — the UniFi integration API
    rejects them as unknown properties."""
    mock_response = {
        "data": {
            "_id": "acl-full",
            "name": "Full Options Rule",
            "enabled": False,
            "action": "BLOCK",
            "type": "IPV4",
        }
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        with patch("src.tools.acls.audit_action", new_callable=AsyncMock):
            mock_client = _prepare_client(AsyncMock())
            mock_client.is_authenticated = True
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await create_acl_rule(
                "default",
                "Full Options Rule",
                "block",
                mock_settings,
                enabled=False,
                source_type="network",
                source_id="net-1",
                source_network="10.0.0.0/8",
                destination_type="network",
                destination_id="net-2",
                destination_network="192.168.0.0/16",
                protocol="tcp",
                src_port=1024,
                dst_port=443,
                priority=5,
                description="Full test rule",
                confirm=True,
            )

            assert result["name"] == "Full Options Rule"
            call_args = mock_client.post.call_args
            payload = call_args[1]["json_data"]
            # Payload contains only the 4 fields the integration API accepts.
            assert set(payload.keys()) == {"name", "enabled", "action", "type"}
            assert payload["action"] == "BLOCK"
            assert payload["type"] == "IPV4"
            assert payload["enabled"] is False


@pytest.mark.asyncio
async def test_update_acl_rule_success(mock_settings):
    mock_response = {
        "data": {
            "_id": "acl-1",
            "site_id": "default",
            "name": "Updated Rule",
            "enabled": False,
            "action": "deny",
            "priority": 100,
        }
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        with patch("src.tools.acls.audit_action", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.is_authenticated = True
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await update_acl_rule(
                "default",
                "acl-1",
                mock_settings,
                name="Updated Rule",
                enabled=False,
                confirm=True,
            )

            assert result["name"] == "Updated Rule"
            assert result["enabled"] is False
            mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_update_acl_rule_dry_run(mock_settings):
    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = _prepare_client(AsyncMock())
        mock_client.is_authenticated = True
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await update_acl_rule(
            "default",
            "acl-1",
            mock_settings,
            name="Preview Name",
            action="allow",
            priority=50,  # legacy kwarg — ignored
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["payload"]["name"] == "Preview Name"
        assert result["payload"]["action"] == "ALLOW"
        assert "priority" not in result["payload"]
        mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_acl_rule_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await update_acl_rule(
            "default",
            "acl-1",
            mock_settings,
            name="New Name",
            confirm=False,
        )
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_acl_rule_partial_fields(mock_settings):
    mock_response = {
        "data": {
            "_id": "acl-1",
            "name": "Existing Name",
            "enabled": False,
            "action": "BLOCK",
            "type": "IPV4",
        }
    }

    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        with patch("src.tools.acls.audit_action", new_callable=AsyncMock):
            mock_client = _prepare_client(AsyncMock())
            mock_client.is_authenticated = True
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await update_acl_rule(
                "default",
                "acl-1",
                mock_settings,
                enabled=False,
                confirm=True,
            )

            assert result["enabled"] is False
            call_args = mock_client.put.call_args
            payload = call_args[1]["json_data"]
            assert payload == {"enabled": False}


@pytest.mark.asyncio
async def test_delete_acl_rule_success(mock_settings):
    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        with patch("src.tools.acls.audit_action", new_callable=AsyncMock):
            mock_client = _prepare_client(AsyncMock())
            mock_client.is_authenticated = False
            mock_client.authenticate = AsyncMock()
            mock_client.delete = AsyncMock(return_value={})
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await delete_acl_rule(
                "default",
                "acl-1",
                mock_settings,
                confirm=True,
            )

            assert result["success"] is True
            assert "acl-1" in result["message"]
            mock_client.delete.assert_called_once_with(
                "/integration/v1/sites/default/acl-rules/acl-1"
            )


@pytest.mark.asyncio
async def test_delete_acl_rule_dry_run(mock_settings):
    with patch("src.tools.acls.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await delete_acl_rule(
            "default",
            "acl-1",
            mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["acl_rule_id"] == "acl-1"
        mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_acl_rule_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await delete_acl_rule(
            "default",
            "acl-1",
            mock_settings,
            confirm=False,
        )
    assert "requires confirmation" in str(excinfo.value)
