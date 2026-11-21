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
    # The spec declares no query parameters for this route and returns a bare
    # array, so the window is applied locally rather than forwarded.
    mock_client.get.assert_awaited_once_with("/integration/v1/external/arm-profiles")
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


@pytest.mark.asyncio
async def test_list_accepts_a_bare_array(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value=[{"id": "ext-1", "title": "Night", "state": "armed"}])
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await list_protect_external_arm_profiles(mock_settings)
    assert result["count"] == 1
    assert result["data"][0]["id"] == "ext-1"


@pytest.mark.asyncio
async def test_empty_profile_id_is_rejected(mock_settings):
    with pytest.raises(ValidationError, match="arm_profile_id"):
        await get_protect_external_arm_profile("  ", mock_settings)


@pytest.mark.asyncio
async def test_create_includes_schedule_and_deactivation_delay(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"id": "ext-1", "title": "Night"})
    schedule = {"sun": {"type": "intervals", "entries": []}}
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        await create_protect_external_arm_profile(
            mock_settings,
            title="Night",
            deactivation_delay=10,
            schedule=schedule,
            confirm=True,
        )
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/external/arm-profiles",
        json_data={"title": "Night", "deactivation_delay": 10, "schedule": schedule},
    )


@pytest.mark.asyncio
async def test_update_sends_changed_fields(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"id": "ext-1", "title": "Day"})
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await update_protect_external_arm_profile(
            "ext-1",
            mock_settings,
            title="Day",
            deactivation_delay=5,
            schedule={"mon": {"type": "intervals", "entries": []}},
            confirm=True,
        )
    mock_client.patch.assert_awaited_once()
    args, kwargs = mock_client.patch.await_args
    assert args[0] == "/integration/v1/external/arm-profiles/ext-1"
    assert kwargs["json_data"]["title"] == "Day"
    assert kwargs["json_data"]["deactivation_delay"] == 5
    assert result["id"] == "ext-1"


@pytest.mark.asyncio
async def test_update_rejects_empty_title(mock_settings):
    with pytest.raises(ValidationError, match="title"):
        await update_protect_external_arm_profile("ext-1", mock_settings, title="  ", confirm=True)


@pytest.mark.asyncio
async def test_get_unwraps_data_envelope(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"data": {"id": "ext-1", "title": "Night"}})
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await get_protect_external_arm_profile("ext-1", mock_settings)
    assert result["id"] == "ext-1"


def _profiles(count):
    return [
        {"id": f"ext-{index}", "title": f"Profile {index}", "state": "disarmed"}
        for index in range(count)
    ]


@pytest.mark.asyncio
async def test_list_applies_limit_locally(mock_settings, mock_client):
    """Regression: the route ignores query params, so limit must slice locally."""
    mock_client.get = AsyncMock(return_value=_profiles(5))
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await list_protect_external_arm_profiles(mock_settings, limit=2)

    assert [profile["id"] for profile in result["data"]] == ["ext-0", "ext-1"]
    assert result["count"] == 2
    assert result["totalCount"] == 5
    assert result["limit"] == 2


@pytest.mark.asyncio
async def test_list_applies_offset_locally(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value=_profiles(5))
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await list_protect_external_arm_profiles(mock_settings, limit=2, offset=3)

    assert [profile["id"] for profile in result["data"]] == ["ext-3", "ext-4"]
    assert result["count"] == 2
    assert result["totalCount"] == 5
    assert result["offset"] == 3


@pytest.mark.asyncio
async def test_list_never_forwards_pagination_query_params(mock_settings, mock_client):
    """Regression: forwarding limit/offset as query params is what broke paging."""
    mock_client.get = AsyncMock(return_value=_profiles(3))
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        await list_protect_external_arm_profiles(mock_settings, limit=1, offset=1)

    _, kwargs = mock_client.get.await_args
    assert "params" not in kwargs


@pytest.mark.asyncio
async def test_list_offset_past_the_end_returns_an_empty_page(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value=_profiles(2))
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await list_protect_external_arm_profiles(mock_settings, limit=10, offset=99)

    assert result["data"] == []
    assert result["count"] == 0
    assert result["totalCount"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_id",
    [
        "../../external/arm-profiles",
        "ext-1/../other",
        "ext 1",
        "..",
        "ext-1?limit=100",
        "ext-1#fragment",
    ],
)
async def test_path_traversal_ids_are_rejected(mock_settings, mock_client, bad_id):
    """Regression: profile IDs become one path segment and must stay one."""
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        with pytest.raises(ValidationError, match="arm_profile_id"):
            await get_protect_external_arm_profile(bad_id, mock_settings)
    mock_client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_traversal_id_is_rejected_before_any_write(mock_settings, mock_client):
    """The same guard must hold for the mutating tools, before any request."""
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        with pytest.raises(ValidationError, match="arm_profile_id"):
            await delete_protect_external_arm_profile("../x", mock_settings, confirm=True)
        with pytest.raises(ValidationError, match="arm_profile_id"):
            await arm_protect_external_arm_profile("../x", mock_settings, confirm=True)
        with pytest.raises(ValidationError, match="arm_profile_id"):
            await disarm_protect_external_arm_profile("../x", mock_settings, confirm=True)
        with pytest.raises(ValidationError, match="arm_profile_id"):
            await update_protect_external_arm_profile(
                "../x", mock_settings, title="x", confirm=True
            )
    mock_client.delete.assert_not_awaited()
    mock_client.post.assert_not_awaited()
    mock_client.patch.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_valid_profile_id_still_reaches_the_path(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value=PROFILE)
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        await get_protect_external_arm_profile("ext-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/external/arm-profiles/ext-1")


@pytest.mark.asyncio
async def test_list_tolerates_a_response_that_is_not_a_collection(mock_settings, mock_client):
    """A non-list, non-envelope body yields an empty page rather than raising."""
    mock_client.get = AsyncMock(return_value="NOT_FOUND")
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await list_protect_external_arm_profiles(mock_settings)

    assert result["data"] == []
    assert result["count"] == 0
    assert result["totalCount"] == 0


@pytest.mark.asyncio
async def test_get_tolerates_a_body_that_is_not_a_record(mock_settings, mock_client):
    """A body that is neither a record nor an envelope yields a null-field profile.

    This is the pre-existing contract of the model dump, not a change made
    here: the tool must not raise on an unexpected body.
    """
    mock_client.get = AsyncMock(return_value=["unexpected"])
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await get_protect_external_arm_profile("ext-1", mock_settings)

    assert isinstance(result, dict)
    assert result.get("id") is None


@pytest.mark.asyncio
async def test_get_unwraps_a_data_envelope_around_a_record(mock_settings, mock_client):
    """A data envelope holding one record is unwrapped to that record."""
    mock_client.get = AsyncMock(return_value={"data": PROFILE})
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await get_protect_external_arm_profile("ext-1", mock_settings)

    assert result["id"] == "ext-1"


@pytest.mark.asyncio
async def test_get_of_a_bare_non_record_body_yields_a_null_field_profile(
    mock_settings, mock_client
):
    """A body that is not a mapping yields a null-field profile, not a crash."""
    mock_client.get = AsyncMock(return_value=42)
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await get_protect_external_arm_profile("ext-1", mock_settings)

    assert isinstance(result, dict)
    assert result.get("id") is None


@pytest.mark.asyncio
async def test_get_of_an_envelope_whose_data_is_not_a_record(mock_settings, mock_client):
    """A data envelope holding a non-record is passed through, not unwrapped."""
    mock_client.get = AsyncMock(return_value={"data": ["x"]})
    with patch("src.tools.protect_external_arm.ProtectClient", return_value=mock_client):
        result = await get_protect_external_arm_profile("ext-1", mock_settings)

    assert isinstance(result, dict)


def test_serialize_profile_of_a_non_mapping_yields_an_empty_dict():
    """The defensive branch in _serialize_profile returns {} rather than raising."""
    from src.tools.protect_external_arm import _serialize_profile

    assert _serialize_profile(["not-a-record"]) == {}
