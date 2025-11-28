# UniFi MCP Server - Disaster Recovery Guide

**Last Updated**: 2025-11-28
**Version**: 0.2.0

This guide provides comprehensive instructions for backup, restore, and disaster recovery operations using the UniFi MCP Server.

---

## Table of Contents

1. [Overview](#overview)
2. [Backup Types](#backup-types)
3. [Backup Best Practices](#backup-best-practices)
4. [Creating Backups](#creating-backups)
5. [Downloading Backups](#downloading-backups)
6. [Validating Backups](#validating-backups)
7. [Restoring from Backup](#restoring-from-backup)
8. [Disaster Recovery Scenarios](#disaster-recovery-scenarios)
9. [Cross-Controller Migration](#cross-controller-migration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The UniFi MCP Server provides enterprise-grade backup and restore capabilities with built-in safety mechanisms:

- ✅ **Automatic Pre-Restore Backups** - Safety backup created before every restore
- ✅ **Mandatory Confirmation** - All destructive operations require explicit confirmation
- ✅ **Dry-Run Mode** - Test operations without execution
- ✅ **Backup Validation** - Integrity checks before restore
- ✅ **Audit Logging** - Complete audit trail of all operations
- ✅ **SHA-256 Checksums** - File integrity verification

---

## Backup Types

### Network Backup (`.unf` files)
- **Contents**: Network settings and device configurations only
- **Size**: Typically 5-10 MB
- **Creation Time**: 1-2 minutes
- **Use Cases**:
  - Daily automated backups
  - Quick configuration snapshots
  - Network-only changes
- **Restores**: Networks, VLANs, firewall rules, WiFi configs, device settings

### System Backup (`.unifi` files)
- **Contents**: Complete OS, application, and device configurations
- **Size**: Typically 50-100 MB
- **Creation Time**: 5-10 minutes
- **Use Cases**:
  - Before major upgrades
  - Complete system snapshots
  - Controller migrations
- **Restores**: Everything including OS settings, certificates, user accounts

**Recommendation**: Use **network backups** for regular snapshots, **system backups** for major changes.

---

## Backup Best Practices

### Retention Strategy

**3-2-1 Backup Rule**:
- **3** copies of your data (original + 2 backups)
- **2** different storage media (local + cloud)
- **1** offsite backup

**Recommended Schedule**:
```
Daily:   Network backups (retain 7 days)
Weekly:  Network backups (retain 4 weeks)
Monthly: System backups (retain 12 months)
```

### Before Major Operations

Always create a backup before:
- ✅ Firmware upgrades
- ✅ Network reconfigurations
- ✅ Firewall rule changes
- ✅ Adding/removing devices
- ✅ Controller migrations
- ✅ Configuration imports

### Storage Recommendations

- **Local Storage**: Keep 3-5 recent backups on controller
- **Network Storage**: Archive to NAS weekly
- **Cloud Storage**: Enable cloud backup for critical sites
- **Off-Site**: Monthly backup to external location

---

## Creating Backups

### Network Backup (Daily)

```python
import asyncio
from mcp import MCP

async def create_daily_backup():
    """Create daily network backup."""
    mcp = MCP("unifi-mcp-server")

    backup = await mcp.call_tool("trigger_backup", {
        "site_id": "default",
        "backup_type": "network",
        "retention_days": 7,  # Keep for 1 week
        "confirm": True
    })

    print(f"✅ Backup created: {backup['filename']}")
    print(f"📥 Download URL: {backup['download_url']}")
    print(f"📊 Size: {backup.get('size_bytes', 'N/A')} bytes")

    return backup

# Run backup
asyncio.run(create_daily_backup())
```

### System Backup (Monthly)

```python
async def create_system_backup():
    """Create comprehensive system backup."""
    mcp = MCP("unifi-mcp-server")

    backup = await mcp.call_tool("trigger_backup", {
        "site_id": "default",
        "backup_type": "system",
        "retention_days": 365,  # Keep for 1 year
        "confirm": True
    })

    print(f"✅ System backup created: {backup['filename']}")
    return backup

asyncio.run(create_system_backup())
```

### Dry-Run Mode

Test backup creation without executing:

```python
async def test_backup():
    """Test backup creation (dry-run)."""
    mcp = MCP("unifi-mcp-server")

    result = await mcp.call_tool("trigger_backup", {
        "site_id": "default",
        "backup_type": "network",
        "retention_days": 30,
        "confirm": True,
        "dry_run": True  # Don't actually create backup
    })

    print(f"Dry run result: {result}")

asyncio.run(test_backup())
```

---

## Downloading Backups

### List Available Backups

```python
async def list_all_backups():
    """List all available backups."""
    mcp = MCP("unifi-mcp-server")

    backups = await mcp.call_tool("list_backups", {
        "site_id": "default"
    })

    print(f"📁 Found {len(backups)} backups:\n")

    for backup in backups:
        size_mb = backup['size_bytes'] / 1024 / 1024
        cloud = "☁️" if backup['cloud_synced'] else "💾"
        print(f"{cloud} {backup['filename']}")
        print(f"   Type: {backup['backup_type']}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Created: {backup['created_at']}")
        print(f"   Valid: {'✅' if backup['is_valid'] else '❌'}")
        print()

asyncio.run(list_all_backups())
```

### Download to Local Storage

```python
async def download_backup_file():
    """Download backup file with checksum verification."""
    mcp = MCP("unifi-mcp-server")

    result = await mcp.call_tool("download_backup", {
        "site_id": "default",
        "backup_filename": "backup_2025-01-29_12-00-00.unf",
        "output_path": "/backups/unifi_backup.unf",
        "verify_checksum": True  # Verify integrity
    })

    print(f"✅ Downloaded to: {result['local_path']}")
    print(f"📊 Size: {result['size_bytes']} bytes")
    print(f"🔐 Checksum: {result['checksum']}")

    return result

asyncio.run(download_backup_file())
```

### Automated Backup Script

```bash
#!/bin/bash
# automated_backup.sh - Daily backup script

BACKUP_DIR="/mnt/nas/unifi-backups"
DATE=$(date +%Y-%m-%d)

# Create backup via MCP
python3 <<EOF
import asyncio
from mcp import MCP

async def backup():
    mcp = MCP("unifi-mcp-server")
    backup = await mcp.call_tool("trigger_backup", {
        "site_id": "default",
        "backup_type": "network",
        "retention_days": 7,
        "confirm": True
    })

    # Download backup
    await mcp.call_tool("download_backup", {
        "site_id": "default",
        "backup_filename": backup['filename'],
        "output_path": f"${BACKUP_DIR}/${DATE}_unifi.unf",
        "verify_checksum": True
    })

asyncio.run(backup())
EOF

echo "Backup completed: ${BACKUP_DIR}/${DATE}_unifi.unf"
```

---

## Validating Backups

**ALWAYS** validate backups before restore operations.

```python
async def validate_backup_file():
    """Validate backup integrity before restore."""
    mcp = MCP("unifi-mcp-server")

    validation = await mcp.call_tool("validate_backup", {
        "site_id": "default",
        "backup_filename": "backup_2025-01-29.unf"
    })

    if validation["is_valid"]:
        print("✅ Backup is VALID and ready to restore")
        print(f"   Checksum: {'✅' if validation['checksum_valid'] else '❌'}")
        print(f"   Format: {'✅' if validation['format_valid'] else '❌'}")
        print(f"   Version: {validation['backup_version']}")

        if validation['warnings']:
            print(f"\n⚠️  Warnings:")
            for warning in validation['warnings']:
                print(f"   - {warning}")
    else:
        print("❌ Backup is INVALID")
        print(f"   Errors:")
        for error in validation['errors']:
            print(f"   - {error}")

        return False

    return True

# Validate before restore
asyncio.run(validate_backup_file())
```

---

## Restoring from Backup

### Pre-Restore Checklist

Before restoring a backup:

- [ ] **Validate the backup file** using `validate_backup`
- [ ] **Notify users** of potential downtime
- [ ] **Document current state** (screenshots, configs)
- [ ] **Verify backup age** - is it recent enough?
- [ ] **Check controller version** compatibility
- [ ] **Ensure network access** for download after restart
- [ ] **Enable pre-restore backup** (automatic safety backup)

### Safe Restore Procedure

```python
async def safe_restore():
    """Safely restore from backup with all safety measures."""
    mcp = MCP("unifi-mcp-server")

    backup_filename = "backup_2025-01-29.unf"

    # Step 1: Validate backup
    print("Step 1: Validating backup...")
    validation = await mcp.call_tool("validate_backup", {
        "site_id": "default",
        "backup_filename": backup_filename
    })

    if not validation["is_valid"]:
        print("❌ Backup validation failed!")
        print(f"Errors: {validation['errors']}")
        return

    print("✅ Backup is valid\n")

    # Step 2: Restore with pre-restore backup
    print("Step 2: Initiating restore...")
    print("⚠️  WARNING: Controller will restart!")
    print("⚠️  WARNING: All current config will be overwritten!")

    result = await mcp.call_tool("restore_backup", {
        "site_id": "default",
        "backup_filename": backup_filename,
        "create_pre_restore_backup": True,  # CRITICAL: Safety backup
        "confirm": True
    })

    print(f"\n✅ Restore initiated")
    print(f"📦 Pre-restore backup: {result['pre_restore_backup_id']}")
    print(f"🔄 Rollback available: {result['can_rollback']}")
    print(f"\n⏳ Controller restarting... please wait 2-5 minutes")

    # If restore fails, rollback using pre-restore backup
    if not result.get('status') == 'restore_initiated':
        print("\n❌ Restore failed! Rollback using pre-restore backup:")
        print(f"   {result['pre_restore_backup_id']}")

asyncio.run(safe_restore())
```

### Emergency Rollback

If restore fails or causes issues:

```python
async def emergency_rollback(pre_restore_backup_id):
    """Rollback to pre-restore backup."""
    mcp = MCP("unifi-mcp-server")

    print(f"🚨 EMERGENCY ROLLBACK to {pre_restore_backup_id}")

    result = await mcp.call_tool("restore_backup", {
        "site_id": "default",
        "backup_filename": pre_restore_backup_id,
        "create_pre_restore_backup": False,  # Already in emergency
        "confirm": True
    })

    print("✅ Rollback initiated - controller restarting")

# Use the pre-restore backup ID from restore operation
asyncio.run(emergency_rollback("backup_20250129_160000_preRestore.unf"))
```

---

## Disaster Recovery Scenarios

### Scenario 1: Controller Hardware Failure

**Situation**: Controller hardware fails, need to recover to new hardware.

**Recovery Steps**:

1. **Install new controller** with same UniFi OS version
2. **Complete initial setup** (don't configure anything)
3. **Restore from last system backup**:
   ```python
   # Download backup from off-site storage
   # Restore to new controller
   await mcp.call_tool("restore_backup", {
       "site_id": "default",
       "backup_filename": "system_backup_latest.unifi",
       "create_pre_restore_backup": False,  # New controller
       "confirm": True
   })
   ```
4. **Wait for controller restart** (5-10 minutes)
5. **Verify all devices reconnect**
6. **Test critical functionality**

**Recovery Time**: 30-60 minutes

### Scenario 2: Bad Configuration Change

**Situation**: Configuration change breaks network, need to rollback.

**Recovery Steps**:

1. **List recent backups**:
   ```python
   backups = await mcp.call_tool("list_backups", {
       "site_id": "default"
   })
   # Find backup from before change
   ```

2. **Validate backup**:
   ```python
   validation = await mcp.call_tool("validate_backup", {
       "site_id": "default",
       "backup_filename": "backup_before_change.unf"
   })
   ```

3. **Restore with safety backup**:
   ```python
   await mcp.call_tool("restore_backup", {
       "site_id": "default",
       "backup_filename": "backup_before_change.unf",
       "create_pre_restore_backup": True,  # Can rollback if needed
       "confirm": True
   })
   ```

**Recovery Time**: 5-15 minutes

### Scenario 3: Firmware Upgrade Failure

**Situation**: Firmware upgrade causes issues, need to revert.

**Recovery Steps**:

1. **Use pre-upgrade backup** (created before upgrade)
2. **Restore and downgrade**:
   ```python
   await mcp.call_tool("restore_backup", {
       "site_id": "default",
       "backup_filename": "pre_upgrade_backup.unf",
       "create_pre_restore_backup": True,
       "confirm": True
   })
   ```
3. **Wait for downgrade** (may take 10-15 minutes)
4. **Verify device functionality**

**Recovery Time**: 20-30 minutes

### Scenario 4: Accidental Deletion

**Situation**: Critical firewall rule or network accidentally deleted.

**Recovery Steps**:

1. **Find most recent backup** (hourly/daily)
2. **Restore specific backup**:
   ```python
   await mcp.call_tool("restore_backup", {
       "site_id": "default",
       "backup_filename": "backup_1_hour_ago.unf",
       "create_pre_restore_backup": True,
       "confirm": True
   })
   ```

**Recovery Time**: 5-10 minutes

---

## Cross-Controller Migration

### Migrating to New Controller

**Scenario**: Moving from old controller to new hardware or location.

**Steps**:

1. **Create final backup on old controller**:
   ```python
   backup = await mcp.call_tool("trigger_backup", {
       "site_id": "default",
       "backup_type": "system",  # Full system backup
       "retention_days": -1,  # Keep indefinitely
       "confirm": True
   })
   ```

2. **Download backup file**:
   ```python
   await mcp.call_tool("download_backup", {
       "site_id": "default",
       "backup_filename": backup['filename'],
       "output_path": "/migration/final_backup.unifi",
       "verify_checksum": True
   })
   ```

3. **Setup new controller**:
   - Install UniFi OS (same or newer version)
   - Complete initial setup (minimal config)
   - Connect to MCP Server

4. **Upload and restore backup** on new controller
   - Copy backup file to new controller
   - Restore using MCP tools

5. **Inform devices** of new controller IP:
   - Option A: DHCP Option 43
   - Option B: DNS override for `unifi`
   - Option C: Manual SSH adoption

6. **Monitor device adoption** (may take 5-30 minutes)

### Migration Checklist

- [ ] Verify UniFi OS versions compatible
- [ ] Document current device count
- [ ] Backup SSL certificates
- [ ] Note custom port configurations
- [ ] Export any external integrations
- [ ] Update DNS/DHCP for new controller IP
- [ ] Test with 1-2 devices first
- [ ] Keep old controller running during migration
- [ ] Verify all devices adopted
- [ ] Test all critical functionality
- [ ] Update documentation with new controller info

---

## Troubleshooting

### Backup Creation Fails

**Symptoms**: Backup operation returns error

**Solutions**:
1. Check disk space: `df -h`
2. Verify controller health: Check system logs
3. Retry with dry-run mode first
4. Try network backup instead of system backup
5. Check retention days value (must be -1 or >0)

### Restore Fails to Complete

**Symptoms**: Restore initiated but doesn't finish

**Solutions**:
1. Wait 10-15 minutes (controller restart takes time)
2. Check controller accessibility
3. Review system logs for errors
4. If hung, power cycle controller
5. Restore again from pre-restore backup

### Pre-Restore Backup Not Created

**Symptoms**: Restore proceeds without safety backup

**Solutions**:
1. Ensure `create_pre_restore_backup: True`
2. Check disk space for backup
3. Manually create backup before restore
4. Document current config as fallback

### Backup File Corrupted

**Symptoms**: Validation fails with checksum errors

**Solutions**:
1. Re-download backup file
2. Use older backup
3. Check backup storage for issues
4. Verify backup was fully written
5. Check for disk errors on backup storage

### Devices Don't Reconnect After Restore

**Symptoms**: Devices show offline after restore

**Solutions**:
1. Wait 5-10 minutes for auto-reconnect
2. Power cycle devices
3. Check network connectivity
4. Verify controller IP accessible
5. Force adoption via SSH if needed
6. Check if firewall rules blocking management

### Version Mismatch Warning

**Symptoms**: Backup from different UniFi version

**Solutions**:
1. Check compatibility: backup version vs. current version
2. Upgrade/downgrade controller if needed
3. Review changelog for breaking changes
4. Test restore in lab environment first
5. Consider manual configuration instead

---

## Support

For backup/restore issues:

- **GitHub Issues**: https://github.com/elvis/unifi-mcp-server/issues
- **Documentation**: See `API.md` for tool references
- **Security**: See `SECURITY.md` for vulnerability reporting

---

**Last Updated**: 2025-11-28
**Version**: 0.2.0
**Maintained By**: UniFi MCP Server Team
