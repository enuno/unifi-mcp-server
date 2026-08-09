"""Unit tests for DHCP reservation tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType
from src.tools import dhcp_reservations as dhcp
from src.utils.exceptions import ResourceNotFoundError


@pytest.fixture
def local_settings() -> MagicMock:
    settings = MagicMock()
    settings.api_type = APIType.LOCAL
    settings.api_key = "test-key"
    settings.log_level = "INFO"
    return settings


@pytest.fixture
def cloud_settings() -> MagicMock:
    settings = MagicMock()
    settings.api_type = APIType.CLOUD_EA
    settings.api_key = "test-key"
    settings.log_level = "INFO"
    return settings


@pytest.fixture
def sample_users() -> list[dict[str, Any]]:
    return [
        {
            "_id": "user-1",
            "mac": "aa:bb:cc:dd:ee:01",
            "name": "Camera 1",
            "hostname": "cam-1",
            "use_fixedip": True,
            "fixed_ip": "192.168.30.10",
            "network_id": "net-cameras",
            "local_dns_record": "cam1.local",
            "local_dns_record_enabled": True,
        },
        {
            "_id": "user-2",
            "mac": "aa:bb:cc:dd:ee:02",
            "name": "Laptop",
            "hostname": "laptop",
            "use_fixedip": False,
        },
        {
            "_id": "user-3",
            "mac": "aa:bb:cc:dd:ee:03",
            "name": "Server",
            "use_fixedip": True,
            "fixed_ip": "192.168.40.10",
            "network_id": "net-servers",
            "local_dns_record": "",
            "local_dns_record_enabled": False,
        },
    ]


def _mock_client(get_response: Any = None) -> AsyncMock:
    client = AsyncMock()
    client.is_authenticated = True
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value=get_response)
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestLocalApiGate:
    @pytest.mark.asyncio
    async def test_cloud_mode_raises(self, cloud_settings: MagicMock) -> None:
        with pytest.raises(NotImplementedError, match="UNIFI_API_TYPE='local'"):
            await dhcp.list_dhcp_reservations("default", cloud_settings)


class TestListDhcpReservations:
    @pytest.mark.asyncio
    async def test_lists_only_fixed_ip_users(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        client = _mock_client({"data": sample_users})
        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.list_dhcp_reservations("default", local_settings)

        assert len(result) == 2
        macs = {r["mac"] for r in result}
        assert macs == {"aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:03"}

    @pytest.mark.asyncio
    async def test_filter_by_network_id(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        client = _mock_client({"data": sample_users})
        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.list_dhcp_reservations(
                "default", local_settings, network_id="net-cameras"
            )

        assert len(result) == 1
        assert result[0]["mac"] == "aa:bb:cc:dd:ee:01"


class TestGetDhcpReservation:
    @pytest.mark.asyncio
    async def test_found(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        client = _mock_client({"data": sample_users})
        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.get_dhcp_reservation("aa:bb:cc:dd:ee:01", "default", local_settings)

        assert result["fixed_ip"] == "192.168.30.10"
        assert result["name"] == "Camera 1"

    @pytest.mark.asyncio
    async def test_not_found_raises(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        client = _mock_client({"data": sample_users})
        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            with pytest.raises(ResourceNotFoundError):
                await dhcp.get_dhcp_reservation("ff:ff:ff:ff:ff:ff", "default", local_settings)

    @pytest.mark.asyncio
    async def test_non_fixed_ip_user_not_found(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        """user-2 exists but has use_fixedip=False — should not match."""
        client = _mock_client({"data": sample_users})
        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            with pytest.raises(ResourceNotFoundError):
                await dhcp.get_dhcp_reservation("aa:bb:cc:dd:ee:02", "default", local_settings)


class TestCreateDhcpReservation:
    @pytest.mark.asyncio
    async def test_create_success(self, local_settings: MagicMock) -> None:
        created = {
            "_id": "new-1",
            "mac": "11:22:33:44:55:66",
            "name": "New Device",
            "use_fixedip": True,
            "fixed_ip": "192.168.10.200",
            "network_id": "net-lan",
        }
        client = _mock_client()
        client.post.return_value = {"data": [created]}

        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.create_dhcp_reservation(
                mac="11:22:33:44:55:66",
                fixed_ip="192.168.10.200",
                network_id="net-lan",
                site_id="default",
                settings=local_settings,
                name="New Device",
                confirm=True,
            )

        assert result["fixed_ip"] == "192.168.10.200"
        assert result["mac"] == "11:22:33:44:55:66"
        post_body = client.post.call_args.kwargs["json_data"]
        assert post_body["use_fixedip"] is True
        assert post_body["fixed_ip"] == "192.168.10.200"
        assert post_body["network_id"] == "net-lan"

    @pytest.mark.asyncio
    async def test_create_dry_run(self, local_settings: MagicMock) -> None:
        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client()
            result = await dhcp.create_dhcp_reservation(
                mac="11:22:33:44:55:66",
                fixed_ip="192.168.10.200",
                network_id="net-lan",
                site_id="default",
                settings=local_settings,
                confirm=True,
                dry_run=True,
            )

        assert result["status"] == "dry_run"
        assert result["payload"]["fixed_ip"] == "192.168.10.200"

    @pytest.mark.asyncio
    async def test_create_existing_mac_merges_via_put(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        """A MAC the controller already knows is merged, not re-posted.

        Posting it would fail with api.err.MacUsed.
        """
        merged = {**sample_users[1], "fixed_ip": "192.168.10.200", "use_fixedip": True}
        client = _mock_client({"data": sample_users})
        client.put.return_value = {"data": [merged]}

        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.create_dhcp_reservation(
                mac="aa:bb:cc:dd:ee:02",
                fixed_ip="192.168.10.200",
                network_id="net-lan",
                site_id="default",
                settings=local_settings,
                confirm=True,
            )

        client.post.assert_not_called()
        assert client.put.call_args.args[0].endswith("/user-2")
        put_body = client.put.call_args.kwargs["json_data"]
        assert put_body["use_fixedip"] is True
        assert put_body["fixed_ip"] == "192.168.10.200"
        # The MAC identifies the existing entry; re-sending it is rejected.
        assert "mac" not in put_body
        assert result["fixed_ip"] == "192.168.10.200"

    @pytest.mark.asyncio
    async def test_create_without_confirm_raises(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValueError, match="confirm=True"):
            await dhcp.create_dhcp_reservation(
                mac="11:22:33:44:55:66",
                fixed_ip="192.168.10.200",
                network_id="net-lan",
                site_id="default",
                settings=local_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_create_defaults_use_fixedip_true_when_response_omits(
        self, local_settings: MagicMock
    ) -> None:
        """create always requests use_fixedip, so an absent key means active."""
        client = _mock_client()
        client.post.return_value = {
            "data": [{"_id": "new-2", "mac": "11:22:33:44:55:77", "fixed_ip": "192.168.10.201"}]
        }

        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.create_dhcp_reservation(
                mac="11:22:33:44:55:77",
                fixed_ip="192.168.10.201",
                network_id="net-lan",
                site_id="default",
                settings=local_settings,
                confirm=True,
            )

        assert result["use_fixedip"] is True


class TestUpdateDhcpReservation:
    @pytest.mark.asyncio
    async def test_update_ip(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        updated = {**sample_users[0], "fixed_ip": "192.168.30.99"}
        client = _mock_client({"data": sample_users})
        client.put.return_value = {"data": [updated]}

        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.update_dhcp_reservation(
                mac="aa:bb:cc:dd:ee:01",
                site_id="default",
                settings=local_settings,
                fixed_ip="192.168.30.99",
                confirm=True,
            )

        assert result["fixed_ip"] == "192.168.30.99"
        put_body = client.put.call_args.kwargs["json_data"]
        # Setting a fixed_ip must also enable use_fixedip, otherwise the
        # controller stores the IP inertly and the reservation never activates.
        assert put_body == {"fixed_ip": "192.168.30.99", "use_fixedip": True}

    @pytest.mark.asyncio
    async def test_update_name_only_does_not_enable_fixedip(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        """A metadata-only update (no fixed_ip) must not toggle use_fixedip."""
        client = _mock_client({"data": sample_users})
        client.put.return_value = {"data": [{**sample_users[0], "name": "Renamed"}]}

        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            await dhcp.update_dhcp_reservation(
                mac="aa:bb:cc:dd:ee:01",
                site_id="default",
                settings=local_settings,
                name="Renamed",
                confirm=True,
            )

        put_body = client.put.call_args.kwargs["json_data"]
        assert put_body == {"name": "Renamed"}
        assert "use_fixedip" not in put_body

    @pytest.mark.asyncio
    async def test_update_metadata_only_preserves_existing_use_fixedip(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        """If the PUT response omits use_fixedip, fall back to the prior state."""
        client = _mock_client({"data": sample_users})
        # Response echoes the rename but not use_fixedip; user-1 was active.
        client.put.return_value = {
            "data": [{"_id": "user-1", "mac": "aa:bb:cc:dd:ee:01", "name": "Renamed"}]
        }

        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.update_dhcp_reservation(
                mac="aa:bb:cc:dd:ee:01",
                site_id="default",
                settings=local_settings,
                name="Renamed",
                confirm=True,
            )

        assert result["use_fixedip"] is True

    @pytest.mark.asyncio
    async def test_update_unknown_mac_raises(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        client = _mock_client({"data": sample_users})
        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            with pytest.raises(ResourceNotFoundError):
                await dhcp.update_dhcp_reservation(
                    mac="ff:ff:ff:ff:ff:ff",
                    site_id="default",
                    settings=local_settings,
                    fixed_ip="192.168.10.1",
                    confirm=True,
                )


class TestRemoveDhcpReservation:
    @pytest.mark.asyncio
    async def test_clear_reservation_keeps_client(
        self, local_settings: MagicMock, sample_users: list[dict[str, Any]]
    ) -> None:
        client = _mock_client({"data": sample_users})
        client.put.return_value = {"data": [{**sample_users[0], "use_fixedip": False}]}

        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.remove_dhcp_reservation(
                mac="aa:bb:cc:dd:ee:01",
                site_id="default",
                settings=local_settings,
                confirm=True,
            )

        assert result["action"] == "reservation_cleared"
        put_body = client.put.call_args.kwargs["json_data"]
        assert put_body == {"use_fixedip": False}

    @pytest.mark.asyncio
    async def test_forget_client_entirely(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.post.return_value = {"data": []}

        with patch("src.tools.dhcp_reservations.UniFiClient") as MockClient:
            MockClient.return_value = client
            result = await dhcp.remove_dhcp_reservation(
                mac="aa:bb:cc:dd:ee:01",
                site_id="default",
                settings=local_settings,
                forget_client=True,
                confirm=True,
            )

        assert result["action"] == "forgotten"
        post_body = client.post.call_args.kwargs["json_data"]
        assert post_body == {"cmd": "forget-sta", "macs": ["aa:bb:cc:dd:ee:01"]}

    @pytest.mark.asyncio
    async def test_dry_run(self, local_settings: MagicMock) -> None:
        result = await dhcp.remove_dhcp_reservation(
            mac="aa:bb:cc:dd:ee:01",
            site_id="default",
            settings=local_settings,
            confirm=True,
            dry_run=True,
        )
        assert result["status"] == "dry_run"
        assert result["action"] == "clear_fixed_ip"

    @pytest.mark.asyncio
    async def test_dry_run_forget(self, local_settings: MagicMock) -> None:
        result = await dhcp.remove_dhcp_reservation(
            mac="aa:bb:cc:dd:ee:01",
            site_id="default",
            settings=local_settings,
            forget_client=True,
            confirm=True,
            dry_run=True,
        )
        assert result["status"] == "dry_run"
        assert result["action"] == "forget_client"
