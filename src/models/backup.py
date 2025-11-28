"""Backup and restore data models."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BackupType(str, Enum):
    """Backup type enumeration."""

    SYSTEM = "SYSTEM"  # Complete OS, application, and device configurations
    NETWORK = "NETWORK"  # Network settings and device configurations only


class BackupStatus(str, Enum):
    """Backup operation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RestoreStatus(str, Enum):
    """Restore operation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class BackupMetadata(BaseModel):
    """Backup file metadata and information."""

    backup_id: str = Field(..., description="Unique backup identifier")
    filename: str = Field(..., description="Backup filename (e.g., backup_2025-01-29.unf)")
    backup_type: BackupType = Field(..., description="Type of backup (SYSTEM or NETWORK)")
    created_at: datetime = Field(..., description="Backup creation timestamp")
    size_bytes: int | None = Field(None, description="Backup file size in bytes")
    version: str | None = Field(None, description="UniFi Network version at backup time")

    # Metadata about backup contents
    device_count: int | None = Field(None, description="Number of devices in backup")
    site_count: int | None = Field(None, description="Number of sites in backup")
    network_count: int | None = Field(None, description="Number of networks in backup")

    # Cloud backup status
    cloud_synced: bool = Field(False, description="Whether backup is synced to cloud")
    cloud_sync_time: datetime | None = Field(None, description="Last cloud sync timestamp")

    # Backup location
    download_url: str | None = Field(None, description="Download URL for backup file")
    local_path: str | None = Field(None, description="Local filesystem path (if applicable)")

    # Validation
    checksum: str | None = Field(None, description="Backup file checksum (MD5 or SHA256)")
    is_valid: bool = Field(True, description="Whether backup passed validation checks")
    validation_message: str | None = Field(None, description="Validation error message if any")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "backup_id": "backup_20250129_123456",
                "filename": "backup_2025-01-29_12-34-56.unf",
                "backup_type": "NETWORK",
                "created_at": "2025-01-29T12:34:56Z",
                "size_bytes": 1048576,
                "version": "10.0.160",
                "device_count": 15,
                "site_count": 1,
                "network_count": 5,
                "cloud_synced": True,
                "is_valid": True,
            }
        },
    )


class BackupOperation(BaseModel):
    """Backup operation status and details."""

    operation_id: str = Field(..., description="Unique operation identifier")
    backup_type: BackupType = Field(..., description="Type of backup being created")
    status: BackupStatus = Field(..., description="Current operation status")
    started_at: datetime = Field(..., description="Operation start time")
    completed_at: datetime | None = Field(None, description="Operation completion time")

    # Progress tracking
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage (0-100)")
    current_step: str | None = Field(None, description="Current operation step description")

    # Result
    backup_metadata: BackupMetadata | None = Field(None, description="Metadata of created backup")
    error_message: str | None = Field(None, description="Error message if failed")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "operation_id": "op_backup_abc123",
                "backup_type": "NETWORK",
                "status": "completed",
                "started_at": "2025-01-29T12:34:00Z",
                "completed_at": "2025-01-29T12:35:30Z",
                "progress_percent": 100,
                "current_step": "Finalizing backup",
            }
        },
    )


class RestoreOperation(BaseModel):
    """Restore operation status and details."""

    operation_id: str = Field(..., description="Unique operation identifier")
    backup_id: str = Field(..., description="Backup being restored")
    status: RestoreStatus = Field(..., description="Current operation status")
    started_at: datetime = Field(..., description="Operation start time")
    completed_at: datetime | None = Field(None, description="Operation completion time")

    # Progress tracking
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage (0-100)")
    current_step: str | None = Field(None, description="Current operation step description")

    # Safety features
    pre_restore_backup_id: str | None = Field(
        None,
        description="Backup ID of automatic pre-restore backup (for rollback)",
    )
    can_rollback: bool = Field(False, description="Whether rollback is available")

    # Result
    error_message: str | None = Field(None, description="Error message if failed")
    rollback_reason: str | None = Field(None, description="Reason for rollback if applicable")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "operation_id": "op_restore_xyz789",
                "backup_id": "backup_20250129_123456",
                "status": "in_progress",
                "started_at": "2025-01-29T14:00:00Z",
                "progress_percent": 45,
                "current_step": "Restoring device configurations",
                "pre_restore_backup_id": "backup_20250129_140000_preRestore",
                "can_rollback": True,
            }
        },
    )


class BackupSchedule(BaseModel):
    """Automated backup schedule configuration."""

    schedule_id: str = Field(..., description="Unique schedule identifier")
    enabled: bool = Field(True, description="Whether schedule is enabled")
    backup_type: BackupType = Field(..., description="Type of backup to create")

    # Schedule configuration
    frequency: Literal["daily", "weekly", "monthly"] = Field(
        ...,
        description="Backup frequency",
    )
    time_of_day: str = Field(
        ...,
        description="Time to run backup (HH:MM format, 24-hour)",
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
    )
    day_of_week: int | None = Field(
        None,
        ge=0,
        le=6,
        description="Day of week for weekly backups (0=Monday, 6=Sunday)",
    )
    day_of_month: int | None = Field(
        None,
        ge=1,
        le=31,
        description="Day of month for monthly backups",
    )

    # Retention policy
    retention_days: int = Field(
        30,
        ge=1,
        le=365,
        description="Number of days to retain backups",
    )
    max_backups: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum number of backups to keep",
    )

    # Cloud backup
    cloud_backup_enabled: bool = Field(
        False,
        description="Whether to sync backups to cloud",
    )

    # Last run info
    last_run: datetime | None = Field(None, description="Last execution timestamp")
    last_backup_id: str | None = Field(None, description="Last created backup ID")
    next_run: datetime | None = Field(None, description="Next scheduled execution")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "schedule_id": "schedule_daily_network",
                "enabled": True,
                "backup_type": "NETWORK",
                "frequency": "daily",
                "time_of_day": "03:00",
                "retention_days": 30,
                "max_backups": 10,
                "cloud_backup_enabled": True,
                "last_run": "2025-01-29T03:00:00Z",
                "next_run": "2025-01-30T03:00:00Z",
            }
        },
    )


class BackupValidationResult(BaseModel):
    """Result of backup file validation."""

    backup_id: str = Field(..., description="Backup being validated")
    is_valid: bool = Field(..., description="Whether backup is valid")

    # Validation checks
    checksum_valid: bool = Field(..., description="File integrity check passed")
    format_valid: bool = Field(..., description="File format is correct")
    version_compatible: bool = Field(..., description="Version is compatible with current system")

    # Validation details
    backup_version: str | None = Field(None, description="UniFi version of backup")
    current_version: str | None = Field(None, description="Current UniFi version")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    errors: list[str] = Field(default_factory=list, description="Validation errors")

    # Backup contents preview
    contains_devices: int | None = Field(None, description="Number of devices in backup")
    contains_networks: int | None = Field(None, description="Number of networks in backup")
    contains_sites: int | None = Field(None, description="Number of sites in backup")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "backup_id": "backup_20250129_123456",
                "is_valid": True,
                "checksum_valid": True,
                "format_valid": True,
                "version_compatible": True,
                "backup_version": "10.0.160",
                "current_version": "10.0.160",
                "warnings": [],
                "errors": [],
                "contains_devices": 15,
                "contains_networks": 5,
                "contains_sites": 1,
            }
        },
    )
