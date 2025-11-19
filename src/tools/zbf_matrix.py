"""Zone-Based Firewall matrix management tools.

⚠️ IMPORTANT: All tools in this file are DEPRECATED as of 2025-11-18.

Endpoint verification on UniFi Express 7 and UDM Pro (API v10.0.156) confirmed
that the zone policy matrix and application blocking endpoints DO NOT EXIST.

The following endpoints were tested and returned 404:
- /sites/{siteId}/firewall/policies/zone-matrix
- /sites/{siteId}/firewall/policies/zones/{zoneId}
- /sites/{siteId}/firewall/zones/{zoneId}/policies
- /sites/{siteId}/firewall/zones/{zoneId}/applications/block
- /sites/{siteId}/firewall/zones/{zoneId}/applications/blocked

Workarounds:
- Configure zone policies manually in UniFi Console UI
- Use traditional ACL rules (/sites/{siteId}/acls) for IP-based filtering
- Use DPI categories for application blocking at network level

See tests/verification/PHASE2_FINDINGS.md for complete verification report.
"""

from typing import Any

from ..api.client import UniFiClient  # noqa: F401
from ..config import Settings
from ..models.zbf_matrix import ApplicationBlockRule, ZonePolicy, ZonePolicyMatrix  # noqa: F401
from ..utils import audit_action, get_logger, validate_confirmation  # noqa: F401

logger = get_logger(__name__)


async def get_zbf_matrix(site_id: str, settings: Settings) -> dict[str, Any]:
    """Retrieve zone-to-zone policy matrix.

    ⚠️ **DEPRECATED - ENDPOINT DOES NOT EXIST**

    This endpoint has been verified to NOT EXIST in UniFi Network API v10.0.156.
    Tested on UniFi Express 7 and UDM Pro on 2025-11-18.

    The zone policy matrix must be configured via the UniFi Console UI.
    Use traditional ACL rules (/sites/{siteId}/acls) as a workaround.

    See tests/verification/PHASE2_FINDINGS.md for details.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Zone policy matrix with all zones and policies

    Raises:
        NotImplementedError: This endpoint does not exist in the UniFi API
    """
    logger.warning(
        "get_zbf_matrix called but endpoint does not exist in UniFi API v10.0.156. "
        "Configure zone policies via UniFi Console UI instead."
    )
    raise NotImplementedError(
        "Zone policy matrix endpoint does not exist in UniFi Network API v10.0.156. "
        "Verified on U7 Express and UDM Pro (2025-11-18). "
        "Configure zone policies manually in UniFi Console. "
        "See tests/verification/PHASE2_FINDINGS.md for details."
    )


async def get_zone_policies(site_id: str, zone_id: str, settings: Settings) -> list[dict[str, Any]]:
    """Get policies for a specific zone.

    ⚠️ **DEPRECATED - ENDPOINT DOES NOT EXIST**

    This endpoint has been verified to NOT EXIST in UniFi Network API v10.0.156.
    Tested on UniFi Express 7 and UDM Pro on 2025-11-18.

    Zone policies must be configured via the UniFi Console UI.

    See tests/verification/PHASE2_FINDINGS.md for details.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        settings: Application settings

    Returns:
        List of policies for the zone

    Raises:
        NotImplementedError: This endpoint does not exist in the UniFi API
    """
    logger.warning(
        f"get_zone_policies called for zone {zone_id} but endpoint does not exist in UniFi API v10.0.156."
    )
    raise NotImplementedError(
        "Zone policies endpoint does not exist in UniFi Network API v10.0.156. "
        "Verified on U7 Express and UDM Pro (2025-11-18). "
        "Configure zone policies manually in UniFi Console. "
        "See tests/verification/PHASE2_FINDINGS.md for details."
    )


async def update_zbf_policy(
    site_id: str,
    source_zone_id: str,
    destination_zone_id: str,
    action: str,
    settings: Settings,
    description: str | None = None,
    priority: int | None = None,
    enabled: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Modify inter-zone firewall policy.

    ⚠️ **DEPRECATED - ENDPOINT DOES NOT EXIST**

    This endpoint has been verified to NOT EXIST in UniFi Network API v10.0.156.
    Tested on UniFi Express 7 and UDM Pro on 2025-11-18.

    Zone-to-zone policies must be configured via the UniFi Console UI.

    See tests/verification/PHASE2_FINDINGS.md for details.

    Args:
        site_id: Site identifier
        source_zone_id: Source zone identifier
        destination_zone_id: Destination zone identifier
        action: Policy action (allow/deny)
        settings: Application settings
        description: Policy description
        priority: Policy priority
        enabled: Whether policy is enabled
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated policy

    Raises:
        NotImplementedError: This endpoint does not exist in the UniFi API
    """
    logger.warning(
        f"update_zbf_policy called for {source_zone_id} -> {destination_zone_id} "
        "but endpoint does not exist in UniFi API v10.0.156."
    )
    raise NotImplementedError(
        "Zone policy update endpoint does not exist in UniFi Network API v10.0.156. "
        "Verified on U7 Express and UDM Pro (2025-11-18). "
        "Configure zone policies manually in UniFi Console. "
        "See tests/verification/PHASE2_FINDINGS.md for details."
    )


async def block_application_by_zone(
    site_id: str,
    zone_id: str,
    application_id: str,
    settings: Settings,
    action: str = "block",
    enabled: bool = True,
    description: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Block applications using zone-based rules.

    ⚠️ **DEPRECATED - ENDPOINT DOES NOT EXIST**

    This endpoint has been verified to NOT EXIST in UniFi Network API v10.0.156.
    Tested on UniFi Express 7 and UDM Pro on 2025-11-18.

    Application blocking per zone is not available via the API.
    Use DPI categories for application blocking at the network level instead.

    See tests/verification/PHASE2_FINDINGS.md for details.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        application_id: DPI application identifier
        settings: Application settings
        action: Action to take (block/allow)
        enabled: Whether rule is enabled
        description: Rule description
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created application block rule

    Raises:
        NotImplementedError: This endpoint does not exist in the UniFi API
    """
    logger.warning(
        f"block_application_by_zone called for zone {zone_id}, app {application_id} "
        "but endpoint does not exist in UniFi API v10.0.156."
    )
    raise NotImplementedError(
        "Application blocking per zone endpoint does not exist in UniFi Network API v10.0.156. "
        "Verified on U7 Express and UDM Pro (2025-11-18). "
        "Use DPI categories for application blocking at network level. "
        "See tests/verification/PHASE2_FINDINGS.md for details."
    )


async def list_blocked_applications(
    site_id: str, zone_id: str | None = None, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """List applications blocked per zone.

    ⚠️ **DEPRECATED - ENDPOINT DOES NOT EXIST**

    This endpoint has been verified to NOT EXIST in UniFi Network API v10.0.156.
    Tested on UniFi Express 7 and UDM Pro on 2025-11-18.

    Application blocking per zone is not available via the API.

    See tests/verification/PHASE2_FINDINGS.md for details.

    Args:
        site_id: Site identifier
        zone_id: Optional zone identifier to filter by
        settings: Application settings

    Returns:
        List of blocked applications

    Raises:
        NotImplementedError: This endpoint does not exist in the UniFi API
    """
    logger.warning(
        f"list_blocked_applications called for site {site_id} "
        "but endpoint does not exist in UniFi API v10.0.156."
    )
    raise NotImplementedError(
        "Blocked applications list endpoint does not exist in UniFi Network API v10.0.156. "
        "Verified on U7 Express and UDM Pro (2025-11-18). "
        "See tests/verification/PHASE2_FINDINGS.md for details."
    )


async def get_zone_matrix_policy(
    site_id: str,
    source_zone_id: str,
    destination_zone_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a specific zone-to-zone policy.

    ⚠️ **DEPRECATED - ENDPOINT DOES NOT EXIST**

    This endpoint has been verified to NOT EXIST in UniFi Network API v10.0.156.
    Tested on UniFi Express 7 and UDM Pro on 2025-11-18.

    Zone-to-zone policies must be configured via the UniFi Console UI.

    See tests/verification/PHASE2_FINDINGS.md for details.

    Args:
        site_id: Site identifier
        source_zone_id: Source zone identifier
        destination_zone_id: Destination zone identifier
        settings: Application settings

    Returns:
        Zone-to-zone policy details

    Raises:
        NotImplementedError: This endpoint does not exist in the UniFi API
    """
    logger.warning(
        f"get_zone_matrix_policy called for {source_zone_id} -> {destination_zone_id} "
        "but endpoint does not exist in UniFi API v10.0.156."
    )
    raise NotImplementedError(
        "Zone matrix policy endpoint does not exist in UniFi Network API v10.0.156. "
        "Verified on U7 Express and UDM Pro (2025-11-18). "
        "Configure zone policies manually in UniFi Console. "
        "See tests/verification/PHASE2_FINDINGS.md for details."
    )


async def delete_zbf_policy(
    site_id: str,
    source_zone_id: str,
    destination_zone_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete a zone-to-zone policy (revert to default action).

    ⚠️ **DEPRECATED - ENDPOINT DOES NOT EXIST**

    This endpoint has been verified to NOT EXIST in UniFi Network API v10.0.156.
    Tested on UniFi Express 7 and UDM Pro on 2025-11-18.

    Zone-to-zone policies must be configured via the UniFi Console UI.

    See tests/verification/PHASE2_FINDINGS.md for details.

    Args:
        site_id: Site identifier
        source_zone_id: Source zone identifier
        destination_zone_id: Destination zone identifier
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion confirmation

    Raises:
        NotImplementedError: This endpoint does not exist in the UniFi API
    """
    logger.warning(
        f"delete_zbf_policy called for {source_zone_id} -> {destination_zone_id} "
        "but endpoint does not exist in UniFi API v10.0.156."
    )
    raise NotImplementedError(
        "Zone policy delete endpoint does not exist in UniFi Network API v10.0.156. "
        "Verified on U7 Express and UDM Pro (2025-11-18). "
        "Configure zone policies manually in UniFi Console. "
        "See tests/verification/PHASE2_FINDINGS.md for details."
    )
