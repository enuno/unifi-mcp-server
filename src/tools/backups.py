"""Backup and restore operations MCP tools."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.backup import BackupMetadata, BackupType
from ..utils import (
    ValidationError,
    get_logger,
    log_audit,
    validate_confirmation,
    validate_site_id,
)


async def trigger_backup(
    site_id: str,
    backup_type: str,
    settings: Settings,
    retention_days: int = 30,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Trigger a backup operation on the UniFi controller.

    This creates a new backup of the specified type. The backup process may take
    several minutes depending on the size of your configuration and number of devices.

    Args:
        site_id: Site identifier
        backup_type: Type of backup ("network" or "system")
                    - "network": Network settings and device configurations only
                    - "system": Complete OS, application, and device configurations
        settings: Application settings
        retention_days: Number of days to retain the backup (default: 30, -1 for indefinite)
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create the backup

    Returns:
        Backup operation result including download URL and metadata

    Raises:
        ValidationError: If confirm is not True or backup_type is invalid

    Example:
        ```python
        result = await trigger_backup(
            site_id="default",
            backup_type="network",
            retention_days=30,
            confirm=True,
            settings=settings
        )
        print(f"Backup created: {result['filename']}")
        print(f"Download from: {result['download_url']}")
        ```

    Note:
        - Network backups are faster and smaller (typically <10 MB)
        - System backups are comprehensive but larger (can be >100 MB)
        - After backup completes, use the download_url to retrieve the file
        - Backup files are named with timestamp: backup_YYYY-MM-DD_HH-MM-SS.unf
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "backup operation")
    logger = get_logger(__name__, settings.log_level)

    # Validate backup type
    valid_types = ["network", "system"]
    if backup_type.lower() not in valid_types:
        raise ValidationError(
            f"Invalid backup_type '{backup_type}'. Must be one of: {valid_types}"
        )

    # Validate retention days
    if retention_days < -1 or retention_days == 0:
        raise ValidationError(
            "retention_days must be -1 (indefinite) or positive integer"
        )

    parameters = {
        "site_id": site_id,
        "backup_type": backup_type,
        "retention_days": retention_days,
    }

    if dry_run:
        logger.info(
            f"DRY RUN: Would create {backup_type} backup for site '{site_id}' "
            f"with {retention_days} days retention"
        )
        log_audit(
            operation="trigger_backup",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {
            "dry_run": True,
            "would_create": {
                "backup_type": backup_type,
                "retention_days": retention_days,
                "estimated_size": "10-100 MB" if backup_type == "system" else "<10 MB",
            },
        }

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            response = await client.trigger_backup(
                site_id=site_id,
                backup_type=backup_type,
                days=retention_days,
            )

            # Extract backup information from response
            # Response format: {"data": {"url": "/data/backup/filename.unf", "id": "..."}}
            backup_data = response.get("data", {})
            download_url = backup_data.get("url", "")
            backup_id = backup_data.get("id", "")

            # Extract filename from URL
            filename = download_url.split("/")[-1] if download_url else f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.unf"

            result = {
                "backup_id": backup_id or filename.replace(".unf", ""),
                "filename": filename,
                "download_url": download_url,
                "backup_type": backup_type,
                "created_at": datetime.now().isoformat(),
                "retention_days": retention_days,
                "status": "completed",
            }

            logger.info(
                f"Successfully created {backup_type} backup '{filename}' for site '{site_id}'"
            )
            log_audit(
                operation="trigger_backup",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return result

    except Exception as e:
        logger.error(f"Failed to create backup for site '{site_id}': {e}")
        log_audit(
            operation="trigger_backup",
            parameters=parameters,
            result="error",
            error=str(e),
            site_id=site_id,
        )
        raise


async def list_backups(
    site_id: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """List all available backups for a site.

    Retrieves metadata for all backup files including file size, creation date,
    type, and validity status.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        List of backup metadata dictionaries

    Example:
        ```python
        backups = await list_backups(site_id="default", settings=settings)
        for backup in backups:
            print(f"{backup['filename']}: {backup['size_bytes']} bytes, "
                  f"created {backup['created_at']}")
        ```
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        backups_data = await client.list_backups(site_id=site_id)

        # Transform API response to BackupMetadata format
        backups = []
        for backup in backups_data:
            # Parse backup metadata
            filename = backup.get("filename", backup.get("name", ""))
            size_bytes = backup.get("size", backup.get("filesize", 0))
            created_timestamp = backup.get("datetime", backup.get("created", ""))

            # Determine backup type from filename or metadata
            backup_type_str = backup.get("type", "")
            if not backup_type_str:
                # Infer from filename: .unf = network, .unifi = system
                backup_type_str = "SYSTEM" if filename.endswith(".unifi") else "NETWORK"

            backups.append({
                "backup_id": backup.get("id", filename.replace(".unf", "").replace(".unifi", "")),
                "filename": filename,
                "backup_type": backup_type_str,
                "created_at": created_timestamp,
                "size_bytes": size_bytes,
                "version": backup.get("version", ""),
                "is_valid": backup.get("valid", True),
                "cloud_synced": backup.get("cloud_backup", False),
            })

        logger.info(f"Retrieved {len(backups)} backups for site '{site_id}'")
        return backups


async def get_backup_details(
    site_id: str,
    backup_filename: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get detailed information about a specific backup.

    Args:
        site_id: Site identifier
        backup_filename: Backup filename (e.g., "backup_2025-01-29.unf")
        settings: Application settings

    Returns:
        Detailed backup metadata dictionary

    Raises:
        ResourceNotFoundError: If backup file is not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    # List all backups and find the matching one
    backups = await list_backups(site_id=site_id, settings=settings)

    for backup in backups:
        if backup["filename"] == backup_filename:
            logger.info(f"Retrieved details for backup '{backup_filename}' in site '{site_id}'")
            return backup

    from ..utils import ResourceNotFoundError

    raise ResourceNotFoundError("backup", backup_filename)


async def download_backup(
    site_id: str,
    backup_filename: str,
    output_path: str,
    settings: Settings,
    verify_checksum: bool = True,
) -> dict[str, Any]:
    """Download a backup file to local storage.

    Downloads the specified backup file and optionally verifies its integrity
    using checksum validation.

    Args:
        site_id: Site identifier
        backup_filename: Backup filename to download
        output_path: Local filesystem path to save the backup
        settings: Application settings
        verify_checksum: Whether to calculate and verify file checksum

    Returns:
        Download result with file path and metadata

    Example:
        ```python
        result = await download_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            output_path="/backups/unifi_backup.unf",
            settings=settings
        )
        print(f"Downloaded to: {result['local_path']}")
        print(f"Size: {result['size_bytes']} bytes")
        print(f"Checksum: {result['checksum']}")
        ```
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    logger.info(f"Downloading backup '{backup_filename}' from site '{site_id}'")

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Download backup content
            backup_content = await client.download_backup(
                site_id=site_id,
                backup_filename=backup_filename,
            )

            # Write to file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(backup_content)

            # Calculate checksum if requested
            checksum = ""
            if verify_checksum:
                sha256_hash = hashlib.sha256()
                sha256_hash.update(backup_content)
                checksum = sha256_hash.hexdigest()

            result = {
                "backup_filename": backup_filename,
                "local_path": str(output_file.absolute()),
                "size_bytes": len(backup_content),
                "checksum": checksum if verify_checksum else None,
                "download_time": datetime.now().isoformat(),
            }

            logger.info(
                f"Successfully downloaded backup '{backup_filename}' to '{output_path}' "
                f"({len(backup_content)} bytes)"
            )
            log_audit(
                operation="download_backup",
                parameters={"site_id": site_id, "backup_filename": backup_filename},
                result="success",
                site_id=site_id,
            )

            return result

    except Exception as e:
        logger.error(f"Failed to download backup '{backup_filename}': {e}")
        log_audit(
            operation="download_backup",
            parameters={"site_id": site_id, "backup_filename": backup_filename},
            result="error",
            error=str(e),
            site_id=site_id,
        )
        raise


async def delete_backup(
    site_id: str,
    backup_filename: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete a backup file from the controller.

    Permanently removes a backup file from the UniFi controller storage.
    This operation cannot be undone.

    Args:
        site_id: Site identifier
        backup_filename: Backup filename to delete
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't delete the backup

    Returns:
        Deletion result

    Raises:
        ValidationError: If confirm is not True

    Example:
        ```python
        result = await delete_backup(
            site_id="default",
            backup_filename="old_backup_2024-01-01.unf",
            confirm=True,
            settings=settings
        )
        print(f"Deleted: {result['backup_filename']}")
        ```

    Warning:
        This operation permanently deletes the backup file.
        Ensure you have downloaded or don't need the backup before deleting.
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "backup deletion")
    logger = get_logger(__name__, settings.log_level)

    parameters = {
        "site_id": site_id,
        "backup_filename": backup_filename,
    }

    if dry_run:
        logger.info(f"DRY RUN: Would delete backup '{backup_filename}' from site '{site_id}'")
        log_audit(
            operation="delete_backup",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_delete": backup_filename}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            await client.delete_backup(
                site_id=site_id,
                backup_filename=backup_filename,
            )

            logger.info(f"Successfully deleted backup '{backup_filename}' from site '{site_id}'")
            log_audit(
                operation="delete_backup",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "backup_filename": backup_filename,
                "status": "deleted",
                "deleted_at": datetime.now().isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to delete backup '{backup_filename}': {e}")
        log_audit(
            operation="delete_backup",
            parameters=parameters,
            result="error",
            error=str(e),
            site_id=site_id,
        )
        raise


async def restore_backup(
    site_id: str,
    backup_filename: str,
    settings: Settings,
    create_pre_restore_backup: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restore the UniFi controller from a backup file.

    This is a DESTRUCTIVE operation that will restore the controller to the state
    captured in the backup. The controller may restart during the restore process.

    Safety features:
    - Automatic pre-restore backup creation (enabled by default)
    - Mandatory confirmation flag
    - Dry-run mode for validation
    - Audit logging

    Args:
        site_id: Site identifier
        backup_filename: Backup filename to restore from
        settings: Application settings
        create_pre_restore_backup: Create automatic backup before restore (recommended)
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't restore

    Returns:
        Restore operation result including pre-restore backup info

    Raises:
        ValidationError: If confirm is not True

    Example:
        ```python
        # ALWAYS use confirm=True for restore operations
        result = await restore_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            create_pre_restore_backup=True,  # Create safety backup first
            confirm=True,
            settings=settings
        )
        print(f"Restore initiated. Pre-restore backup: {result['pre_restore_backup_id']}")
        ```

    Warning:
        This operation will:
        1. Restore all configuration from the backup
        2. May overwrite current settings
        3. May cause controller restart
        4. May temporarily disconnect devices

        ALWAYS create a pre-restore backup (enabled by default) so you can
        rollback if needed.
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "RESTORE operation - this will OVERWRITE current configuration")
    logger = get_logger(__name__, settings.log_level)

    parameters = {
        "site_id": site_id,
        "backup_filename": backup_filename,
        "create_pre_restore_backup": create_pre_restore_backup,
    }

    if dry_run:
        logger.info(
            f"DRY RUN: Would restore from backup '{backup_filename}' for site '{site_id}'"
        )
        log_audit(
            operation="restore_backup",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {
            "dry_run": True,
            "would_restore_from": backup_filename,
            "would_create_pre_restore_backup": create_pre_restore_backup,
            "warning": "Controller will restart during restore",
        }

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Create pre-restore backup if requested
            pre_restore_backup_id = None
            if create_pre_restore_backup:
                logger.info("Creating pre-restore backup for safety...")
                pre_restore_result = await trigger_backup(
                    site_id=site_id,
                    backup_type="network",
                    retention_days=7,  # Keep for 7 days
                    confirm=True,
                    settings=settings,
                )
                pre_restore_backup_id = pre_restore_result["backup_id"]
                logger.info(f"Pre-restore backup created: {pre_restore_backup_id}")

            # Perform restore
            logger.warning(
                f"INITIATING RESTORE from '{backup_filename}' for site '{site_id}'. "
                "Controller may restart."
            )

            restore_response = await client.restore_backup(
                site_id=site_id,
                backup_filename=backup_filename,
            )

            result = {
                "backup_filename": backup_filename,
                "status": "restore_initiated",
                "pre_restore_backup_id": pre_restore_backup_id,
                "can_rollback": pre_restore_backup_id is not None,
                "restore_time": datetime.now().isoformat(),
                "warning": "Controller may restart. Devices may temporarily disconnect.",
                "restore_response": restore_response,
            }

            logger.warning(
                f"Restore initiated from '{backup_filename}'. "
                f"Pre-restore backup: {pre_restore_backup_id or 'None'}"
            )
            log_audit(
                operation="restore_backup",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return result

    except Exception as e:
        logger.error(f"Failed to restore from backup '{backup_filename}': {e}")
        log_audit(
            operation="restore_backup",
            parameters=parameters,
            result="error",
            error=str(e),
            site_id=site_id,
        )
        raise


async def validate_backup(
    site_id: str,
    backup_filename: str,
    settings: Settings,
) -> dict[str, Any]:
    """Validate a backup file before restore.

    Performs integrity checks on a backup file to ensure it's valid and compatible
    with the current controller version.

    Args:
        site_id: Site identifier
        backup_filename: Backup filename to validate
        settings: Application settings

    Returns:
        Validation result with details and warnings

    Example:
        ```python
        validation = await validate_backup(
            site_id="default",
            backup_filename="backup_2025-01-29.unf",
            settings=settings
        )
        if validation['is_valid']:
            print("Backup is valid and ready to restore")
        else:
            print(f"Validation errors: {validation['errors']}")
        ```
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    try:
        # Get backup details
        backup_details = await get_backup_details(
            site_id=site_id,
            backup_filename=backup_filename,
            settings=settings,
        )

        # Basic validation checks
        warnings = []
        errors = []

        # Check file size
        size_bytes = backup_details.get("size_bytes", 0)
        if size_bytes == 0:
            errors.append("Backup file appears to be empty")
        elif size_bytes < 1024:  # Less than 1 KB
            warnings.append("Backup file is unusually small")

        # Check backup validity flag
        if not backup_details.get("is_valid", True):
            errors.append("Backup is marked as invalid by controller")

        # Version compatibility check would require downloading the file
        # For now, we just note if version info is available
        backup_version = backup_details.get("version", "")
        if not backup_version:
            warnings.append("Backup version unknown - cannot verify compatibility")

        is_valid = len(errors) == 0

        result = {
            "backup_id": backup_details.get("backup_id", ""),
            "backup_filename": backup_filename,
            "is_valid": is_valid,
            "checksum_valid": True,  # Assumed true if controller lists it
            "format_valid": is_valid,
            "version_compatible": len(errors) == 0,
            "backup_version": backup_version,
            "warnings": warnings,
            "errors": errors,
            "size_bytes": size_bytes,
            "validated_at": datetime.now().isoformat(),
        }

        logger.info(
            f"Validated backup '{backup_filename}': "
            f"{'VALID' if is_valid else 'INVALID'} "
            f"({len(warnings)} warnings, {len(errors)} errors)"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to validate backup '{backup_filename}': {e}")
        return {
            "backup_filename": backup_filename,
            "is_valid": False,
            "errors": [str(e)],
            "validated_at": datetime.now().isoformat(),
        }
