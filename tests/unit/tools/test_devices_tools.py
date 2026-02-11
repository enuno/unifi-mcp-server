"""Unit tests for src/tools/devices.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.devices import (
    adopt_device,
    execute_port_action,
    get_device_details,
    get_device_statistics,
    list_devices_by_type,
    list_pending_devices,
    search_devices,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "cloud-ea"
    settings.base_url = "https://api.ui.com"
    settings.api_key = "test-key"
    return settings


def create_mock_client(mock_response):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.authenticate = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


DEVICE_ID_1 = "507f1f77bcf86cd799439011"
DEVICE_ID_2 = "507f1f77bcf86cd799439022"
DEVICE_ID_3 = "507f1f77bcf86cd799439033"


def make_device(
    device_id=DEVICE_ID_1, name="Test Device", device_type="uap", model="U7-Pro", state=1
):
    return {
        "_id": device_id,
        "name": name,
        "type": device_type,
        "model": model,
        "mac": "00:11:22:33:44:55",
        "ip": "192.168.2.100",
        "state": state,
        "uptime": 86400,
        "cpu": 15.5,
        "mem": 45.2,
        "tx_bytes": 1000000,
        "rx_bytes": 2000000,
        "bytes": 3000000,
        "uplink_depth": 1,
    }


class TestGetDeviceDetails:
    @pytest.mark.asyncio
    async def test_get_device_details_success(self, mock_settings):
        mock_response = {"data": [make_device(DEVICE_ID_1, "AP-Living")]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_device_details("site-1", DEVICE_ID_1, mock_settings)

            assert result["id"] == DEVICE_ID_1
            assert result["name"] == "AP-Living"

    @pytest.mark.asyncio
    async def test_get_device_details_list_response(self, mock_settings):
        mock_response = [make_device(DEVICE_ID_2, "Switch-Main")]

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_device_details("site-1", DEVICE_ID_2, mock_settings)

            assert result["id"] == DEVICE_ID_2
            assert result["name"] == "Switch-Main"

    @pytest.mark.asyncio
    async def test_get_device_details_not_found(self, mock_settings):
        mock_response = {"data": [make_device(DEVICE_ID_1)]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            with pytest.raises(ResourceNotFoundError):
                await get_device_details("site-1", DEVICE_ID_3, mock_settings)

    @pytest.mark.asyncio
    async def test_get_device_details_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_device_details("", DEVICE_ID_1, mock_settings)

    @pytest.mark.asyncio
    async def test_get_device_details_invalid_device_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_device_details("site-1", "", mock_settings)


class TestGetDeviceStatistics:
    @pytest.mark.asyncio
    async def test_get_device_statistics_success(self, mock_settings):
        device = make_device(DEVICE_ID_1)
        mock_response = {"data": [device]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_device_statistics("site-1", DEVICE_ID_1, mock_settings)

            assert result["device_id"] == DEVICE_ID_1
            assert result["uptime"] == 86400
            assert result["cpu"] == 15.5
            assert result["mem"] == 45.2
            assert result["tx_bytes"] == 1000000
            assert result["rx_bytes"] == 2000000
            assert result["state"] == 1

    @pytest.mark.asyncio
    async def test_get_device_statistics_list_response(self, mock_settings):
        device = make_device(DEVICE_ID_2)
        mock_response = [device]

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_device_statistics("site-1", DEVICE_ID_2, mock_settings)

            assert result["device_id"] == DEVICE_ID_2

    @pytest.mark.asyncio
    async def test_get_device_statistics_not_found(self, mock_settings):
        mock_response = {"data": [make_device(DEVICE_ID_1)]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            with pytest.raises(ResourceNotFoundError):
                await get_device_statistics("site-1", DEVICE_ID_3, mock_settings)

    @pytest.mark.asyncio
    async def test_get_device_statistics_missing_fields(self, mock_settings):
        device = {"_id": DEVICE_ID_1, "name": "Minimal", "type": "uap", "mac": "aa:bb:cc:dd:ee:ff"}
        mock_response = {"data": [device]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_device_statistics("site-1", DEVICE_ID_1, mock_settings)

            assert result["device_id"] == DEVICE_ID_1
            assert result["uptime"] == 0
            assert result["tx_bytes"] == 0
            assert result["rx_bytes"] == 0


class TestListDevicesByType:
    @pytest.mark.asyncio
    async def test_list_devices_by_type_success(self, mock_settings):
        mock_response = {
            "data": [
                make_device("ap-1", "AP-1", device_type="uap"),
                make_device("sw-1", "Switch-1", device_type="usw"),
                make_device("ap-2", "AP-2", device_type="uap"),
            ]
        }

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_devices_by_type("site-1", "uap", mock_settings)

            assert len(result) == 2
            assert all(d["type"] == "uap" for d in result)

    @pytest.mark.asyncio
    async def test_list_devices_by_type_case_insensitive(self, mock_settings):
        mock_response = {"data": [make_device("ap-1", device_type="uap")]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_devices_by_type("site-1", "UAP", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_devices_by_type_match_model(self, mock_settings):
        mock_response = {"data": [make_device("sw-1", device_type="usw", model="USW-Pro-24")]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_devices_by_type("site-1", "pro", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_devices_by_type_with_pagination(self, mock_settings):
        mock_response = {"data": [make_device(f"ap-{i}", device_type="uap") for i in range(10)]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_devices_by_type("site-1", "uap", mock_settings, limit=3, offset=2)

            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_devices_by_type_empty(self, mock_settings):
        mock_response = {"data": [make_device("sw-1", device_type="usw")]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_devices_by_type("site-1", "uap", mock_settings)

            assert result == []


class TestSearchDevices:
    @pytest.mark.asyncio
    async def test_search_devices_by_name(self, mock_settings):
        mock_response = {
            "data": [
                make_device("ap-1", "Office AP"),
                make_device("ap-2", "Living Room AP"),
            ]
        }

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await search_devices("site-1", "office", mock_settings)

            assert len(result) == 1
            assert result[0]["name"] == "Office AP"

    @pytest.mark.asyncio
    async def test_search_devices_by_mac(self, mock_settings):
        device = make_device("ap-1")
        device["mac"] = "aa:bb:cc:dd:ee:ff"
        mock_response = {"data": [device]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await search_devices("site-1", "aa:bb", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_devices_by_ip(self, mock_settings):
        device = make_device("ap-1")
        device["ip"] = "192.168.10.50"
        mock_response = {"data": [device]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await search_devices("site-1", "192.168.10", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_devices_by_model(self, mock_settings):
        mock_response = {
            "data": [
                make_device("ap-1", model="U7-Pro"),
                make_device("sw-1", model="USW-Lite"),
            ]
        }

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await search_devices("site-1", "u7", mock_settings)

            assert len(result) == 1
            assert result[0]["model"] == "U7-Pro"

    @pytest.mark.asyncio
    async def test_search_devices_with_pagination(self, mock_settings):
        mock_response = {"data": [make_device(f"ap-{i}", f"AP-{i}") for i in range(10)]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await search_devices("site-1", "ap", mock_settings, limit=5)

            assert len(result) == 5

    @pytest.mark.asyncio
    async def test_search_devices_no_match(self, mock_settings):
        mock_response = {"data": [make_device("ap-1", "Office AP")]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await search_devices("site-1", "nonexistent", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_search_devices_list_response(self, mock_settings):
        mock_response = [make_device("ap-1", "Test AP")]

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await search_devices("site-1", "test", mock_settings)

            assert len(result) == 1


class TestListPendingDevices:
    @pytest.mark.asyncio
    async def test_list_pending_devices_success(self, mock_settings):
        mock_response = {
            "data": [
                make_device("pending-1", "New AP"),
                make_device("pending-2", "New Switch"),
            ]
        }

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client(mock_response)
            mock_client_class.return_value = mock_client

            result = await list_pending_devices("site-1", mock_settings)

            assert len(result) == 2
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_pending_devices_empty(self, mock_settings):
        mock_response = {"data": []}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_pending_devices("site-1", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_pending_devices_with_pagination(self, mock_settings):
        mock_response = {"data": [make_device()]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client(mock_response)
            mock_client_class.return_value = mock_client

            await list_pending_devices("site-1", mock_settings, limit=10, offset=5)

            call_args = mock_client.get.call_args
            assert call_args[1]["params"]["limit"] == 10
            assert call_args[1]["params"]["offset"] == 5

    @pytest.mark.asyncio
    async def test_list_pending_devices_limit_only(self, mock_settings):
        mock_response = {"data": [make_device()]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client(mock_response)
            mock_client_class.return_value = mock_client

            await list_pending_devices("site-1", mock_settings, limit=25)

            call_args = mock_client.get.call_args
            assert call_args[1]["params"]["limit"] == 25


class TestAdoptDevice:
    @pytest.mark.asyncio
    async def test_adopt_device_success(self, mock_settings):
        mock_response = {"data": make_device(DEVICE_ID_1, "Adopted AP")}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            with patch("src.tools.devices.audit_action", new_callable=AsyncMock) as mock_audit:
                mock_client = create_mock_client(mock_response)
                mock_client_class.return_value = mock_client

                result = await adopt_device(
                    "site-1", DEVICE_ID_1, mock_settings, name="My AP", confirm=True
                )

                assert result["id"] == DEVICE_ID_1
                mock_client.post.assert_called_once()
                mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_adopt_device_dry_run(self, mock_settings):
        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client({})
            mock_client_class.return_value = mock_client

            result = await adopt_device(
                "site-1", DEVICE_ID_1, mock_settings, name="My AP", confirm=True, dry_run=True
            )

            assert result["dry_run"] is True
            assert result["device_id"] == DEVICE_ID_1
            assert result["payload"]["name"] == "My AP"
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_adopt_device_no_confirm(self, mock_settings):
        with pytest.raises(ValidationError, match="requires confirmation"):
            await adopt_device("site-1", DEVICE_ID_1, mock_settings)

    @pytest.mark.asyncio
    async def test_adopt_device_no_name(self, mock_settings):
        mock_response = {"data": make_device(DEVICE_ID_1)}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            with patch("src.tools.devices.audit_action", new_callable=AsyncMock):
                mock_client = create_mock_client(mock_response)
                mock_client_class.return_value = mock_client

                result = await adopt_device("site-1", DEVICE_ID_1, mock_settings, confirm=True)

                assert result["id"] == DEVICE_ID_1
                call_args = mock_client.post.call_args
                assert call_args[1]["json_data"] == {}


class TestExecutePortAction:
    @pytest.mark.asyncio
    async def test_execute_port_action_success(self, mock_settings):
        mock_response = {"data": {"status": "ok"}}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            with patch("src.tools.devices.audit_action", new_callable=AsyncMock) as mock_audit:
                mock_client = create_mock_client(mock_response)
                mock_client_class.return_value = mock_client

                result = await execute_port_action(
                    "site-1", DEVICE_ID_1, 1, "power-cycle", mock_settings, confirm=True
                )

                assert result["success"] is True
                assert result["action"] == "power-cycle"
                assert result["port_idx"] == 1
                mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_port_action_dry_run(self, mock_settings):
        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client({})
            mock_client_class.return_value = mock_client

            result = await execute_port_action(
                "site-1", DEVICE_ID_1, 2, "disable", mock_settings, confirm=True, dry_run=True
            )

            assert result["dry_run"] is True
            assert result["port_idx"] == 2
            assert result["payload"]["action"] == "disable"
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_port_action_no_confirm(self, mock_settings):
        with pytest.raises(ValidationError, match="requires confirmation"):
            await execute_port_action("site-1", DEVICE_ID_1, 1, "enable", mock_settings)

    @pytest.mark.asyncio
    async def test_execute_port_action_with_params(self, mock_settings):
        mock_response = {"data": {"status": "ok"}}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            with patch("src.tools.devices.audit_action", new_callable=AsyncMock):
                mock_client = create_mock_client(mock_response)
                mock_client_class.return_value = mock_client

                await execute_port_action(
                    "site-1",
                    DEVICE_ID_1,
                    3,
                    "power-cycle",
                    mock_settings,
                    params={"delay": 5},
                    confirm=True,
                )

                call_args = mock_client.post.call_args
                assert call_args[1]["json_data"]["params"] == {"delay": 5}
