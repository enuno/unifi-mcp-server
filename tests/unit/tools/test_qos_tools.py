"""Tests for QoS (Quality of Service) tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    from src.config import APIType

    settings = MagicMock(spec="Settings")
    settings.log_level = "INFO"
    settings.api_type = APIType.LOCAL
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    settings.get_api_path = MagicMock(side_effect=lambda x: f"/api/{x}")
    return settings


@pytest.fixture
def sample_qos_profiles():
    return [
        {
            "_id": "profile-001",
            "name": "Voice Priority",
            "priority_level": 5,
            "description": "VoIP traffic",
            "dscp_marking": 46,
            "bandwidth_guaranteed_down_kbps": 128,
            "bandwidth_guaranteed_up_kbps": 128,
            "ports": [5060, 5061],
            "protocols": ["udp"],
            "enabled": True,
            "site_id": "default",
            "applications": [],
            "categories": [],
            "preserve_dscp": False,
            "schedule_enabled": False,
            "schedule_days": [],
            "schedule_time_start": None,
            "schedule_time_end": None,
            "proav_protocol": None,
            "proav_multicast_enabled": False,
            "proav_ptp_enabled": False,
        },
        {
            "_id": "profile-002",
            "name": "Video Streaming",
            "priority_level": 4,
            "description": "HD video",
            "dscp_marking": 34,
            "bandwidth_guaranteed_down_kbps": 2500,
            "bandwidth_guaranteed_up_kbps": 2500,
            "ports": [3478, 3479],
            "protocols": ["udp", "tcp"],
            "enabled": True,
            "site_id": "default",
            "applications": [],
            "categories": [],
            "preserve_dscp": False,
            "schedule_enabled": False,
            "schedule_days": [],
            "schedule_time_start": None,
            "schedule_time_end": None,
            "proav_protocol": None,
            "proav_multicast_enabled": False,
            "proav_ptp_enabled": False,
        },
    ]


@pytest.fixture
def sample_traffic_routes():
    return [
        {
            "_id": "route-001",
            "name": "Block External DNS",
            "description": "Block external DNS queries",
            "action": "deny",
            "enabled": True,
            "match_criteria": {
                "destination_port": 53,
                "protocol": "udp",
            },
            "priority": 100,
            "site_id": "default",
        },
        {
            "_id": "route-002",
            "name": "Prioritize VoIP",
            "description": "Mark VoIP with EF",
            "action": "mark",
            "enabled": True,
            "match_criteria": {
                "destination_port": 5060,
                "protocol": "udp",
            },
            "dscp_marking": 46,
            "priority": 50,
            "site_id": "default",
        },
    ]


# ============================================================================
# QoS Profile Management Tests (5 tools)
# ============================================================================


class TestListQoSProfiles:
    @pytest.mark.asyncio
    async def test_list_qos_profiles_success(self, mock_settings, sample_qos_profiles):
        from src.tools.qos import list_qos_profiles

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": sample_qos_profiles})

            result = await list_qos_profiles("default", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Voice Priority"
            assert result[0]["priority_level"] == 5
            assert result[1]["name"] == "Video Streaming"
            assert result[1]["priority_level"] == 4

    @pytest.mark.asyncio
    async def test_list_qos_profiles_empty(self, mock_settings):
        from src.tools.qos import list_qos_profiles

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": []})

            result = await list_qos_profiles("default", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_qos_profiles_pagination(self, mock_settings, sample_qos_profiles):
        from src.tools.qos import list_qos_profiles

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            # Return 5 profiles
            mock_instance.get = AsyncMock(
                return_value={"data": sample_qos_profiles * 3}  # 6 profiles
            )

            # Get first 2
            result = await list_qos_profiles("default", mock_settings, limit=2, offset=0)
            assert len(result) == 2

            # Get next 2
            result = await list_qos_profiles("default", mock_settings, limit=2, offset=2)
            assert len(result) == 2


class TestGetQoSProfile:
    @pytest.mark.asyncio
    async def test_get_qos_profile_success(self, mock_settings, sample_qos_profiles):
        from src.tools.qos import get_qos_profile

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": [sample_qos_profiles[0]]})

            result = await get_qos_profile("default", "profile-001", mock_settings)

            assert result["id"] == "profile-001"
            assert result["name"] == "Voice Priority"

    @pytest.mark.asyncio
    async def test_get_qos_profile_not_found(self, mock_settings):
        from src.tools.qos import get_qos_profile
        from src.utils.exceptions import ValidationError

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": []})

            with pytest.raises(ValidationError, match="not found"):
                await get_qos_profile("default", "nonexistent", mock_settings)


class TestCreateQoSProfile:
    @pytest.mark.asyncio
    async def test_create_qos_profile_success(self, mock_settings):
        from src.tools.qos import create_qos_profile

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "new-profile",
                            "name": "Test Profile",
                            "priority_level": 5,
                            "enabled": True,
                            "site_id": "default",
                            "dscp_marking": 46,
                            "applications": [],
                            "categories": [],
                            "ports": [],
                            "protocols": [],
                            "preserve_dscp": False,
                            "schedule_enabled": False,
                            "schedule_days": [],
                            "schedule_time_start": None,
                            "schedule_time_end": None,
                            "proav_protocol": None,
                            "proav_multicast_enabled": False,
                            "proav_ptp_enabled": False,
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await create_qos_profile(
                    site_id="default",
                    name="Test Profile",
                    priority_level=5,
                    settings=mock_settings,
                    dscp_marking=46,
                    confirm=True,
                )

            assert result["name"] == "Test Profile"
            assert result["priority_level"] == 5

    @pytest.mark.asyncio
    async def test_create_qos_profile_requires_confirmation(self, mock_settings):
        from src.tools.qos import create_qos_profile
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await create_qos_profile(
                site_id="default",
                name="Test",
                priority_level=5,
                settings=mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_create_qos_profile_invalid_priority(self, mock_settings):
        from src.tools.qos import create_qos_profile
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Priority level must be 0-7"):
            await create_qos_profile(
                site_id="default",
                name="Test",
                priority_level=10,  # Invalid
                settings=mock_settings,
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_create_qos_profile_invalid_dscp(self, mock_settings):
        from src.tools.qos import create_qos_profile
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="DSCP marking must be 0-63"):
            await create_qos_profile(
                site_id="default",
                name="Test",
                priority_level=5,
                settings=mock_settings,
                dscp_marking=100,  # Invalid
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_create_qos_profile_dry_run(self, mock_settings):
        from src.tools.qos import create_qos_profile

        result = await create_qos_profile(
            site_id="default",
            name="Test Profile",
            priority_level=5,
            settings=mock_settings,
            dscp_marking=46,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert "profile" in result

    @pytest.mark.asyncio
    async def test_create_qos_profile_with_schedule(self, mock_settings):
        from src.tools.qos import create_qos_profile

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "new-profile",
                            "name": "Scheduled Profile",
                            "priority_level": 5,
                            "enabled": True,
                            "site_id": "default",
                            "schedule_enabled": True,
                            "schedule_days": ["mon", "tue", "wed"],
                            "schedule_time_start": "09:00",
                            "schedule_time_end": "17:00",
                            "applications": [],
                            "categories": [],
                            "ports": [],
                            "protocols": [],
                            "preserve_dscp": False,
                            "proav_protocol": None,
                            "proav_multicast_enabled": False,
                            "proav_ptp_enabled": False,
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await create_qos_profile(
                    site_id="default",
                    name="Scheduled Profile",
                    priority_level=5,
                    settings=mock_settings,
                    schedule_enabled=True,
                    schedule_days=["mon", "tue", "wed"],
                    schedule_time_start="09:00",
                    schedule_time_end="17:00",
                    confirm=True,
                )

            assert result["schedule_enabled"] is True
            assert len(result["schedule_days"]) == 3


class TestUpdateQoSProfile:
    @pytest.mark.asyncio
    async def test_update_qos_profile_success(self, mock_settings, sample_qos_profiles):
        from src.tools.qos import update_qos_profile

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            updated_profile = sample_qos_profiles[0].copy()
            updated_profile["name"] = "Updated Name"
            mock_instance.put = AsyncMock(return_value={"data": [updated_profile]})

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await update_qos_profile(
                    site_id="default",
                    profile_id="profile-001",
                    settings=mock_settings,
                    name="Updated Name",
                    confirm=True,
                )

            assert result["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_qos_profile_requires_confirmation(self, mock_settings):
        from src.tools.qos import update_qos_profile
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await update_qos_profile(
                site_id="default",
                profile_id="profile-001",
                settings=mock_settings,
                name="Updated",
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_update_qos_profile_no_fields(self, mock_settings):
        from src.tools.qos import update_qos_profile
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="No update fields provided"):
            await update_qos_profile(
                site_id="default",
                profile_id="profile-001",
                settings=mock_settings,
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_update_qos_profile_dry_run(self, mock_settings):
        from src.tools.qos import update_qos_profile

        result = await update_qos_profile(
            site_id="default",
            profile_id="profile-001",
            settings=mock_settings,
            name="Updated Name",
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["profile_id"] == "profile-001"


class TestDeleteQoSProfile:
    @pytest.mark.asyncio
    async def test_delete_qos_profile_success(self, mock_settings):
        from src.tools.qos import delete_qos_profile

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.delete = AsyncMock(return_value={})

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await delete_qos_profile(
                    site_id="default",
                    profile_id="profile-001",
                    settings=mock_settings,
                    confirm=True,
                )

            assert result["success"] is True
            assert result["profile_id"] == "profile-001"

    @pytest.mark.asyncio
    async def test_delete_qos_profile_requires_confirmation(self, mock_settings):
        from src.tools.qos import delete_qos_profile
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await delete_qos_profile(
                site_id="default",
                profile_id="profile-001",
                settings=mock_settings,
                confirm=False,
            )


# ============================================================================
# ProAV Profile Management Tests (3 tools)
# ============================================================================


class TestListProAVTemplates:
    @pytest.mark.asyncio
    async def test_list_proav_templates(self, mock_settings):
        from src.tools.qos import list_proav_templates

        result = await list_proav_templates(mock_settings)

        # Should include 7 ProAV + 6 reference profiles
        assert len(result) == 13

        # Check ProAV templates
        protocols = [t.get("protocol") for t in result if "protocol" in t]
        assert "dante" in protocols
        assert "q-sys" in protocols
        assert "sdvoe" in protocols
        assert "avb" in protocols
        assert "ravenna" in protocols
        assert "ndi" in protocols
        assert "smpte-2110" in protocols

        # Check reference profiles
        profile_keys = [t.get("key") for t in result if "key" in t]
        assert "voice-first" in profile_keys
        assert "video-conferencing" in profile_keys
        assert "cloud-gaming" in profile_keys


class TestCreateProAVProfile:
    @pytest.mark.asyncio
    async def test_create_proav_profile_dante(self, mock_settings):
        from src.tools.qos import create_proav_profile

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "dante-profile",
                            "name": "Audinate Dante",
                            "priority_level": 5,
                            "dscp_marking": 46,
                            "enabled": True,
                            "site_id": "default",
                            "applications": [],
                            "categories": [],
                            "ports": [319, 320, 4440, 4444, 4455, 8700, 8800, 14336, 14337, 8019],
                            "protocols": ["udp", "tcp"],
                            "preserve_dscp": False,
                            "schedule_enabled": False,
                            "schedule_days": [],
                            "schedule_time_start": None,
                            "schedule_time_end": None,
                            "proav_protocol": None,
                            "proav_multicast_enabled": False,
                            "proav_ptp_enabled": False,
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await create_proav_profile(
                    site_id="default",
                    protocol="dante",
                    settings=mock_settings,
                    confirm=True,
                )

            assert result["name"] == "Audinate Dante"
            assert result["priority_level"] == 5
            assert result["dscp_marking"] == 46

    @pytest.mark.asyncio
    async def test_create_proav_profile_reference(self, mock_settings):
        from src.tools.qos import create_proav_profile

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "voice-profile",
                            "name": "Voice First",
                            "priority_level": 5,
                            "dscp_marking": 46,
                            "enabled": True,
                            "site_id": "default",
                            "applications": [],
                            "categories": [],
                            "ports": [5060, 5061, 5004, 5005],
                            "protocols": ["udp", "tcp"],
                            "preserve_dscp": False,
                            "schedule_enabled": False,
                            "schedule_days": [],
                            "schedule_time_start": None,
                            "schedule_time_end": None,
                            "proav_protocol": None,
                            "proav_multicast_enabled": False,
                            "proav_ptp_enabled": False,
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await create_proav_profile(
                    site_id="default",
                    protocol="voice-first",
                    settings=mock_settings,
                    confirm=True,
                )

            assert result["name"] == "Voice First"

    @pytest.mark.asyncio
    async def test_create_proav_profile_invalid_protocol(self, mock_settings):
        from src.tools.qos import create_proav_profile
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Unknown protocol"):
            await create_proav_profile(
                site_id="default",
                protocol="invalid-protocol",
                settings=mock_settings,
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_create_proav_profile_with_customizations(self, mock_settings):
        from src.tools.qos import create_proav_profile

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "custom-dante",
                            "name": "Custom Dante",
                            "priority_level": 5,
                            "dscp_marking": 40,  # Customized
                            "enabled": True,
                            "site_id": "default",
                            "applications": [],
                            "categories": [],
                            "ports": [5000, 5001],  # Custom ports
                            "protocols": [],
                            "preserve_dscp": False,
                            "schedule_enabled": False,
                            "schedule_days": [],
                            "schedule_time_start": None,
                            "schedule_time_end": None,
                            "proav_protocol": None,
                            "proav_multicast_enabled": False,
                            "proav_ptp_enabled": False,
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await create_proav_profile(
                    site_id="default",
                    protocol="dante",
                    settings=mock_settings,
                    name="Custom Dante",
                    customize_dscp=40,
                    customize_ports=[5000, 5001],
                    confirm=True,
                )

            assert result["name"] == "Custom Dante"
            assert result["dscp_marking"] == 40


class TestValidateProAVProfile:
    @pytest.mark.asyncio
    async def test_validate_proav_profile_success(self, mock_settings):
        from src.tools.qos import validate_proav_profile

        result = await validate_proav_profile(
            protocol="dante",
            settings=mock_settings,
            bandwidth_mbps=100,  # Sufficient
        )

        assert result["valid"] is True
        assert result["protocol"] == "dante"
        assert len(result["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_validate_proav_profile_insufficient_bandwidth(self, mock_settings):
        from src.tools.qos import validate_proav_profile

        result = await validate_proav_profile(
            protocol="smpte-2110",  # Requires 3000 Mbps
            settings=mock_settings,
            bandwidth_mbps=1000,  # Insufficient
        )

        assert result["valid"] is False
        assert len(result["warnings"]) > 0
        assert any("bandwidth" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_validate_proav_profile_invalid_protocol(self, mock_settings):
        from src.tools.qos import validate_proav_profile
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Unknown ProAV protocol"):
            await validate_proav_profile(
                protocol="invalid",
                settings=mock_settings,
            )


# ============================================================================
# Smart Queue Management Tests (3 tools)
# ============================================================================


class TestGetSmartQueueConfig:
    @pytest.mark.asyncio
    async def test_get_smart_queue_config_success(self, mock_settings):
        from src.tools.qos import get_smart_queue_config

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "wan-001",
                            "sqm_enabled": True,
                            "sqm_algorithm": "fq_codel",
                            "sqm_download_kbps": 95000,
                            "sqm_upload_kbps": 9500,
                            "sqm_overhead_bytes": 44,
                        }
                    ]
                }
            )

            result = await get_smart_queue_config("default", mock_settings)

            assert result["enabled"] is True
            assert result["algorithm"] == "fq_codel"
            assert result["download_kbps"] == 95000

    @pytest.mark.asyncio
    async def test_get_smart_queue_config_no_wan(self, mock_settings):
        from src.tools.qos import get_smart_queue_config
        from src.utils.exceptions import ValidationError

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": []})

            with pytest.raises(ValidationError, match="No WAN configuration found"):
                await get_smart_queue_config("default", mock_settings)


class TestConfigureSmartQueue:
    @pytest.mark.asyncio
    async def test_configure_smart_queue_success(self, mock_settings):
        from src.tools.qos import configure_smart_queue

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.put = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "wan-001",
                            "sqm_enabled": True,
                            "sqm_algorithm": "fq_codel",
                            "sqm_download_kbps": 95000,
                            "sqm_upload_kbps": 9500,
                            "sqm_overhead_bytes": 44,
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await configure_smart_queue(
                    site_id="default",
                    wan_id="wan-001",
                    download_kbps=95000,
                    upload_kbps=9500,
                    settings=mock_settings,
                    confirm=True,
                )

            assert result["success"] is True
            assert "config" in result

    @pytest.mark.asyncio
    async def test_configure_smart_queue_requires_confirmation(self, mock_settings):
        from src.tools.qos import configure_smart_queue
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await configure_smart_queue(
                site_id="default",
                wan_id="wan-001",
                download_kbps=95000,
                upload_kbps=9500,
                settings=mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_configure_smart_queue_invalid_bandwidth(self, mock_settings):
        from src.tools.qos import configure_smart_queue
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Bandwidth must be greater than 0"):
            await configure_smart_queue(
                site_id="default",
                wan_id="wan-001",
                download_kbps=0,  # Invalid
                upload_kbps=9500,
                settings=mock_settings,
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_configure_smart_queue_invalid_algorithm(self, mock_settings):
        from src.tools.qos import configure_smart_queue
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Invalid algorithm"):
            await configure_smart_queue(
                site_id="default",
                wan_id="wan-001",
                download_kbps=95000,
                upload_kbps=9500,
                settings=mock_settings,
                algorithm="invalid",
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_configure_smart_queue_high_bandwidth_warning(self, mock_settings):
        from src.tools.qos import configure_smart_queue

        result = await configure_smart_queue(
            site_id="default",
            wan_id="wan-001",
            download_kbps=500000,  # > 300 Mbps
            upload_kbps=50000,
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert len(result["warnings"]) > 0
        assert any("300 Mbps" in w for w in result["warnings"])


class TestDisableSmartQueue:
    @pytest.mark.asyncio
    async def test_disable_smart_queue_success(self, mock_settings):
        from src.tools.qos import disable_smart_queue

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.put = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "wan-001",
                            "sqm_enabled": False,
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await disable_smart_queue(
                    site_id="default",
                    wan_id="wan-001",
                    settings=mock_settings,
                    confirm=True,
                )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_disable_smart_queue_requires_confirmation(self, mock_settings):
        from src.tools.qos import disable_smart_queue
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await disable_smart_queue(
                site_id="default",
                wan_id="wan-001",
                settings=mock_settings,
                confirm=False,
            )


# ============================================================================
# Traffic Route Management Tests (4 tools)
# ============================================================================


class TestListTrafficRoutes:
    @pytest.mark.asyncio
    async def test_list_traffic_routes_success(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_routes})

            result = await list_traffic_routes("default", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Block External DNS"
            assert result[1]["name"] == "Prioritize VoIP"

    @pytest.mark.asyncio
    async def test_list_traffic_routes_pagination(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(
                return_value={"data": sample_traffic_routes * 3}  # 6 routes
            )

            result = await list_traffic_routes("default", mock_settings, limit=2, offset=2)
            assert len(result) == 2


class TestCreateTrafficRoute:
    @pytest.mark.asyncio
    async def test_create_traffic_route_success(self, mock_settings):
        from src.tools.qos import create_traffic_route

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "route-new",
                            "name": "Test Route",
                            "action": "allow",
                            "enabled": True,
                            "match_criteria": {
                                "destination_port": 443,
                                "protocol": "tcp",
                            },
                            "priority": 100,
                            "site_id": "default",
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await create_traffic_route(
                    site_id="default",
                    name="Test Route",
                    action="allow",
                    settings=mock_settings,
                    destination_port=443,
                    protocol="tcp",
                    confirm=True,
                )

            assert result["name"] == "Test Route"
            assert result["action"] == "allow"

    @pytest.mark.asyncio
    async def test_create_traffic_route_requires_confirmation(self, mock_settings):
        from src.tools.qos import create_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await create_traffic_route(
                site_id="default",
                name="Test",
                action="allow",
                settings=mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_create_traffic_route_invalid_action(self, mock_settings):
        from src.tools.qos import create_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Invalid action"):
            await create_traffic_route(
                site_id="default",
                name="Test",
                action="invalid",
                settings=mock_settings,
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_create_traffic_route_invalid_dscp(self, mock_settings):
        from src.tools.qos import create_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="DSCP marking must be 0-63"):
            await create_traffic_route(
                site_id="default",
                name="Test",
                action="mark",
                settings=mock_settings,
                dscp_marking=100,  # Invalid
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_create_traffic_route_invalid_priority(self, mock_settings):
        from src.tools.qos import create_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Priority must be 1-1000"):
            await create_traffic_route(
                site_id="default",
                name="Test",
                action="allow",
                settings=mock_settings,
                priority=2000,  # Invalid
                confirm=True,
            )


class TestUpdateTrafficRoute:
    @pytest.mark.asyncio
    async def test_update_traffic_route_success(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import update_traffic_route

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            updated_route = sample_traffic_routes[0].copy()
            updated_route["enabled"] = False
            mock_instance.put = AsyncMock(return_value={"data": [updated_route]})

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await update_traffic_route(
                    site_id="default",
                    route_id="route-001",
                    settings=mock_settings,
                    enabled=False,
                    confirm=True,
                )

            assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_traffic_route_requires_confirmation(self, mock_settings):
        from src.tools.qos import update_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await update_traffic_route(
                site_id="default",
                route_id="route-001",
                settings=mock_settings,
                enabled=False,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_update_traffic_route_no_fields(self, mock_settings):
        from src.tools.qos import update_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="No update fields provided"):
            await update_traffic_route(
                site_id="default",
                route_id="route-001",
                settings=mock_settings,
                confirm=True,
            )


class TestDeleteTrafficRoute:
    @pytest.mark.asyncio
    async def test_delete_traffic_route_success(self, mock_settings):
        from src.tools.qos import delete_traffic_route

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.delete = AsyncMock(return_value={})

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await delete_traffic_route(
                    site_id="default",
                    route_id="route-001",
                    settings=mock_settings,
                    confirm=True,
                )

            assert result["success"] is True
            assert result["route_id"] == "route-001"

    @pytest.mark.asyncio
    async def test_delete_traffic_route_requires_confirmation(self, mock_settings):
        from src.tools.qos import delete_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await delete_traffic_route(
                site_id="default",
                route_id="route-001",
                settings=mock_settings,
                confirm=False,
            )
