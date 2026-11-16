"""Unit tests for UniFi Protect external arm profile tools (Protect 7.4.96)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_external_arm
from src.tools.protect_external_arm import (
    arm_protect_external_arm_profile,
    create_protect_external_arm_profile,
    delete_protect_external_arm_profile,
    disarm_protect_external_arm_profile,
    get_protect_external_arm_profile,
    list_protect_external_arm_profiles,
    update_protect_external_arm_profile,
)
from src.utils.exceptions import ValidationError

PROFILE = {
    "id": "ext-1",
    "title": "Night",
    "alarm_ids": ["a1"],
    "created_at": "2026-11-11T00:00:00Z",
    "state": "disarmed",
    "has_pin": True,
    "pin": "should-not-leak",
    "pinCode": "also-secret",
}


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


@pytest.mark.asyncio
async def test_list_strips_pin_fields(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"count": 1, "totalCount": 1, "data": [PROFILE]})
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await list_protect_external_arm_profiles(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/external/arm-profiles", params={"limit": 10, "offset": 0}
    )
    assert result["data"][0]["id"] == "ext-1"
    assert result["data"][0]["has_pin"] is True or result["data"][0].get("hasPin") is True
    dumped = str(result)
    assert "should-not-leak" not in dumped
    assert "also-secret" not in dumped
    assert "pin" not in result["data"][0] or result["data"][0].get("pin") is None


@pytest.mark.asyncio
async def test_get_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value=PROFILE)
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await get_protect_external_arm_profile("ext-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/external/arm-profiles/ext-1")
    assert result["id"] == "ext-1"
    assert "should-not-leak" not in str(result)


WRITES = [
    ("create_protect_external_arm_profile", {"title": "Night"}),
    ("update_protect_external_arm_profile", {"arm_profile_id": "ext-1", "title": "Day"}),
    ("delete_protect_external_arm_profile", {"arm_profile_id": "ext-1"}),
    ("arm_protect_external_arm_profile", {"arm_profile_id": "ext-1"}),
    ("disarm_protect_external_arm_profile", {"arm_profile_id": "ext-1"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[n for n, _ in WRITES])
async def test_write_refused_without_confirm(mock_settings, name, kwargs):
    with patch("src.tools.protect_external_arm.ProtectClient") as client_cls:
        with pytest.raises(ValidationError, match="confirm"):
            await getattr(protect_external_arm, name)(settings=mock_settings, **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[f"{n}-strfalse" for n, _ in WRITES])
async def test_write_refused_with_string_false_confirm(mock_settings, name, kwargs):
    with patch("src.tools.protect_external_arm.ProtectClient") as client_cls:
        with pytest.raises(ValidationError, match="confirm"):
            await getattr(protect_external_arm, name)(
                settings=mock_settings, confirm="false", **kwargs
            )
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[f"{n}-dry" for n, _ in WRITES])
async def test_dry_run_makes_no_request(mock_settings, name, kwargs):
    with patch("src.tools.protect_external_arm.ProtectClient") as client_cls:
        result = await getattr(protect_external_arm, name)(
            settings=mock_settings, dry_run=True, **kwargs
        )
    assert result["dry_run"] is True
    client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_create_sends_title(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={**PROFILE, "pin": None})
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        await create_protect_external_arm_profile(
            mock_settings, title="Night", activation_delay=30, confirm=True
        )
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/external/arm-profiles",
        json_data={"title": "Night", "activation_delay": 30},
    )


@pytest.mark.asyncio
async def test_create_rejects_empty_title(mock_settings):
    with pytest.raises(ValidationError, match="title"):
        await create_protect_external_arm_profile(mock_settings, title="  ", confirm=True)


@pytest.mark.asyncio
async def test_update_requires_a_field(mock_settings):
    with pytest.raises(ValidationError, match="No updates"):
        await update_protect_external_arm_profile("ext-1", mock_settings, confirm=True)


@pytest.mark.asyncio
async def test_update_rejects_out_of_range_delay(mock_settings):
    with pytest.raises(ValidationError, match="activation_delay"):
        await update_protect_external_arm_profile(
            "ext-1", mock_settings, activation_delay=3601, confirm=True
        )


@pytest.mark.asyncio
async def test_arm_posts_actions_path(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"id": "ext-1", "state": "arming"})
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await arm_protect_external_arm_profile("ext-1", mock_settings, confirm=True)
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/external/arm-profiles/ext-1/actions/arm"
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_disarm_posts_actions_path(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"id": "ext-1", "state": "disarmed"})
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        await disarm_protect_external_arm_profile("ext-1", mock_settings, confirm=True)
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/external/arm-profiles/ext-1/actions/disarm"
    )


@pytest.mark.asyncio
async def test_delete_success(mock_settings, mock_client):
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await delete_protect_external_arm_profile("ext-1", mock_settings, confirm=True)
    mock_client.delete.assert_awaited_once_with("/integration/v1/external/arm-profiles/ext-1")
    assert result == {"success": True, "arm_profile_id": "ext-1"}
