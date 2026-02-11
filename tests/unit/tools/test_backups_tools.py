"""Tests for backup and restore tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.backups as backups_module
from src.tools.backups import (
    delete_backup,
    download_backup,
    get_backup_details,
    get_backup_schedule,
    get_backup_status,
    get_restore_status,
    list_backups,
    restore_backup,
    schedule_backups,
    trigger_backup,
    validate_backup,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError


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
    return settings


@pytest.mark.asyncio
async def test_trigger_backup_success(mock_settings):
    mock_response = {
        "data": {
            "url": "/data/backup/backup_20260105.unf",
            "id": "backup-123",
        }
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.trigger_backup = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with patch.object(backups_module, "log_audit"):
            result = await trigger_backup(
                "default",
                "network",
                mock_settings,
                retention_days=30,
                confirm=True,
            )

            assert result["status"] == "completed"
            assert result["backup_type"] == "network"
            assert result["filename"] == "backup_20260105.unf"
            mock_client.trigger_backup.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_backup_dry_run(mock_settings):
    with patch.object(backups_module, "log_audit"):
        result = await trigger_backup(
            "default",
            "system",
            mock_settings,
            retention_days=7,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_create"]["backup_type"] == "system"
        assert "10-100 MB" in result["would_create"]["estimated_size"]


@pytest.mark.asyncio
async def test_trigger_backup_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await trigger_backup("default", "network", mock_settings, confirm=False)
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_trigger_backup_invalid_type(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await trigger_backup("default", "invalid", mock_settings, confirm=True)
    assert "Invalid backup_type" in str(excinfo.value)


@pytest.mark.asyncio
async def test_trigger_backup_invalid_retention(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await trigger_backup("default", "network", mock_settings, retention_days=0, confirm=True)
    assert "retention_days" in str(excinfo.value)


@pytest.mark.asyncio
async def test_list_backups_success(mock_settings):
    mock_backups = [
        {
            "id": "backup-1",
            "filename": "backup_20260101.unf",
            "size": 5000000,
            "datetime": "2026-01-01T12:00:00Z",
            "type": "NETWORK",
            "valid": True,
        },
        {
            "id": "backup-2",
            "name": "backup_20260102.unifi",
            "filesize": 100000000,
            "created": "2026-01-02T12:00:00Z",
            "valid": True,
            "cloud_backup": True,
        },
    ]

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_backups = AsyncMock(return_value=mock_backups)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await list_backups("default", mock_settings)

        assert len(result) == 2
        assert result[0]["filename"] == "backup_20260101.unf"
        assert result[0]["size_bytes"] == 5000000
        assert result[0]["backup_type"] == "NETWORK"
        assert result[1]["filename"] == "backup_20260102.unifi"
        assert result[1]["backup_type"] == "SYSTEM"
        assert result[1]["cloud_synced"] is True


@pytest.mark.asyncio
async def test_list_backups_empty(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_backups = AsyncMock(return_value=[])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await list_backups("default", mock_settings)
        assert result == []


@pytest.mark.asyncio
async def test_get_backup_details_success(mock_settings):
    mock_backups = [
        {
            "id": "backup-1",
            "filename": "backup_20260101.unf",
            "size": 5000000,
            "datetime": "2026-01-01T12:00:00Z",
            "type": "NETWORK",
            "valid": True,
            "version": "8.0.26",
        },
    ]

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_backups = AsyncMock(return_value=mock_backups)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await get_backup_details("default", "backup_20260101.unf", mock_settings)

        assert result["filename"] == "backup_20260101.unf"
        assert result["version"] == "8.0.26"


@pytest.mark.asyncio
async def test_get_backup_details_not_found(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_backups = AsyncMock(return_value=[])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await get_backup_details("default", "nonexistent.unf", mock_settings)


@pytest.mark.asyncio
async def test_download_backup_success(mock_settings, tmp_path):
    backup_content = b"UNIFI_BACKUP_CONTENT_TEST_DATA"

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.download_backup = AsyncMock(return_value=backup_content)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    output_path = tmp_path / "test_backup.unf"

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with patch.object(backups_module, "log_audit"):
            result = await download_backup(
                "default",
                "backup_20260101.unf",
                str(output_path),
                mock_settings,
                verify_checksum=True,
            )

            assert result["size_bytes"] == len(backup_content)
            assert result["checksum"] is not None
            assert len(result["checksum"]) == 64
            assert output_path.exists()
            assert output_path.read_bytes() == backup_content


@pytest.mark.asyncio
async def test_download_backup_no_checksum(mock_settings, tmp_path):
    backup_content = b"BACKUP_DATA"

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.download_backup = AsyncMock(return_value=backup_content)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    output_path = tmp_path / "test_backup.unf"

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with patch.object(backups_module, "log_audit"):
            result = await download_backup(
                "default",
                "backup.unf",
                str(output_path),
                mock_settings,
                verify_checksum=False,
            )

            assert result["checksum"] is None


@pytest.mark.asyncio
async def test_delete_backup_success(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.delete_backup = AsyncMock(return_value={})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with patch.object(backups_module, "log_audit"):
            result = await delete_backup(
                "default",
                "old_backup.unf",
                mock_settings,
                confirm=True,
            )

            assert result["status"] == "deleted"
            assert result["backup_filename"] == "old_backup.unf"
            mock_client.delete_backup.assert_called_once()


@pytest.mark.asyncio
async def test_delete_backup_dry_run(mock_settings):
    with patch.object(backups_module, "log_audit"):
        result = await delete_backup(
            "default",
            "backup.unf",
            mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_delete"] == "backup.unf"


@pytest.mark.asyncio
async def test_delete_backup_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await delete_backup("default", "backup.unf", mock_settings, confirm=False)
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_restore_backup_success(mock_settings):
    mock_trigger_response = {
        "data": {
            "url": "/data/backup/pre_restore.unf",
            "id": "pre-restore-backup",
        }
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.trigger_backup = AsyncMock(return_value=mock_trigger_response)
    mock_client.restore_backup = AsyncMock(return_value={"status": "ok"})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with patch.object(backups_module, "log_audit"):
            result = await restore_backup(
                "default",
                "backup_20260101.unf",
                mock_settings,
                create_pre_restore_backup=True,
                confirm=True,
            )

            assert result["status"] == "restore_initiated"
            assert result["pre_restore_backup_id"] is not None
            assert result["can_rollback"] is True
            mock_client.restore_backup.assert_called_once()


@pytest.mark.asyncio
async def test_restore_backup_no_pre_backup(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.restore_backup = AsyncMock(return_value={"status": "ok"})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with patch.object(backups_module, "log_audit"):
            result = await restore_backup(
                "default",
                "backup.unf",
                mock_settings,
                create_pre_restore_backup=False,
                confirm=True,
            )

            assert result["pre_restore_backup_id"] is None
            assert result["can_rollback"] is False


@pytest.mark.asyncio
async def test_restore_backup_dry_run(mock_settings):
    with patch.object(backups_module, "log_audit"):
        result = await restore_backup(
            "default",
            "backup.unf",
            mock_settings,
            create_pre_restore_backup=True,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_restore_from"] == "backup.unf"
        assert "warning" in result


@pytest.mark.asyncio
async def test_restore_backup_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await restore_backup("default", "backup.unf", mock_settings, confirm=False)
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_validate_backup_valid(mock_settings):
    mock_backups = [
        {
            "id": "backup-1",
            "filename": "valid_backup.unf",
            "size": 10000000,
            "datetime": "2026-01-01T12:00:00Z",
            "type": "NETWORK",
            "valid": True,
            "version": "8.0.26",
        },
    ]

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_backups = AsyncMock(return_value=mock_backups)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await validate_backup("default", "valid_backup.unf", mock_settings)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0
        assert result["backup_version"] == "8.0.26"


@pytest.mark.asyncio
async def test_validate_backup_invalid_empty(mock_settings):
    mock_backups = [
        {
            "id": "backup-1",
            "filename": "empty_backup.unf",
            "size": 0,
            "datetime": "2026-01-01T12:00:00Z",
            "valid": False,
        },
    ]

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_backups = AsyncMock(return_value=mock_backups)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await validate_backup("default", "empty_backup.unf", mock_settings)

        assert result["is_valid"] is False
        assert any("empty" in err.lower() for err in result["errors"])


@pytest.mark.asyncio
async def test_validate_backup_with_warnings(mock_settings):
    mock_backups = [
        {
            "id": "backup-1",
            "filename": "small_backup.unf",
            "size": 500,
            "datetime": "2026-01-01T12:00:00Z",
            "valid": True,
        },
    ]

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_backups = AsyncMock(return_value=mock_backups)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await validate_backup("default", "small_backup.unf", mock_settings)

        assert result["is_valid"] is True
        assert len(result["warnings"]) > 0


@pytest.mark.asyncio
async def test_validate_backup_not_found(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_backups = AsyncMock(return_value=[])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await validate_backup("default", "nonexistent.unf", mock_settings)

        assert result["is_valid"] is False
        assert len(result["errors"]) > 0


# Tests for new backup status and scheduling tools


@pytest.mark.asyncio
async def test_get_backup_status_success(mock_settings):
    mock_status = {
        "status": "completed",
        "progress": 100,
        "step": "Finalizing",
        "started_at": "2026-01-24T10:00:00Z",
        "completed_at": "2026-01-24T10:02:30Z",
        "backup": {
            "id": "backup-123",
            "filename": "backup_20260124.unf",
        },
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get_backup_status = AsyncMock(return_value=mock_status)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await get_backup_status("op_backup_abc123", mock_settings)

        assert result["status"] == "completed"
        assert result["progress_percent"] == 100
        assert result["operation_id"] == "op_backup_abc123"
        mock_client.get_backup_status.assert_called_once_with(operation_id="op_backup_abc123")


@pytest.mark.asyncio
async def test_get_backup_status_fallback(mock_settings):
    """Test fallback when API doesn't support status endpoint."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    # Simulate API not having get_backup_status method
    del mock_client.get_backup_status
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await get_backup_status("op_backup_abc123", mock_settings)

        assert result["status"] == "completed"
        assert result["progress_percent"] == 100
        assert "not available" in result["message"]


@pytest.mark.asyncio
async def test_get_restore_status_success(mock_settings):
    mock_status = {
        "backup_id": "backup-123",
        "status": "in_progress",
        "progress": 45,
        "step": "Restoring device configurations",
        "started_at": "2026-01-24T10:05:00Z",
        "pre_restore_backup_id": "backup-pre-restore-456",
        "can_rollback": True,
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get_restore_status = AsyncMock(return_value=mock_status)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await get_restore_status("op_restore_xyz789", mock_settings)

        assert result["status"] == "in_progress"
        assert result["progress_percent"] == 45
        assert result["can_rollback"] is True
        assert result["pre_restore_backup_id"] == "backup-pre-restore-456"
        mock_client.get_restore_status.assert_called_once_with(operation_id="op_restore_xyz789")


@pytest.mark.asyncio
async def test_get_restore_status_connection_error(mock_settings):
    """Test graceful handling when controller is restarting during restore."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get_restore_status = AsyncMock(
        side_effect=ConnectionError("Controller unavailable")
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await get_restore_status("op_restore_xyz789", mock_settings)

        # Should handle gracefully and indicate in_progress
        assert result["status"] == "in_progress"
        assert "unavailable" in result["message"]


@pytest.mark.asyncio
async def test_schedule_backups_daily_success(mock_settings):
    mock_response = {
        "schedule_id": "schedule_daily_network",
        "next_run": "2026-01-25T03:00:00Z",
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.configure_backup_schedule = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with patch.object(backups_module, "log_audit"):
            result = await schedule_backups(
                site_id="default",
                backup_type="network",
                frequency="daily",
                time_of_day="03:00",
                retention_days=30,
                max_backups=10,
                confirm=True,
                settings=mock_settings,
            )

            assert result["schedule_id"] == "schedule_daily_network"
            assert result["frequency"] == "daily"
            assert result["backup_type"] == "network"
            assert result["time_of_day"] == "03:00"
            assert result["next_run"] == "2026-01-25T03:00:00Z"
            mock_client.configure_backup_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_schedule_backups_weekly_success(mock_settings):
    mock_response = {
        "schedule_id": "schedule_weekly_system",
        "next_run": "2026-01-26T02:00:00Z",
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.configure_backup_schedule = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        with patch.object(backups_module, "log_audit"):
            result = await schedule_backups(
                site_id="default",
                backup_type="system",
                frequency="weekly",
                time_of_day="02:00",
                day_of_week=6,  # Sunday
                retention_days=90,
                cloud_backup_enabled=True,
                confirm=True,
                settings=mock_settings,
            )

            assert result["frequency"] == "weekly"
            assert result["day_of_week"] == 6
            assert result["cloud_backup_enabled"] is True


@pytest.mark.asyncio
async def test_schedule_backups_dry_run(mock_settings):
    with patch.object(backups_module, "log_audit"):
        result = await schedule_backups(
            site_id="default",
            backup_type="network",
            frequency="daily",
            time_of_day="03:00",
            confirm=True,
            dry_run=True,
            settings=mock_settings,
        )

        assert result["dry_run"] is True
        assert result["would_configure"]["frequency"] == "daily"


@pytest.mark.asyncio
async def test_schedule_backups_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await schedule_backups(
            site_id="default",
            backup_type="network",
            frequency="daily",
            time_of_day="03:00",
            confirm=False,
            settings=mock_settings,
        )
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_schedule_backups_invalid_frequency(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await schedule_backups(
            site_id="default",
            backup_type="network",
            frequency="hourly",  # Invalid
            time_of_day="03:00",
            confirm=True,
            settings=mock_settings,
        )
    assert "Invalid frequency" in str(excinfo.value)


@pytest.mark.asyncio
async def test_schedule_backups_invalid_time(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await schedule_backups(
            site_id="default",
            backup_type="network",
            frequency="daily",
            time_of_day="25:00",  # Invalid hour
            confirm=True,
            settings=mock_settings,
        )
    assert "Invalid time_of_day" in str(excinfo.value)


@pytest.mark.asyncio
async def test_schedule_backups_weekly_missing_day(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await schedule_backups(
            site_id="default",
            backup_type="network",
            frequency="weekly",
            time_of_day="03:00",
            # Missing day_of_week
            confirm=True,
            settings=mock_settings,
        )
    assert "day_of_week required" in str(excinfo.value)


@pytest.mark.asyncio
async def test_schedule_backups_monthly_missing_day(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await schedule_backups(
            site_id="default",
            backup_type="network",
            frequency="monthly",
            time_of_day="03:00",
            # Missing day_of_month
            confirm=True,
            settings=mock_settings,
        )
    assert "day_of_month required" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_backup_schedule_configured(mock_settings):
    mock_schedule = {
        "schedule_id": "schedule_daily_network",
        "enabled": True,
        "backup_type": "network",
        "frequency": "daily",
        "time_of_day": "03:00",
        "retention_days": 30,
        "max_backups": 10,
        "cloud_backup_enabled": True,
        "last_run": "2026-01-24T03:00:00Z",
        "last_backup_id": "backup-123",
        "next_run": "2026-01-25T03:00:00Z",
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get_backup_schedule = AsyncMock(return_value=mock_schedule)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await get_backup_schedule("default", mock_settings)

        assert result["configured"] is True
        assert result["enabled"] is True
        assert result["frequency"] == "daily"
        assert result["time_of_day"] == "03:00"
        assert result["next_run"] == "2026-01-25T03:00:00Z"
        mock_client.get_backup_schedule.assert_called_once_with(site_id="default")


@pytest.mark.asyncio
async def test_get_backup_schedule_not_configured(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get_backup_schedule = AsyncMock(return_value=None)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await get_backup_schedule("default", mock_settings)

        assert result["configured"] is False
        assert "No automated backup schedule" in result["message"]


@pytest.mark.asyncio
async def test_get_backup_schedule_fallback(mock_settings):
    """Test fallback when API doesn't support scheduling."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    # Simulate API not having get_backup_schedule method
    del mock_client.get_backup_schedule
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(backups_module, "UniFiClient", return_value=mock_client):
        result = await get_backup_schedule("default", mock_settings)

        assert result["configured"] is False
        assert "not supported" in result["message"]
