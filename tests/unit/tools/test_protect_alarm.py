"""Unit tests for UniFi Protect arm profile and alarm tools (Protect v7 surface)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_alarm
from src.tools.protect_alarm import (
    create_protect_arm_profile,
    delete_protect_arm_profile,
    disable_protect_alarm,
    enable_protect_alarm,
    get_protect_arm_profile,
    list_protect_arm_profiles,
    set_current_protect_arm_profile,
    update_protect_arm_profile,
)
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.get_protect_integration_path = MagicMock(
        side_effect=lambda endpoint: f"/integration/v1/{endpoint.lstrip('/')}"
    )
    return settings


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.patch = AsyncMock()
    client.delete = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


SCHEDULES = [{"mode": "away", "startCron": "0 22 * * *", "endCron": "0 6 * * *"}]

CREATE_KWARGS = {
    "name": "Night",
    "automations": ["auto-1"],
    "schedules": SCHEDULES,
    "record_everything": True,
    "activation_delay": 60000,
}

CREATE_PAYLOAD = {
    "name": "Night",
    "automations": ["auto-1"],
    "schedules": [{"mode": "away", "startCron": "0 22 * * *", "endCron": "0 6 * * *"}],
    "recordEverything": True,
    "activationDelay": 60000,
}


# --- Read paths -------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_protect_arm_profiles_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(
        return_value={"count": 2, "totalCount": 2, "data": [
            {"id": "profile-1", "name": "Night", "recordEverything": True},
            {"id": "profile-2", "name": "Day", "recordEverything": False},
        ]}
    )
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await list_protect_arm_profiles(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/arm-profiles", params={"limit": 10, "offset": 0}
    )
    assert result["count"] == 2
    assert result["data"][0]["id"] == "profile-1"


@pytest.mark.asyncio
async def test_get_protect_arm_profile_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"id": "profile-1", "name": "Night"})
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await get_protect_arm_profile("profile-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/arm-profiles/profile-1")
    assert result["id"] == "profile-1"


# --- Write gates ------------------------------------------------------------

WRITES = [
    ("create_protect_arm_profile", dict(CREATE_KWARGS)),
    ("update_protect_arm_profile", {"arm_profile_id": "profile-1", "name": "x"}),
    ("delete_protect_arm_profile", {"arm_profile_id": "profile-1"}),
    ("set_current_protect_arm_profile", {"arm_profile_id": "profile-1"}),
    ("enable_protect_alarm", {}),
    ("disable_protect_alarm", {}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[n for n, _ in WRITES])
async def test_write_refused_without_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_alarm.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_alarm, name)(settings=mock_settings, **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[f"{n}-strfalse" for n, _ in WRITES])
async def test_write_refused_with_string_false_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_alarm.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_alarm, name)(
                settings=mock_settings, confirm="false", **kwargs
            )
        client_cls.assert_not_called()


# --- create -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_protect_arm_profile_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(
        return_value={"id": "profile-1", "name": "Night", "activationDelay": 60000}
    )
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await create_protect_arm_profile(
            mock_settings, confirm=True, **CREATE_KWARGS
        )
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/arm-profiles", json_data=CREATE_PAYLOAD
    )
    assert result["id"] == "profile-1"


@pytest.mark.asyncio
async def test_create_protect_arm_profile_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await create_protect_arm_profile(
            mock_settings, confirm=True, dry_run=True, **CREATE_KWARGS
        )
    assert result["dry_run"] is True
    assert result["operation"] == "create_protect_arm_profile"
    assert result["payload"] == CREATE_PAYLOAD
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_protect_arm_profile_validates_activation_delay(
    mock_settings, mock_client
):
    with pytest.raises(ValidationError):
        await create_protect_arm_profile(
            mock_settings, confirm=True, activation_delay=30000, **{
                k: v for k, v in CREATE_KWARGS.items() if k != "activation_delay"
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("delay", [0, 60000, 300000, 600000])
async def test_create_protect_arm_profile_allowed_activation_delays(
    mock_settings, mock_client, delay
):
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await create_protect_arm_profile(
            mock_settings, confirm=True, dry_run=True, activation_delay=delay, **{
                k: v for k, v in CREATE_KWARGS.items() if k != "activation_delay"
            }
        )
    assert result["payload"]["activationDelay"] == delay


# --- update -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_protect_arm_profile_success(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"id": "profile-1", "name": "New Name"})
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await update_protect_arm_profile(
            "profile-1", mock_settings, name="New Name", confirm=True
        )
    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/arm-profiles/profile-1", json_data={"name": "New Name"}
    )
    assert result["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_protect_arm_profile_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await update_protect_arm_profile(
            "profile-1", mock_settings, record_everything=False, confirm=True, dry_run=True
        )
    assert result["dry_run"] is True
    assert result["arm_profile_id"] == "profile-1"
    assert result["payload"] == {"recordEverything": False}
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_arm_profile_sends_camel_case(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"id": "profile-1"})
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        await update_protect_arm_profile(
            "profile-1",
            mock_settings,
            schedules=SCHEDULES,
            activation_delay=300000,
            confirm=True,
        )
    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/arm-profiles/profile-1",
        json_data={
            "schedules": [
                {"mode": "away", "startCron": "0 22 * * *", "endCron": "0 6 * * *"}
            ],
            "activationDelay": 300000,
        },
    )


@pytest.mark.asyncio
async def test_update_protect_arm_profile_requires_a_field(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_arm_profile("profile-1", mock_settings, confirm=True)


@pytest.mark.asyncio
async def test_update_protect_arm_profile_validates_activation_delay(
    mock_settings, mock_client
):
    with pytest.raises(ValidationError):
        await update_protect_arm_profile(
            "profile-1", mock_settings, activation_delay=15000, confirm=True
        )


# --- delete -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_protect_arm_profile_success(mock_settings, mock_client):
    mock_client.delete = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await delete_protect_arm_profile("profile-1", mock_settings, confirm=True)
    mock_client.delete.assert_awaited_once_with("/integration/v1/arm-profiles/profile-1")
    assert result == {"success": True, "arm_profile_id": "profile-1"}


@pytest.mark.asyncio
async def test_delete_protect_arm_profile_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await delete_protect_arm_profile(
            "profile-1", mock_settings, confirm=True, dry_run=True
        )
    assert result["dry_run"] is True
    assert result["arm_profile_id"] == "profile-1"
    mock_client.delete.assert_not_called()


# --- set current profile ------------------------------------------------------


@pytest.mark.asyncio
async def test_set_current_protect_arm_profile_success(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await set_current_protect_arm_profile(
            mock_settings, "profile-1", confirm=True
        )
    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/arm-profiles/settings", json_data={"armProfileId": "profile-1"}
    )
    assert result["success"] is True
    assert result["arm_profile_id"] == "profile-1"


@pytest.mark.asyncio
async def test_set_current_protect_arm_profile_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await set_current_protect_arm_profile(
            mock_settings, "profile-1", confirm=True, dry_run=True
        )
    assert result["dry_run"] is True
    assert result["payload"] == {"armProfileId": "profile-1"}
    mock_client.patch.assert_not_called()


# --- enable / disable ----------------------------------------------------------


@pytest.mark.asyncio
async def test_enable_protect_alarm_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await enable_protect_alarm(mock_settings, confirm=True)
    mock_client.post.assert_awaited_once_with("/integration/v1/arm-profiles/enable")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_enable_protect_alarm_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await enable_protect_alarm(mock_settings, confirm=True, dry_run=True)
    assert result["dry_run"] is True
    assert result["operation"] == "enable_protect_alarm"
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_disable_protect_alarm_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await disable_protect_alarm(mock_settings, confirm=True)
    mock_client.post.assert_awaited_once_with("/integration/v1/arm-profiles/disable")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_disable_protect_alarm_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_alarm.ProtectClient", return_value=mock_client):
        result = await disable_protect_alarm(mock_settings, confirm=True, dry_run=True)
    assert result["dry_run"] is True
    assert result["operation"] == "disable_protect_alarm"
    mock_client.post.assert_not_called()


# --- Input validation ----------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_arm_profile_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await get_protect_arm_profile("   ", mock_settings)


@pytest.mark.asyncio
async def test_delete_empty_arm_profile_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await delete_protect_arm_profile("   ", mock_settings, confirm=True)


@pytest.mark.asyncio
async def test_set_current_empty_arm_profile_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await set_current_protect_arm_profile(mock_settings, "   ", confirm=True)
