"""Unit tests for src/tools/wans.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType
from src.tools.wans import (
    create_dynamic_dns,
    delete_dynamic_dns,
    get_dynamic_dns,
    list_dynamic_dns,
    list_wan_connections,
    update_dynamic_dns,
)
from src.utils.exceptions import APIError, ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = APIType.LOCAL
    return settings


def make_wan(wan_id="wan-1"):
    return {
        "_id": wan_id,
        "site_id": "default",
        "name": "WAN1",
        "wan_type": "dhcp",
        "interface": "eth0",
        "status": "online",
        "dns_servers": ["1.1.1.1", "8.8.8.8"],
        "is_backup": True,
    }


def make_sparse_wan(wan_id="wan-1"):
    """Build a WAN exactly as Integration v1 ``/sites/{site_id}/wans`` returns it.

    That endpoint reports only ``id`` and ``name``; there is no per-WAN detail
    route to enrich the record from.

    Args:
        wan_id: Identifier to report as ``id``

    Returns:
        The two-field WAN record the sparse endpoint sends
    """
    return {"id": wan_id, "name": "Internet 1"}


def create_mock_client(return_value):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=return_value)
    mock_client.post = AsyncMock(return_value=return_value)
    mock_client.put = AsyncMock(return_value=return_value)
    mock_client.delete = AsyncMock(return_value={"meta": {"rc": "ok"}})
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = False
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def make_dynamic_dns(dynamic_dns_id="ddns-1"):
    return {
        "_id": dynamic_dns_id,
        "host_name": "vpn.example.com",
        "service": "custom",
        "custom_service": "dyndns",
        "server": "updates.example.com",
        "interface": "wan",
        "login": "api-user",
        "x_password": "secret-token",
        "options": ["ssl=yes"],
    }


class TestListWanConnections:
    async def test_returns_list_when_api_returns_list(self, mock_settings):
        wan = make_wan()
        mock_client = create_mock_client([wan])
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_wan_connections("default", mock_settings)
        assert len(result) == 1
        assert result[0]["name"] == "WAN1"

    async def test_returns_list_when_api_returns_dict(self, mock_settings):
        wan = make_wan()
        mock_client = create_mock_client({"data": [wan]})
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_wan_connections("default", mock_settings)
        assert len(result) == 1
        assert result[0]["wan_type"] == "dhcp"

    async def test_empty_response(self, mock_settings):
        mock_client = create_mock_client([])
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_wan_connections("default", mock_settings)
        assert result == []

    async def test_authenticates_when_not_authenticated(self, mock_settings):
        wan = make_wan()
        mock_client = create_mock_client([wan])
        mock_client.is_authenticated = False
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            await list_wan_connections("default", mock_settings)
        mock_client.authenticate.assert_called_once()

    async def test_accepts_sparse_integration_api_response(self, mock_settings):
        """Integration v1 returns only id and name; that must not raise."""
        mock_client = create_mock_client({"data": [make_sparse_wan()]})
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_wan_connections("default", mock_settings)

        # Absent fields are dropped from the output rather than failing
        # validation or padding the record with 20 nulls. No field carries a
        # concrete default, so "omitted by the controller" is never reported as
        # an empty list or a False flag either.
        assert result == [{"id": "wan-1", "name": "Internet 1"}]

    async def test_populated_optional_fields_are_preserved(self, mock_settings):
        """Relaxing the model must not drop values when they are present."""
        mock_client = create_mock_client({"data": [make_wan()]})
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_wan_connections("default", mock_settings)

        assert result[0]["site_id"] == "default"
        assert result[0]["wan_type"] == "dhcp"
        assert result[0]["interface"] == "eth0"
        assert result[0]["status"] == "online"
        assert result[0]["dns_servers"] == ["1.1.1.1", "8.8.8.8"]
        assert result[0]["is_backup"] is True
        # Only what the controller reported: is_backup=True survives the
        # exclude_none filter, but a field nobody sent stays out.
        assert "ip_address" not in result[0]


class TestDynamicDNS:
    async def test_list_dynamic_dns_redacts_password(self, mock_settings):
        record = make_dynamic_dns()
        mock_client = create_mock_client({"data": [record]})

        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_dynamic_dns("default", mock_settings)

        mock_client.get.assert_called_once_with("/ea/sites/default/rest/dynamicdns")
        assert result == [
            {
                "id": "ddns-1",
                "_id": "ddns-1",
                "host_name": "vpn.example.com",
                "service": "custom",
                "custom_service": "dyndns",
                "server": "updates.example.com",
                "interface": "wan",
                "login": "api-user",
                "options": ["ssl=yes"],
                "password_configured": True,
            }
        ]

    async def test_get_dynamic_dns(self, mock_settings):
        mock_client = create_mock_client({"data": [make_dynamic_dns()]})

        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await get_dynamic_dns("ddns-1", "default", mock_settings)

        mock_client.get.assert_called_once_with("/ea/sites/default/rest/dynamicdns/ddns-1")
        assert result["id"] == "ddns-1"
        assert "x_password" not in result

    async def test_get_dynamic_dns_handles_direct_dict_response(self, mock_settings):
        mock_client = create_mock_client(make_dynamic_dns())

        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await get_dynamic_dns("ddns-1", "default", mock_settings)

        assert result["id"] == "ddns-1"
        assert result["host_name"] == "vpn.example.com"

    async def test_get_dynamic_dns_empty_response_raises_not_found(self, mock_settings):
        mock_client = create_mock_client({"data": []})

        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            with pytest.raises(ResourceNotFoundError):
                await get_dynamic_dns("ddns-1", "default", mock_settings)

    async def test_create_dynamic_dns_posts_custom_provider_payload(self, mock_settings):
        mock_client = create_mock_client({"data": [make_dynamic_dns()]})

        with (
            patch("src.tools.wans.UniFiClient", return_value=mock_client),
            patch("src.tools.wans.log_audit") as mock_audit,
        ):
            result = await create_dynamic_dns(
                site_id="default",
                settings=mock_settings,
                host_name="vpn.example.com",
                service="custom",
                interface="wan",
                login="api-user",
                password="secret-token",
                server="updates.example.com",
                custom_service="dyndns",
                options=["ssl=yes"],
                confirm=True,
            )

        mock_client.post.assert_called_once_with(
            "/ea/sites/default/rest/dynamicdns",
            json_data={
                "host_name": "vpn.example.com",
                "service": "custom",
                "interface": "wan",
                "login": "api-user",
                "x_password": "secret-token",
                "server": "updates.example.com",
                "custom_service": "dyndns",
                "options": ["ssl=yes"],
            },
        )
        audit_parameters = mock_audit.call_args.kwargs["parameters"]
        assert audit_parameters["x_password"] == "***REDACTED***"
        assert result["password_configured"] is True

    async def test_create_dynamic_dns_invalid_hostname_raises(self, mock_settings):
        with pytest.raises(ValidationError, match="host_name"):
            await create_dynamic_dns(
                site_id="default",
                settings=mock_settings,
                host_name="../bad",
                confirm=True,
            )

    async def test_create_dynamic_dns_failure_is_audited(self, mock_settings):
        mock_client = create_mock_client({})
        mock_client.post = AsyncMock(side_effect=APIError("create failed"))

        with (
            patch("src.tools.wans.UniFiClient", return_value=mock_client),
            patch("src.tools.wans.log_audit") as mock_audit,
        ):
            with pytest.raises(APIError):
                await create_dynamic_dns(
                    site_id="default",
                    settings=mock_settings,
                    host_name="vpn.example.com",
                    confirm=True,
                )

        assert mock_audit.call_args.kwargs["result"] == "failed"
        assert mock_audit.call_args.kwargs["error"] == "create failed"

    async def test_create_dynamic_dns_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await create_dynamic_dns(
                site_id="default",
                settings=mock_settings,
                host_name="vpn.example.com",
            )

    async def test_create_dynamic_dns_dry_run_redacts_password(self, mock_settings):
        with patch("src.tools.wans.log_audit") as mock_audit:
            result = await create_dynamic_dns(
                site_id="default",
                settings=mock_settings,
                host_name="vpn.example.com",
                password="secret-token",
                confirm=False,
                dry_run=True,
            )

        assert result["dry_run"] is True
        assert result["would_create"]["x_password"] == "***REDACTED***"
        assert mock_audit.call_args.kwargs["result"] == "dry_run"
        assert mock_audit.call_args.kwargs["dry_run"] is True

    async def test_update_dynamic_dns_puts_partial_payload(self, mock_settings):
        mock_client = create_mock_client(
            {
                "data": [
                    {
                        **make_dynamic_dns(),
                        "host_name": "new.example.com",
                        "x_password": "",
                    }
                ]
            }
        )

        with (
            patch("src.tools.wans.UniFiClient", return_value=mock_client),
            patch("src.tools.wans.log_audit") as mock_audit,
        ):
            result = await update_dynamic_dns(
                dynamic_dns_id="ddns-1",
                site_id="default",
                settings=mock_settings,
                host_name="new.example.com",
                server="new-updates.example.com",
                confirm=True,
            )

        mock_client.put.assert_called_once_with(
            "/ea/sites/default/rest/dynamicdns/ddns-1",
            json_data={"host_name": "new.example.com", "server": "new-updates.example.com"},
        )
        assert mock_audit.call_args.kwargs["operation"] == "update_dynamic_dns"
        assert result["host_name"] == "new.example.com"
        assert result["password_configured"] is False

    async def test_update_dynamic_dns_empty_payload_raises(self, mock_settings):
        with pytest.raises(ValidationError, match="At least one field"):
            await update_dynamic_dns(
                dynamic_dns_id="ddns-1",
                site_id="default",
                settings=mock_settings,
                confirm=True,
            )

    async def test_update_dynamic_dns_empty_response_raises_not_found(self, mock_settings):
        mock_client = create_mock_client({"data": []})

        with (
            patch("src.tools.wans.UniFiClient", return_value=mock_client),
            patch("src.tools.wans.log_audit") as mock_audit,
        ):
            with pytest.raises(ResourceNotFoundError):
                await update_dynamic_dns(
                    dynamic_dns_id="ddns-1",
                    site_id="default",
                    settings=mock_settings,
                    host_name="new.example.com",
                    confirm=True,
                )

        assert mock_audit.call_args.kwargs["result"] == "failed"

    async def test_update_dynamic_dns_dry_run_skips_api_call(self, mock_settings):
        with (
            patch("src.tools.wans.UniFiClient") as mock_client_cls,
            patch("src.tools.wans.log_audit") as mock_audit,
        ):
            result = await update_dynamic_dns(
                dynamic_dns_id="ddns-1",
                site_id="default",
                settings=mock_settings,
                login="new-user",
                password="new-secret",
                dry_run=True,
            )

        mock_client_cls.assert_not_called()
        assert result["would_update"] == {
            "login": "new-user",
            "x_password": "***REDACTED***",
        }
        assert mock_audit.call_args.kwargs["result"] == "dry_run"

    async def test_delete_dynamic_dns(self, mock_settings):
        mock_client = create_mock_client({})

        with (
            patch("src.tools.wans.UniFiClient", return_value=mock_client),
            patch("src.tools.wans.log_audit") as mock_audit,
        ):
            result = await delete_dynamic_dns(
                dynamic_dns_id="ddns-1",
                site_id="default",
                settings=mock_settings,
                confirm=True,
            )

        mock_client.delete.assert_called_once_with("/ea/sites/default/rest/dynamicdns/ddns-1")
        assert mock_audit.call_args.kwargs["operation"] == "delete_dynamic_dns"
        assert result == {
            "status": "deleted",
            "dynamic_dns_id": "ddns-1",
            "site_id": "default",
        }

    async def test_delete_dynamic_dns_dry_run(self, mock_settings):
        with patch("src.tools.wans.log_audit") as mock_audit:
            result = await delete_dynamic_dns(
                dynamic_dns_id="ddns-1",
                site_id="default",
                settings=mock_settings,
                dry_run=True,
            )

        assert result == {"dry_run": True, "would_delete": "ddns-1"}
        assert mock_audit.call_args.kwargs["result"] == "dry_run"

    async def test_delete_dynamic_dns_invalid_id_raises(self, mock_settings):
        with pytest.raises(ValidationError, match="dynamic_dns_id"):
            await delete_dynamic_dns(
                dynamic_dns_id="../ddns-1",
                site_id="default",
                settings=mock_settings,
                confirm=True,
            )
