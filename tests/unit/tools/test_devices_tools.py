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

# The integration API keys devices by UUID, not by the legacy ObjectId above.
DEVICE_UUID_1 = "b12257d4-d910-3b09-bcf9-e842229ac697"
DEVICE_UUID_2 = "c33f1a92-7e41-4a0d-9a55-1de6f0b2c841"


def make_integration_device(device_id=DEVICE_UUID_1, name="Test Device"):
    """Build a device exactly as ``/integration/v1/sites/{site}/devices`` returns it.

    Note the differences from the legacy ``/ea/`` shape in ``make_device``:
    ``macAddress`` instead of ``mac``, a string ``state``, no ``type`` key, and
    ``features`` / ``interfaces`` as objects rather than lists of strings.

    Args:
        device_id: Integration-API UUID to report as ``id``
        name: Device display name

    Returns:
        A device record in the integration API's shape
    """
    return {
        "id": device_id,
        "name": name,
        "model": "U7-Pro-Wall",
        "macAddress": "1c:6a:1b:5b:c7:85",
        "ipAddress": "192.168.1.185",
        "state": "ONLINE",
        "supported": True,
        "firmwareVersion": "8.6.11.18870",
        "firmwareUpdatable": False,
        "adoptedAt": "2025-10-04T10:00:00Z",
        "features": {"accessPoint": {}},
        "interfaces": {
            "ports": [],
            "radios": [{"frequencyGHz": 5, "channelWidthMHz": 320, "channel": 53}],
        },
    }


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
        mock_response = {"data": [make_integration_device(DEVICE_UUID_1, "AP-Living")]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_device_details("site-1", DEVICE_UUID_1, mock_settings)

            assert result["id"] == DEVICE_UUID_1
            assert result["name"] == "AP-Living"

    @pytest.mark.asyncio
    async def test_get_device_details_list_response(self, mock_settings):
        mock_response = [make_integration_device(DEVICE_UUID_2, "Switch-Main")]

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_device_details("site-1", DEVICE_UUID_2, mock_settings)

            assert result["id"] == DEVICE_UUID_2
            assert result["name"] == "Switch-Main"

    @pytest.mark.asyncio
    async def test_get_device_details_parses_real_integration_payload(self, mock_settings):
        """The integration API shape must validate — see issue #108.

        It reports ``macAddress`` rather than ``mac``, a string ``state`` rather
        than the legacy integer, no ``type`` at all, and ``features`` /
        ``interfaces`` as objects rather than lists. Every one of those used to
        raise because the response was parsed with the legacy ``Device`` model.
        """
        device = make_integration_device(DEVICE_UUID_1, "2p ap 2")

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(device)

            result = await get_device_details("site-1", DEVICE_UUID_1, mock_settings)

        assert result["mac_address"] == "1c:6a:1b:5b:c7:85"
        assert result["state"] == "ONLINE"
        assert result["firmware_version"] == "8.6.11.18870"
        assert result["interfaces"]["radios"][0]["channel"] == 53
        assert result["features"] == {"accessPoint": {}}
        # Unmodelled keys survive via extra="allow" rather than being dropped
        assert result["adoptedAt"] == "2025-10-04T10:00:00Z"

    @pytest.mark.asyncio
    async def test_get_device_details_omits_unreported_fields(self, mock_settings):
        """Absent keys are omitted, not returned as null — same rule as #103."""
        sparse = {"id": DEVICE_UUID_1, "name": "Sparse AP"}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(sparse)

            result = await get_device_details("site-1", DEVICE_UUID_1, mock_settings)

        assert result == {"id": DEVICE_UUID_1, "name": "Sparse AP"}

    @pytest.mark.asyncio
    async def test_get_device_details_accepts_legacy_id_key(self, mock_settings):
        """A legacy ``_id`` record still resolves, per the documented fallback."""
        legacy = {"_id": DEVICE_ID_1, "name": "Legacy AP", "mac": "00:11:22:33:44:55"}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client({"data": [legacy]})

            result = await get_device_details("site-1", DEVICE_ID_1, mock_settings)

        assert result["id"] == DEVICE_ID_1
        assert result["mac"] == "00:11:22:33:44:55"

    @pytest.mark.asyncio
    async def test_get_device_details_not_found(self, mock_settings):
        mock_response = {"data": [make_integration_device(DEVICE_UUID_1)]}

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
    """Pending devices come from the legacy stat route (see #101).

    The Integration v1 API has no /devices/pending: the path matches
    /devices/{deviceId} and 400s. Unadopted devices only appear on
    ``stat/device``, flagged ``adopted: false``.
    """

    @pytest.mark.asyncio
    async def test_list_pending_devices_success(self, mock_settings):
        mock_response = {
            "data": [
                {**make_device("pending-1", "New AP"), "adopted": False},
                {**make_device("adopted-1", "Existing AP"), "adopted": True},
                {**make_device("pending-2", "New Switch"), "adopted": False},
            ]
        }

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client(mock_response)
            mock_client_class.return_value = mock_client

            result = await list_pending_devices("site-1", mock_settings)

            assert len(result) == 2
            assert {d["name"] for d in result} == {"New AP", "New Switch"}
            called_url = mock_client.get.call_args[0][0]
            assert called_url == "/ea/sites/site-1/stat/device"

    @pytest.mark.asyncio
    async def test_list_pending_devices_all_adopted(self, mock_settings):
        """A site with every device adopted has nothing pending."""
        mock_response = {"data": [{**make_device(), "adopted": True}]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_pending_devices("site-1", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_pending_devices_empty(self, mock_settings):
        mock_response = {"data": []}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_pending_devices("site-1", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_pending_devices_with_pagination(self, mock_settings):
        """Pagination is applied client-side, after the adopted filter."""
        mock_response = {
            "data": [
                {**make_device(f"pending-{i}", f"Device {i}"), "adopted": False}
                for i in range(1, 4)
            ]
        }

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client(mock_response)
            mock_client_class.return_value = mock_client

            result = await list_pending_devices("site-1", mock_settings, limit=1, offset=1)

            assert len(result) == 1
            assert result[0]["name"] == "Device 2"


class TestAdoptDevice:
    @pytest.mark.asyncio
    async def test_adopt_device_success(self, mock_settings):
        mock_response = {"data": {"macAddress": "00:11:22:33:44:55", "state": "ADOPTING"}}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            with patch("src.tools.devices.audit_action", new_callable=AsyncMock) as mock_audit:
                mock_client = create_mock_client(mock_response)
                mock_client_class.return_value = mock_client

                result = await adopt_device(
                    "site-1", "00:11:22:33:44:55", mock_settings, confirm=True
                )

                assert result["success"] is True
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "/integration/v1/sites/site-1/devices"
                assert call_args[1]["json_data"] == {
                    "macAddress": "00:11:22:33:44:55",
                    "ignoreDeviceLimit": False,
                }
                mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_adopt_device_dry_run(self, mock_settings):
        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client({})
            mock_client_class.return_value = mock_client

            result = await adopt_device(
                "site-1", "00:11:22:33:44:55", mock_settings, confirm=True, dry_run=True
            )

            assert result["dry_run"] is True
            assert result["mac"] == "00:11:22:33:44:55"
            assert result["payload"] == {
                "macAddress": "00:11:22:33:44:55",
                "ignoreDeviceLimit": False,
            }
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_adopt_device_no_confirm(self, mock_settings):
        with pytest.raises(ValidationError, match="requires confirmation"):
            await adopt_device("site-1", DEVICE_ID_1, mock_settings)

    @pytest.mark.asyncio
    async def test_adopt_device_ignore_device_limit(self, mock_settings):
        mock_response = {"data": {"macAddress": "00:11:22:33:44:55"}}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            with patch("src.tools.devices.audit_action", new_callable=AsyncMock):
                mock_client = create_mock_client(mock_response)
                mock_client_class.return_value = mock_client

                await adopt_device(
                    "site-1",
                    "00:11:22:33:44:55",
                    mock_settings,
                    ignore_device_limit=True,
                    confirm=True,
                )

                call_args = mock_client.post.call_args
                assert call_args[1]["json_data"]["ignoreDeviceLimit"] is True

    @pytest.mark.asyncio
    async def test_adopt_device_invalid_mac(self, mock_settings):
        with pytest.raises(ValidationError, match="MAC"):
            await adopt_device("site-1", "not-a-mac", mock_settings, confirm=True)


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
                assert result["action"] == "POWER_CYCLE"
                assert result["port_idx"] == 1
                call_args = mock_client.post.call_args
                assert call_args[0][0] == (
                    f"/integration/v1/sites/site-1/devices/{DEVICE_ID_1}"
                    "/interfaces/ports/1/actions"
                )
                assert call_args[1]["json_data"] == {"action": "POWER_CYCLE"}
                mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_port_action_dry_run(self, mock_settings):
        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client = create_mock_client({})
            mock_client_class.return_value = mock_client

            result = await execute_port_action(
                "site-1", DEVICE_ID_1, 2, "power_cycle", mock_settings, confirm=True, dry_run=True
            )

            assert result["dry_run"] is True
            assert result["port_idx"] == 2
            assert result["payload"] == {"action": "POWER_CYCLE"}
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_port_action_no_confirm(self, mock_settings):
        with pytest.raises(ValidationError, match="requires confirmation"):
            await execute_port_action("site-1", DEVICE_ID_1, 1, "enable", mock_settings)

    @pytest.mark.asyncio
    async def test_execute_port_action_unsupported_action(self, mock_settings):
        with pytest.raises(ValidationError, match="unsupported port action"):
            await execute_port_action(
                "site-1", DEVICE_ID_1, 1, "disable", mock_settings, confirm=True
            )

    @pytest.mark.asyncio
    async def test_execute_port_action_params_ignored(self, mock_settings):
        """params is deprecated and never sent (no spec carrier)."""
        mock_response = {"data": {"status": "ok"}}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            with patch("src.tools.devices.audit_action", new_callable=AsyncMock):
                mock_client = create_mock_client(mock_response)
                mock_client_class.return_value = mock_client

                await execute_port_action(
                    "site-1",
                    DEVICE_ID_1,
                    3,
                    "POWER_CYCLE",
                    mock_settings,
                    params={"delay": 5},
                    confirm=True,
                )

                json_data = mock_client.post.call_args[1]["json_data"]
                assert json_data == {"action": "POWER_CYCLE"}
                assert "params" not in json_data


class TestGetDeviceDetailsIdentifierResolution:
    """Issue #183: get_device_details must resolve all three UniFi ID spaces.

    The integration API only keys device records by UUID, so callers passing
    a legacy ``_id`` (or a MAC) got "device not found" for devices that
    existed. UUID, ObjectId, and MAC inputs must all resolve.
    """

    @pytest.mark.asyncio
    async def test_mac_input_resolves_via_mac_address(self, mock_settings):
        device = make_integration_device(DEVICE_UUID_1, "AP-Living")

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            client = create_mock_client({"data": [device]})
            mock_client_class.return_value = client

            result = await get_device_details("site-1", "1C:6A:1B:5B:C7:85", mock_settings)

        assert result["id"] == DEVICE_UUID_1
        # MAC input must skip both the detail route and the legacy ObjectId
        # mapping — a single integration-list call is the whole conversation.
        assert len(client.get.call_args_list) == 1

    @pytest.mark.asyncio
    async def test_objectid_input_resolves_via_legacy_mapping(self, mock_settings):
        from src.utils import APIError

        legacy_id = "689d9f9ef4061b1ea839a6ec"
        device = make_integration_device(DEVICE_UUID_1, "Gateway")

        async def fake_get(endpoint, **kwargs):
            # Integration endpoints come through as MagicMock on the mocked
            # settings — only the legacy f-string path is a real string.
            endpoint = str(endpoint)
            if endpoint.startswith("/ea/sites/"):
                return {"data": [{"_id": legacy_id, "mac": "1c:6a:1b:5b:c7:85"}]}
            if endpoint.rstrip("/").endswith(f"devices/{legacy_id}"):
                raise APIError("not found", status_code=400)
            return {"data": [device]}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            client = create_mock_client({})
            client.get = AsyncMock(side_effect=fake_get)
            mock_client_class.return_value = client

            result = await get_device_details("site-1", legacy_id, mock_settings)

        assert result["id"] == DEVICE_UUID_1
        assert result["name"] == "Gateway"

    @pytest.mark.asyncio
    async def test_invalid_identifier_raises(self, mock_settings):
        from src.utils import ValidationError

        with pytest.raises(ValidationError):
            await get_device_details("site-1", "not-a-real-id", mock_settings)

    @pytest.mark.asyncio
    async def test_unknown_mac_raises_not_found(self, mock_settings):
        from src.utils import ResourceNotFoundError

        device = make_integration_device(DEVICE_UUID_1, "AP-Living")

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client({"data": [device]})

            with pytest.raises(ResourceNotFoundError):
                await get_device_details("site-1", "aa:bb:cc:dd:ee:ff", mock_settings)
