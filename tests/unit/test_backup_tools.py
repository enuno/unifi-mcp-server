"""Unit tests for backup and restore management tools."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.backups import (
    delete_backup,
    download_backup,
    get_backup_details,
    list_backups,
    restore_backup,
    trigger_backup,
    validate_backup,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_backup_list():
    """Sample list of backups for testing."""
    return [
        {
            "id": "backup_20250129_120000",
            "filename": "backup_2025-01-29_12-00-00.unf",
            "size": 5242880,  # 5 MB
            "datetime": "2025-01-29T12:00:00Z",
            "type": "NETWORK",
            "valid": True,
            "cloud_backup": True,
            "version": "10.0.160",
        },
        {
            "id": "backup_20250128_030000",
            "filename": "backup_2025-01-28_03-00-00.unf",
            "size": 4718592,  # 4.5 MB
            "datetime": "2025-01-28T03:00:00Z",
            "type": "NETWORK",
            "valid": True,
            "cloud_backup": False,
            "version": "10.0.160",
        },
        {
            "id": "backup_20250127_140000",
            "filename": "backup_2025-01-27_14-00-00.unifi",
            "size": 104857600,  # 100 MB
            "datetime": "2025-01-27T14:00:00Z",
            "type": "SYSTEM",
            "valid": True,
            "cloud_backup": False,
            "version": "10.0.159",
        },
    ]


@pytest.fixture
def sample_backup_response():
    """Sample backup creation response."""
    return {
        "data": {
            "id": "backup_20250129_153045",
            "url": "/data/backup/backup_2025-01-29_15-30-45.unf",
        }
    }


@pytest.fixture
def sample_backup_content():
    """Sample backup file content (binary data)."""
    return b"UNIFI_BACKUP_DATA_MOCK_CONTENT" * 1000  # ~30KB of mock data


# ============================================================================
# Test: trigger_backup - Backup Creation
# ============================================================================


@pytest.mark.asyncio
async def test_trigger_backup_network_success(settings, sample_backup_response):
    """Test creating a network backup successfully."""
    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.trigger_backup.return_value = sample_backup_response
        mock_client.return_value = mock_instance

        result = await trigger_backup(
            site_id="default",
            backup_type="network",
            retention_days=30,
            confirm=True,
            settings=settings,
        )

        assert result["backup_id"] == "backup_20250129_153045"
        assert result["filename"] == "backup_2025-01-29_15-30-45.unf"
        assert result["backup_type"] == "network"
        assert result["retention_days"] == 30
        assert result["status"] == "completed"
        assert "download_url" in result
        mock_instance.trigger_backup.assert_called_once_with(
            site_id="default",
            backup_type="network",
            days=30,
        )


@pytest.mark.asyncio
async def test_trigger_backup_system_success(settings, sample_backup_response):
    """Test creating a system backup successfully."""
    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.trigger_backup.return_value = sample_backup_response
        mock_client.return_value = mock_instance

        result = await trigger_backup(
            site_id="default",
            backup_type="system",
            retention_days=7,
            confirm=True,
            settings=settings,
        )

        assert result["backup_type"] == "system"
        assert result["retention_days"] == 7
        mock_instance.trigger_backup.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_backup_without_confirmation(settings):
    """Test that backup creation requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await trigger_backup(
            site_id="default",
            backup_type="network",
            retention_days=30,
            confirm=False,
            settings=settings,
        )


@pytest.mark.asyncio
async def test_trigger_backup_dry_run(settings):
    """Test dry run mode for backup creation."""
    result = await trigger_backup(
        site_id="default",
        backup_type="network",
        retention_days=30,
        confirm=True,
        dry_run=True,
        settings=settings,
    )

    assert result["dry_run"] is True
    assert "would_create" in result
    assert result["would_create"]["backup_type"] == "network"
    assert result["would_create"]["retention_days"] == 30


@pytest.mark.asyncio
async def test_trigger_backup_invalid_type(settings):
    """Test backup creation with invalid type."""
    with pytest.raises(ValidationError, match="Invalid backup_type"):
        await trigger_backup(
            site_id="default",
            backup_type="invalid_type",
            retention_days=30,
            confirm=True,
            settings=settings,
        )


@pytest.mark.asyncio
async def test_trigger_backup_invalid_retention(settings):
    """Test backup creation with invalid retention days."""
    with pytest.raises(ValidationError, match="retention_days"):
        await trigger_backup(
            site_id="default",
            backup_type="network",
            retention_days=0,  # Invalid: must be -1 or positive
            confirm=True,
            settings=settings,
        )


@pytest.mark.asyncio
async def test_trigger_backup_indefinite_retention(settings, sample_backup_response):
    """Test backup creation with indefinite retention."""
    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.trigger_backup.return_value = sample_backup_response
        mock_client.return_value = mock_instance

        result = await trigger_backup(
            site_id="default",
            backup_type="network",
            retention_days=-1,  # Indefinite
            confirm=True,
            settings=settings,
        )

        assert result["retention_days"] == -1
        mock_instance.trigger_backup.assert_called_with(
            site_id="default",
            backup_type="network",
            days=-1,
        )


# ============================================================================
# Test: list_backups - Backup Listing
# ============================================================================


@pytest.mark.asyncio
async def test_list_backups_success(settings, sample_backup_list):
    """Test listing all backups successfully."""
    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.list_backups.return_value = sample_backup_list
        mock_client.return_value = mock_instance

        result = await list_backups(site_id="default", settings=settings)

        assert len(result) == 3
        assert result[0]["filename"] == "backup_2025-01-29_12-00-00.unf"
        assert result[0]["backup_type"] == "NETWORK"
        assert result[0]["size_bytes"] == 5242880
        assert result[1]["cloud_synced"] is False
        assert result[2]["backup_type"] == "SYSTEM"
        mock_instance.list_backups.assert_called_once_with(site_id="default")


@pytest.mark.asyncio
async def test_list_backups_empty(settings):
    """Test listing backups when none exist."""
    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.list_backups.return_value = []
        mock_client.return_value = mock_instance

        result = await list_backups(site_id="default", settings=settings)

        assert result == []
        assert len(result) == 0


# ============================================================================
# Test: get_backup_details - Backup Details Retrieval
# ============================================================================


@pytest.mark.asyncio
async def test_get_backup_details_success(settings, sample_backup_list):
    """Test getting backup details successfully."""
    with patch("src.tools.backups.list_backups") as mock_list:
        # Transform to expected format
        formatted_backups = [
            {
                "backup_id": b["id"],
                "filename": b["filename"],
                "backup_type": b["type"],
                "created_at": b["datetime"],
                "size_bytes": b["size"],
                "version": b["version"],
                "is_valid": b["valid"],
                "cloud_synced": b["cloud_backup"],
            }
            for b in sample_backup_list
        ]
        mock_list.return_value = formatted_backups

        result = await get_backup_details(
            site_id="default",
            backup_filename="backup_2025-01-29_12-00-00.unf",
            settings=settings,
        )

        assert result["filename"] == "backup_2025-01-29_12-00-00.unf"
        assert result["backup_type"] == "NETWORK"
        assert result["size_bytes"] == 5242880


@pytest.mark.asyncio
async def test_get_backup_details_not_found(settings):
    """Test getting details for non-existent backup."""
    with patch("src.tools.backups.list_backups") as mock_list:
        mock_list.return_value = []

        with pytest.raises(ResourceNotFoundError):
            await get_backup_details(
                site_id="default",
                backup_filename="nonexistent.unf",
                settings=settings,
            )


# ============================================================================
# Test: download_backup - Backup Download
# ============================================================================


@pytest.mark.asyncio
async def test_download_backup_success(settings, sample_backup_content, tmp_path):
    """Test downloading a backup file successfully."""
    output_path = tmp_path / "test_backup.unf"

    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.download_backup.return_value = sample_backup_content
        mock_client.return_value = mock_instance

        result = await download_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            output_path=str(output_path),
            verify_checksum=True,
            settings=settings,
        )

        assert result["backup_filename"] == "backup_2025-01-29.unf"
        assert result["size_bytes"] == len(sample_backup_content)
        assert "checksum" in result
        assert result["checksum"] is not None
        assert len(result["checksum"]) == 64  # SHA-256 hex length
        assert output_path.exists()
        assert output_path.read_bytes() == sample_backup_content
        mock_instance.download_backup.assert_called_once()


@pytest.mark.asyncio
async def test_download_backup_without_checksum(settings, sample_backup_content, tmp_path):
    """Test downloading backup without checksum verification."""
    output_path = tmp_path / "test_backup.unf"

    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.download_backup.return_value = sample_backup_content
        mock_client.return_value = mock_instance

        result = await download_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            output_path=str(output_path),
            verify_checksum=False,
            settings=settings,
        )

        assert result["checksum"] is None


@pytest.mark.asyncio
async def test_download_backup_creates_directory(settings, sample_backup_content, tmp_path):
    """Test that download creates parent directories."""
    output_path = tmp_path / "nested" / "directory" / "backup.unf"

    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.download_backup.return_value = sample_backup_content
        mock_client.return_value = mock_instance

        result = await download_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            output_path=str(output_path),
            settings=settings,
        )

        assert output_path.exists()
        assert output_path.parent.exists()


# ============================================================================
# Test: delete_backup - Backup Deletion
# ============================================================================


@pytest.mark.asyncio
async def test_delete_backup_success(settings):
    """Test deleting a backup successfully."""
    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.delete_backup.return_value = {"success": True}
        mock_client.return_value = mock_instance

        result = await delete_backup(
            site_id="default",
            backup_filename="old_backup.unf",
            confirm=True,
            settings=settings,
        )

        assert result["backup_filename"] == "old_backup.unf"
        assert result["status"] == "deleted"
        assert "deleted_at" in result
        mock_instance.delete_backup.assert_called_once_with(
            site_id="default",
            backup_filename="old_backup.unf",
        )


@pytest.mark.asyncio
async def test_delete_backup_without_confirmation(settings):
    """Test that backup deletion requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await delete_backup(
            site_id="default",
            backup_filename="backup.unf",
            confirm=False,
            settings=settings,
        )


@pytest.mark.asyncio
async def test_delete_backup_dry_run(settings):
    """Test dry run mode for backup deletion."""
    result = await delete_backup(
        site_id="default",
        backup_filename="backup.unf",
        confirm=True,
        dry_run=True,
        settings=settings,
    )

    assert result["dry_run"] is True
    assert result["would_delete"] == "backup.unf"


# ============================================================================
# Test: restore_backup - Backup Restoration
# ============================================================================


@pytest.mark.asyncio
async def test_restore_backup_with_pre_restore(settings, sample_backup_response):
    """Test restoring from backup with pre-restore backup."""
    with patch("src.tools.backups.UniFiClient") as mock_client:
        with patch("src.tools.backups.trigger_backup") as mock_trigger:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = True
            mock_instance.restore_backup.return_value = {"status": "success"}
            mock_client.return_value = mock_instance

            mock_trigger.return_value = {
                "backup_id": "pre_restore_backup_123",
                "filename": "pre_restore.unf",
            }

            result = await restore_backup(
                site_id="default",
                backup_filename="backup_2025-01-29.unf",
                create_pre_restore_backup=True,
                confirm=True,
                settings=settings,
            )

            assert result["backup_filename"] == "backup_2025-01-29.unf"
            assert result["status"] == "restore_initiated"
            assert result["pre_restore_backup_id"] == "pre_restore_backup_123"
            assert result["can_rollback"] is True
            mock_trigger.assert_called_once()
            mock_instance.restore_backup.assert_called_once()


@pytest.mark.asyncio
async def test_restore_backup_without_pre_restore(settings):
    """Test restoring without pre-restore backup."""
    with patch("src.tools.backups.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.restore_backup.return_value = {"status": "success"}
        mock_client.return_value = mock_instance

        result = await restore_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            create_pre_restore_backup=False,
            confirm=True,
            settings=settings,
        )

        assert result["pre_restore_backup_id"] is None
        assert result["can_rollback"] is False


@pytest.mark.asyncio
async def test_restore_backup_without_confirmation(settings):
    """Test that restore requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await restore_backup(
            site_id="default",
            backup_filename="backup.unf",
            confirm=False,
            settings=settings,
        )


@pytest.mark.asyncio
async def test_restore_backup_dry_run(settings):
    """Test dry run mode for restore."""
    result = await restore_backup(
        site_id="default",
        backup_filename="backup.unf",
        create_pre_restore_backup=True,
        confirm=True,
        dry_run=True,
        settings=settings,
    )

    assert result["dry_run"] is True
    assert result["would_restore_from"] == "backup.unf"
    assert result["would_create_pre_restore_backup"] is True
    assert "warning" in result


# ============================================================================
# Test: validate_backup - Backup Validation
# ============================================================================


@pytest.mark.asyncio
async def test_validate_backup_success(settings):
    """Test validating a valid backup."""
    valid_backup = {
        "backup_id": "backup_123",
        "filename": "backup_2025-01-29.unf",
        "size_bytes": 5242880,
        "is_valid": True,
        "version": "10.0.160",
    }

    with patch("src.tools.backups.get_backup_details") as mock_details:
        mock_details.return_value = valid_backup

        result = await validate_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            settings=settings,
        )

        assert result["is_valid"] is True
        assert result["checksum_valid"] is True
        assert result["format_valid"] is True
        assert result["version_compatible"] is True
        assert len(result["errors"]) == 0
        assert result["backup_version"] == "10.0.160"


@pytest.mark.asyncio
async def test_validate_backup_empty_file(settings):
    """Test validating an empty backup file."""
    invalid_backup = {
        "backup_id": "backup_123",
        "filename": "backup_2025-01-29.unf",
        "size_bytes": 0,  # Empty file
        "is_valid": True,
        "version": "10.0.160",
    }

    with patch("src.tools.backups.get_backup_details") as mock_details:
        mock_details.return_value = invalid_backup

        result = await validate_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            settings=settings,
        )

        assert result["is_valid"] is False
        assert "empty" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_validate_backup_small_file(settings):
    """Test validating an unusually small backup."""
    small_backup = {
        "backup_id": "backup_123",
        "filename": "backup_2025-01-29.unf",
        "size_bytes": 512,  # Very small
        "is_valid": True,
        "version": "10.0.160",
    }

    with patch("src.tools.backups.get_backup_details") as mock_details:
        mock_details.return_value = small_backup

        result = await validate_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            settings=settings,
        )

        assert result["is_valid"] is True  # Still valid, just warning
        assert len(result["warnings"]) > 0
        assert "unusually small" in result["warnings"][0].lower()


@pytest.mark.asyncio
async def test_validate_backup_marked_invalid(settings):
    """Test validating a backup marked as invalid by controller."""
    invalid_backup = {
        "backup_id": "backup_123",
        "filename": "backup_2025-01-29.unf",
        "size_bytes": 5242880,
        "is_valid": False,  # Marked invalid
        "version": "10.0.160",
    }

    with patch("src.tools.backups.get_backup_details") as mock_details:
        mock_details.return_value = invalid_backup

        result = await validate_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            settings=settings,
        )

        assert result["is_valid"] is False
        assert "marked as invalid" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_validate_backup_no_version(settings):
    """Test validating backup with unknown version."""
    backup_no_version = {
        "backup_id": "backup_123",
        "filename": "backup_2025-01-29.unf",
        "size_bytes": 5242880,
        "is_valid": True,
        "version": "",  # No version info
    }

    with patch("src.tools.backups.get_backup_details") as mock_details:
        mock_details.return_value = backup_no_version

        result = await validate_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            settings=settings,
        )

        assert result["is_valid"] is True
        assert len(result["warnings"]) > 0
        assert "version unknown" in result["warnings"][0].lower()


@pytest.mark.asyncio
async def test_validate_backup_error_handling(settings):
    """Test validation error handling."""
    with patch("src.tools.backups.get_backup_details") as mock_details:
        mock_details.side_effect = Exception("Network error")

        result = await validate_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            settings=settings,
        )

        assert result["is_valid"] is False
        assert len(result["errors"]) > 0
        assert "Network error" in result["errors"][0]
