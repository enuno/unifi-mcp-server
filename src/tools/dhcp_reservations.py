"""DHCP reservation management tools (local V1 legacy endpoint).

Creates and manages fixed-IP DHCP reservations via the UniFi controller's
``/rest/user`` endpoint. Each "user" in the UniFi controller represents a
known client identified by MAC address; DHCP reservations are just users
with ``use_fixedip=true`` and a ``fixed_ip`` + ``network_id`` set.

The endpoint is on the legacy V1 internal API
(``/proxy/network/api/s/{site}/rest/user``), which accepts API-key auth
on current UDM firmware. Local-gateway only — same gating as
firewall_groups / firewall_policies.
"""

from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..utils import APIError, ResourceNotFoundError, get_logger, log_audit, sanitize_log_message
from ..utils.validators import coerce_bool

logger = get_logger(__name__)


def _ensure_local_api(settings: Settings) -> None:
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "DHCP reservation tools require UNIFI_API_TYPE='local'. "
            "The cloud/integration API does not expose the /rest/user endpoint."
        )


def _endpoint(site_id: str, user_id: str | None = None) -> str:
    suffix = f"/{user_id}" if user_id else ""
    return f"/ea/sites/{site_id}/rest/user{suffix}"


def _unwrap(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [i for i in response if isinstance(i, dict)]
    if isinstance(response, dict):
        inner = response.get("data")
        if isinstance(inner, list):
            return [i for i in inner if isinstance(i, dict)]
        if isinstance(inner, dict):
            return [inner]
    return []


async def list_dhcp_reservations(
    site_id: str,
    settings: Settings,
    network_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all DHCP reservations (clients with fixed IPs).

    Args:
        site_id: Site identifier
        settings: Application settings (must be local)
        network_id: Optional filter by network (VLAN) internal ID

    Returns:
        List of reservation dicts with mac, fixed_ip, name, network_id.
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Listing DHCP reservations for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(_endpoint(site_id))
        except APIError:
            logger.exception(
                sanitize_log_message(f"Failed to list DHCP reservations for site {site_id}")
            )
            raise

        items = _unwrap(response)
        reservations = [
            {
                "id": u.get("_id"),
                "mac": u.get("mac"),
                "name": u.get("name") or u.get("hostname"),
                "fixed_ip": u.get("fixed_ip"),
                "network_id": u.get("network_id"),
                "use_fixedip": u.get("use_fixedip", False),
                "local_dns_record": u.get("local_dns_record"),
                "local_dns_record_enabled": u.get("local_dns_record_enabled", False),
            }
            for u in items
            if u.get("use_fixedip")
        ]

        if network_id:
            reservations = [r for r in reservations if r.get("network_id") == network_id]

        return reservations


async def get_dhcp_reservation(
    mac: str,
    site_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get DHCP reservation for a specific MAC address.

    Returns the reservation dict if the MAC has a fixed IP, otherwise raises
    ResourceNotFoundError.
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Getting DHCP reservation for {mac}"))
        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(_endpoint(site_id))
        items = _unwrap(response)

        mac_lower = mac.lower()
        for u in items:
            if (u.get("mac") or "").lower() == mac_lower and u.get("use_fixedip"):
                return {
                    "id": u.get("_id"),
                    "mac": u.get("mac"),
                    "name": u.get("name") or u.get("hostname"),
                    "fixed_ip": u.get("fixed_ip"),
                    "network_id": u.get("network_id"),
                    "use_fixedip": True,
                    "local_dns_record": u.get("local_dns_record"),
                    "local_dns_record_enabled": u.get("local_dns_record_enabled", False),
                }

        raise ResourceNotFoundError("dhcp_reservation", mac)


async def create_dhcp_reservation(
    mac: str,
    fixed_ip: str,
    network_id: str,
    site_id: str,
    settings: Settings,
    name: str | None = None,
    local_dns_record: str | None = None,
    local_dns_record_enabled: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a DHCP reservation (fixed IP) for a client MAC.

    If the MAC already exists in the controller's known-clients table, the
    controller merges the reservation into the existing entry. If it's a
    new MAC, a new user entry is created.

    Args:
        mac: Client MAC address (e.g. ``"aa:bb:cc:dd:ee:ff"``)
        fixed_ip: Fixed IP to assign (must be within the network's DHCP range
            or static allocation pool)
        network_id: Internal network (VLAN) ID where the reservation applies.
            Use ``list_networks`` or ``list_firewall_zones_v2`` to find IDs.
        site_id: Site identifier
        settings: Application settings (must be local)
        name: Friendly name for the client (optional)
        local_dns_record: Local DNS hostname to register (optional)
        local_dns_record_enabled: Enable local DNS registration
        confirm: REQUIRED True for mutating operations
        dry_run: Preview without applying

    Returns:
        Created / merged reservation dict.
    """
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    payload: dict[str, Any] = {
        "mac": mac.lower(),
        "use_fixedip": True,
        "fixed_ip": fixed_ip,
        "network_id": network_id,
    }
    if name is not None:
        payload["name"] = name
    if local_dns_record is not None:
        payload["local_dns_record"] = local_dns_record
        payload["local_dns_record_enabled"] = local_dns_record_enabled

    if dry_run_bool:
        logger.info(
            sanitize_log_message(f"DRY RUN: Would create DHCP reservation {mac} → {fixed_ip}")
        )
        return {"status": "dry_run", "payload": payload}

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(f"Creating DHCP reservation {mac} → {fixed_ip} on site {site_id}")
        )
        if not client.is_authenticated:
            await client.authenticate()

        response = await client.post(_endpoint(site_id), json_data=payload)
        items = _unwrap(response)
        if not items:
            raise APIError(f"DHCP reservation POST returned no data for {mac}")
        data = items[0]

        log_audit(
            operation="create_dhcp_reservation",
            parameters={"site_id": site_id, "mac": mac, "fixed_ip": fixed_ip},
            result="success",
            site_id=site_id,
        )

        return {
            "id": data.get("_id"),
            "mac": data.get("mac"),
            "name": data.get("name"),
            "fixed_ip": data.get("fixed_ip"),
            "network_id": data.get("network_id"),
            "use_fixedip": data.get("use_fixedip", False),
        }


async def update_dhcp_reservation(
    mac: str,
    site_id: str,
    settings: Settings,
    fixed_ip: str | None = None,
    name: str | None = None,
    network_id: str | None = None,
    local_dns_record: str | None = None,
    local_dns_record_enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing DHCP reservation by MAC.

    Looks up the client by MAC, then PUTs the overrides. The V1 ``rest/user``
    endpoint accepts partial updates.

    Args:
        mac: Client MAC address to update
        site_id: Site identifier
        settings: Application settings (must be local)
        fixed_ip: New fixed IP (optional — only if changing)
        name: New friendly name
        network_id: Move reservation to a different network
        local_dns_record: Update local DNS hostname
        local_dns_record_enabled: Toggle local DNS registration
        confirm: REQUIRED True
        dry_run: Preview without applying
    """
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    # Find the user entry by MAC.
    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(_endpoint(site_id))
        items = _unwrap(response)
        mac_lower = mac.lower()
        user_entry = None
        for u in items:
            if (u.get("mac") or "").lower() == mac_lower:
                user_entry = u
                break

        if not user_entry:
            raise ResourceNotFoundError("dhcp_reservation", mac)

        user_id = user_entry["_id"]

        overrides: dict[str, Any] = {}
        if fixed_ip is not None:
            overrides["fixed_ip"] = fixed_ip
            # A fixed_ip is inert unless use_fixedip is also set: the controller
            # stores the address but does not activate the reservation, so it
            # never appears in list_dhcp_reservations (which filters on this
            # flag). Setting the IP always implies enabling the reservation.
            overrides["use_fixedip"] = True
        if name is not None:
            overrides["name"] = name
        if network_id is not None:
            overrides["network_id"] = network_id
        if local_dns_record is not None:
            overrides["local_dns_record"] = local_dns_record
        if local_dns_record_enabled is not None:
            overrides["local_dns_record_enabled"] = local_dns_record_enabled

        if dry_run_bool:
            logger.info(sanitize_log_message(f"DRY RUN: Would update DHCP reservation for {mac}"))
            return {
                "status": "dry_run",
                "user_id": user_id,
                "changes": overrides,
            }

        logger.info(sanitize_log_message(f"Updating DHCP reservation for {mac} (user {user_id})"))

        put_response = await client.put(_endpoint(site_id, user_id), json_data=overrides)
        data = _unwrap(put_response)
        if not data:
            raise APIError(f"DHCP reservation PUT returned no data for {mac}")

        log_audit(
            operation="update_dhcp_reservation",
            parameters={"site_id": site_id, "mac": mac, **overrides},
            result="success",
            site_id=site_id,
        )

        return {
            "id": data[0].get("_id"),
            "mac": data[0].get("mac"),
            "name": data[0].get("name"),
            "fixed_ip": data[0].get("fixed_ip"),
            "network_id": data[0].get("network_id"),
            "use_fixedip": data[0].get("use_fixedip", False),
        }


async def remove_dhcp_reservation(
    mac: str,
    site_id: str,
    settings: Settings,
    forget_client: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Remove a DHCP reservation for a client MAC.

    By default this only clears the fixed-IP assignment (sets
    ``use_fixedip=false``) while keeping the client's history in the
    controller. Pass ``forget_client=True`` to remove the client entry
    entirely via ``cmd/stamgr forget-sta``.

    Args:
        mac: Client MAC address
        site_id: Site identifier
        settings: Application settings (must be local)
        forget_client: If True, remove the entire client entry (not just the
            reservation). This erases all history (first-seen, stats, name).
        confirm: REQUIRED True
        dry_run: Preview without applying
    """
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    if dry_run_bool:
        action = "forget_client" if forget_client else "clear_fixed_ip"
        logger.info(sanitize_log_message(f"DRY RUN: Would {action} for {mac}"))
        return {"status": "dry_run", "mac": mac, "action": action}

    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()

        if forget_client:
            logger.info(sanitize_log_message(f"Forgetting client {mac} from site {site_id}"))
            await client.post(
                f"/ea/sites/{site_id}/cmd/stamgr",
                json_data={"cmd": "forget-sta", "macs": [mac.lower()]},
            )
            action = "forgotten"
        else:
            # Find the user entry to get the _id for PUT.
            response = await client.get(_endpoint(site_id))
            items = _unwrap(response)
            mac_lower = mac.lower()
            user_entry = None
            for u in items:
                if (u.get("mac") or "").lower() == mac_lower:
                    user_entry = u
                    break

            if not user_entry:
                raise ResourceNotFoundError("dhcp_reservation", mac)

            user_id = user_entry["_id"]
            logger.info(
                sanitize_log_message(f"Clearing DHCP reservation for {mac} (user {user_id})")
            )
            await client.put(
                _endpoint(site_id, user_id),
                json_data={"use_fixedip": False},
            )
            action = "reservation_cleared"

        log_audit(
            operation="remove_dhcp_reservation",
            parameters={"site_id": site_id, "mac": mac, "forget_client": forget_client},
            result="success",
            site_id=site_id,
        )

        return {"status": "success", "mac": mac, "action": action}
