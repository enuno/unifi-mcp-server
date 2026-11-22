"""Matter and Thread inventory tools (Network 11 private v2 API).

Network 11 added a Settings > Matter page backed by two read routes on the
local private v2 API:

* ``GET /proxy/network/v2/api/site/{site}/thread-networks``
  — "List detected Thread networks for the site"
* ``GET /proxy/network/v2/api/site/{site}/matter/nodes``
  — "List the site's Matter nodes and their commissioning state"

Both route paths and both operation summaries are **derived** from the
UniFi Network Application 11.0.97 distribution, not from a published API
contract: neither the Site Manager v1.0.0 nor the Network v11.0.97
Integration API contains a Matter or Thread path. The evidence record is
``docs/research/matter-thread-network-11-discovery.md``.

Verification status, honestly stated:

* Both routes answer **404** on Network 10.6.111 under this server's API-key
  auth, while a control route in the same v2 family
  (``.../trafficroutes``) answers 200 with the same credential. The 404 is
  therefore route absence on 10.6, not an authentication refusal — this
  server's API key is accepted on this route family.
* ``GET /proxy/network/v2/api/site/{site}/clients/active``, which
  :func:`list_matter_thread_clients` reads, **is** live-verified on
  10.6.111: it answers 200 and its records carry the ``type``
  discriminator this tool filters on.
* No Network 11 controller was available, so a successful Matter or Thread
  read has **not** been observed. These tools are implemented against the
  derived contract and are mock-tested only.

A controller that predates the feature answers 404, which these tools
surface as an empty list plus an explicit ``supported: false`` so a caller
can tell "no Matter devices" from "this controller has no Matter support".
"""

from __future__ import annotations

from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.matter import MATTER_THREAD_CLIENT_TYPE, MatterNode, MatterThreadClient, ThreadNetwork
from ..utils import ResourceNotFoundError, get_logger, sanitize_log_message, validate_site_id
from ..utils.tool_kind import read_tool

logger = get_logger(__name__)


def _ensure_local_api(settings: Settings) -> None:
    """Matter and Thread inventory is only reachable through the local proxy."""
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "Matter and Thread tools require UNIFI_API_TYPE='local'. Neither the "
            "Site Manager API nor the Network Integration API publishes a Matter "
            "or Thread path; the inventory is only available through the local "
            "gateway's private v2 routes."
        )


def _records(response: Any) -> list[dict[str, Any]]:
    """Return the record dicts from a bare-list or ``{"data": [...]}`` response."""
    if isinstance(response, list):
        return [r for r in response if isinstance(r, dict)]
    if isinstance(response, dict):
        inner = response.get("data")
        if isinstance(inner, list):
            return [r for r in inner if isinstance(r, dict)]
    return []


#: A v2 route that exists on every Network release this server supports, used
#: to tell "this controller lacks the feature" apart from "that site does not
#: exist". Both answer 404, so the status code alone cannot distinguish them.
#: Verified live on Network 10.6.111: the real site answers 200 here, and a
#: site name that cannot exist answers 404.
_SITE_CONTROL_ROUTE = "/clients/active"


async def _site_exists(client: UniFiClient, settings: Settings, site_id: str) -> bool:
    """Return whether the controller knows *site_id*.

    Asked only after a feature route 404s, so the extra request is not on the
    success path.
    """
    endpoint = f"{settings.get_v2_api_path(site_id)}{_SITE_CONTROL_ROUTE}"
    try:
        await client.get(endpoint)
    except ResourceNotFoundError:
        return False
    return True


async def _get_v2(
    settings: Settings,
    site_id: str,
    suffix: str,
    *,
    feature_route: bool,
) -> tuple[list[dict[str, Any]], bool]:
    """GET a v2 site route and return its records plus controller support.

    A 404 is ambiguous on this API: the v2 routes answer 404 both for a
    feature the Network release does not have *and* for a site that does not
    exist (confirmed live on 10.6.111, where a nonexistent site name 404s on
    a route that otherwise answers 200). Reporting the second case as
    ``supported: false`` would turn a mistyped site id into a confident,
    wrong claim that the controller lacks Matter support.

    So a 404 is disambiguated rather than assumed:

    * ``feature_route=True`` — on 404, check the site against a control route
      that every supported release serves. If the site is unknown the 404 is
      re-raised; only a 404 on a site that *does* exist means "unsupported".
    * ``feature_route=False`` — the route itself predates the feature, so a
      404 can only mean an unknown site and always propagates.

    Every other failure propagates either way: a 401, 429 or 5xx must never
    be reported as "unsupported".
    """
    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()
        # The site UUID -> short-name translation is applied centrally by
        # UniFiClient._normalize_endpoint, so it is not repeated here.
        endpoint = f"{settings.get_v2_api_path(site_id)}{suffix}"
        try:
            response = await client.get(endpoint)
        except ResourceNotFoundError:
            if not feature_route:
                raise
            if not await _site_exists(client, settings, site_id):
                raise
            return [], False
        return _records(response), True


@read_tool
async def list_thread_networks(site_id: str, settings: Settings) -> dict[str, Any]:
    """List the Thread networks a site detects (Network 11+).

    A site reports the Thread networks it runs and may also detect a
    neighbouring network it does not control, so a result with no border
    routers is normal rather than an error.

    Border-router identification internals (``fingerprint``, ``host``,
    ``domainName``, ``stateBitmap``, ``sequenceNumber``,
    ``backboneRouterPort``) are deliberately not surfaced, and Matter fabric
    identifiers are reduced to a count.

    Args:
        site_id: Site identifier
        settings: Application settings (must be configured for local API)

    Returns:
        ``{"supported": bool, "count": int, "thread_networks": [...]}``.
        ``supported`` is ``False`` when the controller has no Thread route,
        which is how a pre-Network-11 release answers.

    Raises:
        NotImplementedError: If the server is not in local API mode.
        ValidationError: If the site identifier is malformed.
    """
    _ensure_local_api(settings)
    site_id = validate_site_id(site_id)

    records, supported = await _get_v2(settings, site_id, "/thread-networks", feature_route=True)
    networks = [ThreadNetwork.from_api(record) for record in records]

    if not supported:
        logger.info(
            sanitize_log_message(
                f"Thread inventory is unavailable on site '{site_id}': the controller "
                "has no thread-networks route (Network 11+ required)"
            )
        )
    else:
        logger.info(
            sanitize_log_message(
                f"Retrieved {len(networks)} Thread network(s) for site '{site_id}'"
            )
        )

    return {
        "supported": supported,
        "count": len(networks),
        "thread_networks": [network.model_dump() for network in networks],
    }


@read_tool
async def list_matter_nodes(site_id: str, settings: Settings) -> dict[str, Any]:
    """List the site's Matter nodes and their commissioning state (Network 11+).

    A node's Matter pairing code (``setupCode``) is **never** returned: it is
    a live credential that would let a holder commission the device into
    another fabric. Each node's ``thread_client_id`` can be joined to a
    ``MATTER_THREAD`` record from :func:`list_matter_thread_clients` for its
    network identity.

    Args:
        site_id: Site identifier
        settings: Application settings (must be configured for local API)

    Returns:
        ``{"supported": bool, "count": int, "matter_nodes": [...]}``.
        ``supported`` is ``False`` when the controller has no Matter route.

    Raises:
        NotImplementedError: If the server is not in local API mode.
        ValidationError: If the site identifier is malformed.
    """
    _ensure_local_api(settings)
    site_id = validate_site_id(site_id)

    records, supported = await _get_v2(settings, site_id, "/matter/nodes", feature_route=True)
    nodes = [MatterNode.from_api(record) for record in records]

    if not supported:
        logger.info(
            sanitize_log_message(
                f"Matter inventory is unavailable on site '{site_id}': the controller "
                "has no matter/nodes route (Network 11+ required)"
            )
        )
    else:
        logger.info(
            sanitize_log_message(f"Retrieved {len(nodes)} Matter node(s) for site '{site_id}'")
        )

    return {
        "supported": supported,
        "count": len(nodes),
        "matter_nodes": [node.model_dump() for node in nodes],
    }


@read_tool
async def list_matter_thread_clients(site_id: str, settings: Settings) -> dict[str, Any]:
    """List the site's Matter/Thread devices from the active-client inventory.

    Matter nodes join the client inventory as records whose ``type`` is
    ``MATTER_THREAD``, so this is the client-side view of the same devices
    :func:`list_matter_nodes` reports from the Matter service. The route and
    its ``type`` discriminator are live-verified on Network 10.6.111; the
    ``MATTER_THREAD`` value itself requires a Network 11 site with a
    commissioned node and has not been observed.

    Unlike the Matter and Thread routes, this route exists before Network 11,
    so an empty result on an older controller means "no Matter/Thread
    clients", not "unsupported" — and because the route is always present, a
    404 from it can only mean an unknown site and is raised rather than
    reported as a lack of support. ``supported`` is therefore always ``True``
    here, and is kept only so the three tools share one result shape.

    Records are projected through an allowlist: the controller's active-client
    record is wide and carries fields such as ``fingerprint`` and ``ip`` that
    this server does not republish.

    Args:
        site_id: Site identifier
        settings: Application settings (must be configured for local API)

    Returns:
        ``{"supported": bool, "count": int, "clients": [...]}`` where each
        client is the controller's record for a ``MATTER_THREAD`` device.

    Raises:
        NotImplementedError: If the server is not in local API mode.
        ValidationError: If the site identifier is malformed.
    """
    _ensure_local_api(settings)
    site_id = validate_site_id(site_id)

    records, supported = await _get_v2(settings, site_id, _SITE_CONTROL_ROUTE, feature_route=False)
    matched = [
        MatterThreadClient.from_api(record)
        for record in records
        if record.get("type") == MATTER_THREAD_CLIENT_TYPE
    ]

    logger.info(
        sanitize_log_message(
            f"Retrieved {len(matched)} Matter/Thread client(s) of {len(records)} "
            f"active client(s) for site '{site_id}'"
        )
    )

    return {
        "supported": supported,
        "count": len(matched),
        "clients": [client.model_dump() for client in matched],
    }
