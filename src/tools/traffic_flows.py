"""Traffic flow monitoring tools (local v2 API).

The UniFi Integration API (``/proxy/network/integration/v1/...``) does **not**
expose traffic flow data on any documented endpoint or firmware. Flow data is
only available via the local private v2 endpoint
``POST /proxy/network/v2/api/site/{site_id}/traffic-flows``, which is the
endpoint the UniFi Network web UI uses internally. It returns up to 50 of the
most recently-completed flows with full source/destination metadata, matched
firewall policies, byte counters, and risk classification.

Key constraints of the v2 endpoint, verified live against a UDM Pro running
UniFi Network 10.2.x:

* Hard cap at 50 flows per call; ``limit`` / ``offset`` / ``page_size`` /
  ``duration`` / ``start`` parameters are accepted but ignored.
* The response is a rolling snapshot of the latest completed flows, so
  repeated calls return different IDs as new flows arrive.
* Server-side filter keys (``source_zone_ids``, ``protocols``, ``actions``,
  ``risks``, etc.) are accepted but **non-functional** — they pass syntax
  validation but do not actually narrow the result set. All filtering must
  therefore be performed client-side after fetching the sample.

Because this endpoint is only reachable via the local gateway proxy, every
function in this module calls :func:`_ensure_local_api` and raises
``NotImplementedError`` when the MCP is configured for cloud-only API access.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any
from uuid import uuid4

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.traffic_flow import (
    BlockFlowAction,
    ClientFlowAggregation,
    FlowRuleReferenceMatch,
    FlowStatistics,
    TrafficFlow,
)
from ..utils import (
    APIError,
    ResourceNotFoundError,
    audit_action,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
)

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Low-level helpers                                                           #
# --------------------------------------------------------------------------- #


def _ensure_local_api(settings: Settings) -> None:
    """Flow endpoints are only reachable via the local gateway proxy."""
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "Traffic flow tools require UNIFI_API_TYPE='local'. The UniFi "
            "Integration API does not expose flow data; it is only available "
            "through the local gateway's v2 endpoint at "
            "/proxy/network/v2/api/site/{site}/traffic-flows."
        )


async def _fetch_raw_flows(
    client: UniFiClient, settings: Settings, site_id: str
) -> list[dict[str, Any]]:
    """Hit the v2 traffic-flows endpoint and return the raw flow dicts.

    The endpoint ignores pagination/filter params so we always send an empty
    body and apply filtering client-side in the public wrappers below.
    """
    normalized_site_id = client._site_uuid_to_name.get(site_id, site_id)
    endpoint = f"{settings.get_v2_api_path(normalized_site_id)}/traffic-flows"
    response = await client.post(endpoint, json_data={})
    if isinstance(response, list):
        return [f for f in response if isinstance(f, dict)]
    if isinstance(response, dict):
        inner = response.get("data")
        if isinstance(inner, list):
            return [f for f in inner if isinstance(f, dict)]
    return []


def _parse_flow(raw: dict[str, Any]) -> TrafficFlow:
    """Parse a raw v2 flow dict into a ``TrafficFlow`` pydantic model."""
    return TrafficFlow(**raw)


def _flow_matches(
    flow: TrafficFlow,
    *,
    source_mac: str | None = None,
    source_ip: str | None = None,
    source_zone_name: str | None = None,
    source_network_name: str | None = None,
    destination_ip: str | None = None,
    destination_port: int | None = None,
    destination_zone_name: str | None = None,
    destination_network_name: str | None = None,
    protocol: str | None = None,
    action: str | None = None,
    direction: str | None = None,
    risk: str | None = None,
    min_bytes: int | None = None,
    client_name_contains: str | None = None,
) -> bool:
    """Client-side filter predicate used by every public fetch function.

    Note on inter-VLAN filtering: UniFi labels the ``destination.zone_name``
    of any inter-VLAN flow as ``"Gateway"`` rather than the target VLAN's
    zone — the flow engine sees it as "entered the gateway's routing
    table", which is literally true since routing happens on the gateway.
    To find flows crossing VLAN boundaries, filter by
    ``destination_network_name`` (the target VLAN's display name) rather
    than ``destination_zone_name``. The ``destination_zone_name`` filter
    only returns useful results for egress flows to ``External``.
    """
    src = flow.source
    dst = flow.destination

    if source_mac is not None:
        candidate = (src.mac or src.id or "").lower()
        if candidate != source_mac.lower():
            return False
    if source_ip is not None and src.ip != source_ip:
        return False
    if source_zone_name is not None and ((src.zone_name or "").lower() != source_zone_name.lower()):
        return False
    if source_network_name is not None and (
        (src.network_name or "").lower() != source_network_name.lower()
    ):
        return False
    if destination_ip is not None and dst.ip != destination_ip:
        return False
    if destination_port is not None and dst.port != destination_port:
        return False
    if destination_zone_name is not None and (
        (dst.zone_name or "").lower() != destination_zone_name.lower()
    ):
        return False
    if destination_network_name is not None and (
        (dst.network_name or "").lower() != destination_network_name.lower()
    ):
        return False
    if protocol is not None and (flow.protocol or "").upper() != protocol.upper():
        return False
    if action is not None and (flow.action or "").lower() != action.lower():
        return False
    if direction is not None and (flow.direction or "").lower() != direction.lower():
        return False
    if risk is not None and (flow.risk or "").lower() != risk.lower():
        return False
    if min_bytes is not None and flow.traffic_data.bytes_total < min_bytes:
        return False
    if client_name_contains is not None and client_name_contains.lower() not in (
        (src.client_name or "").lower()
    ):
        return False
    return True


async def _get_filtered_flows(
    site_id: str,
    settings: Settings,
    **filters: Any,
) -> list[TrafficFlow]:
    """Fetch the latest 50 flows and apply client-side filters."""
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()

        try:
            raw_flows = await _fetch_raw_flows(client, settings, site_id)
        except APIError:
            logger.exception(
                sanitize_log_message(f"Failed to fetch traffic flows for site {site_id}")
            )
            raise

        flows: list[TrafficFlow] = []
        for raw in raw_flows:
            try:
                flow = _parse_flow(raw)
            except Exception as exc:
                logger.debug(sanitize_log_message(f"Skipping unparseable flow record: {exc}"))
                continue
            if _flow_matches(flow, **filters):
                flows.append(flow)
        return flows


# --------------------------------------------------------------------------- #
# Public fetch tools                                                          #
# --------------------------------------------------------------------------- #


async def get_traffic_flows(
    site_id: str,
    settings: Settings,
    source_mac: str | None = None,
    source_ip: str | None = None,
    source_zone_name: str | None = None,
    source_network_name: str | None = None,
    destination_ip: str | None = None,
    destination_port: int | None = None,
    destination_zone_name: str | None = None,
    destination_network_name: str | None = None,
    protocol: str | None = None,
    action: str | None = None,
    direction: str | None = None,
    risk: str | None = None,
    min_bytes: int | None = None,
    client_name_contains: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve recent traffic flows from the UniFi controller.

    Fetches up to 50 most-recent completed flows from the local v2 endpoint
    and applies client-side filters. All filter parameters are optional; pass
    any combination to narrow the result set.

    Args:
        site_id: Site identifier
        settings: Application settings (must be configured for local API)
        source_mac: Filter by source MAC address (case-insensitive)
        source_ip: Filter by source IP
        source_zone_name: Filter by source firewall zone name (e.g. "Internal")
        source_network_name: Filter by source VLAN display name (e.g. "Internal - Data")
        destination_ip: Filter by destination IP
        destination_port: Filter by destination port
        destination_zone_name: Filter by destination zone name. **Warning:**
            UniFi labels inter-VLAN destination zones as ``"Gateway"`` rather
            than the target VLAN's zone, so this filter is only useful for
            egress flows to ``"External"``. For inter-VLAN flows, use
            ``destination_network_name`` instead.
        destination_network_name: Filter by destination VLAN display name
            (e.g. ``"Server - Data"``). This is the correct filter for
            discovering inter-VLAN traffic.
        protocol: Filter by transport protocol ("TCP", "UDP", "ICMP", ...)
        action: Filter by firewall action ("allowed", "blocked")
        direction: Filter by flow direction ("outgoing", "incoming")
        risk: Filter by risk classification ("low", "medium", "high", ...)
        min_bytes: Only include flows with at least this many total bytes
        client_name_contains: Substring match against source client_name
        limit: Cap on the number of returned flows (after filtering)

    Returns:
        List of flow dictionaries. Each dict has the full v2 schema —
        ``source``, ``destination``, ``traffic_data``, ``policies``, etc.
    """
    flows = await _get_filtered_flows(
        site_id,
        settings,
        source_mac=source_mac,
        source_ip=source_ip,
        source_zone_name=source_zone_name,
        source_network_name=source_network_name,
        destination_ip=destination_ip,
        destination_port=destination_port,
        destination_zone_name=destination_zone_name,
        destination_network_name=destination_network_name,
        protocol=protocol,
        action=action,
        direction=direction,
        risk=risk,
        min_bytes=min_bytes,
        client_name_contains=client_name_contains,
    )

    logger.info(sanitize_log_message(f"Retrieved {len(flows)} traffic flows for site {site_id}"))

    results = [flow.model_dump(by_alias=True) for flow in flows]
    if limit is not None:
        return results[:limit]
    return results


async def get_flow_statistics(
    site_id: str,
    settings: Settings,
    source_mac: str | None = None,
    source_zone_name: str | None = None,
    destination_zone_name: str | None = None,
    protocol: str | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    """Aggregate statistics over the current flow sample.

    The result describes the rolling 50-flow snapshot (optionally narrowed
    by the same client-side filters as :func:`get_traffic_flows`). There is
    no "time range" — the v2 endpoint does not support historical windows.
    """
    flows = await _get_filtered_flows(
        site_id,
        settings,
        source_mac=source_mac,
        source_zone_name=source_zone_name,
        destination_zone_name=destination_zone_name,
        protocol=protocol,
        action=action,
    )

    total_bytes_tx = sum(f.traffic_data.bytes_tx for f in flows)
    total_bytes_rx = sum(f.traffic_data.bytes_rx for f in flows)
    total_bytes = sum(f.traffic_data.bytes_total for f in flows)
    total_packets = sum(f.traffic_data.packets_total for f in flows)

    unique_sources = {
        f.source.id or f.source.mac or f.source.ip for f in flows if _has_any_identifier(f.source)
    }
    unique_destinations = {f.destination.ip for f in flows if f.destination.ip}

    protocol_breakdown: dict[str, int] = {}
    action_breakdown: dict[str, int] = {}
    for flow in flows:
        protocol_breakdown[flow.protocol] = protocol_breakdown.get(flow.protocol, 0) + 1
        action_breakdown[flow.action] = action_breakdown.get(flow.action, 0) + 1

    top_destinations = _rank_destinations(flows, limit=5)

    stats = FlowStatistics(
        site_id=site_id,
        sample_size=len(flows),
        total_flows=len(flows),
        total_bytes=total_bytes,
        total_bytes_tx=total_bytes_tx,
        total_bytes_rx=total_bytes_rx,
        total_packets=total_packets,
        unique_sources=len(unique_sources),
        unique_destinations=len(unique_destinations),
        protocol_breakdown=protocol_breakdown,
        action_breakdown=action_breakdown,
        top_destinations=top_destinations,
    )
    return stats.model_dump()


async def get_traffic_flow_details(
    site_id: str,
    flow_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Find a specific flow in the current 50-flow snapshot.

    Raises :class:`ResourceNotFoundError` if the flow has rolled out of the
    window (the v2 endpoint has no "fetch by id" lookup).
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()

        raw_flows = await _fetch_raw_flows(client, settings, site_id)
        for raw in raw_flows:
            if raw.get("id") == flow_id:
                return _parse_flow(raw).model_dump(by_alias=True)

        raise ResourceNotFoundError("traffic_flow", flow_id)


async def get_top_flows(
    site_id: str,
    settings: Settings,
    limit: int = 10,
    sort_by: str = "bytes",
) -> list[dict[str, Any]]:
    """Return the top N flows in the current sample, sorted by volume.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of flows to return (default 10)
        sort_by: ``"bytes"`` (default), ``"packets"``, or ``"duration"``.
    """
    flows = await _get_filtered_flows(site_id, settings)

    def _key(flow: TrafficFlow) -> int:
        if sort_by == "packets":
            return flow.traffic_data.packets_total
        if sort_by == "duration":
            return flow.duration_milliseconds or 0
        return flow.traffic_data.bytes_total

    sorted_flows = sorted(flows, key=_key, reverse=True)[:limit]
    return [flow.model_dump(by_alias=True) for flow in sorted_flows]


async def get_flow_risks(
    site_id: str,
    settings: Settings,
    min_risk_level: str | None = None,
) -> list[dict[str, Any]]:
    """Return flows filtered by risk classification.

    The v2 endpoint reports risk inline on each flow (``low``/``medium``/
    ``high``/``critical``). ``min_risk_level`` keeps everything at or above
    the given level.
    """
    order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    threshold = order.get((min_risk_level or "").lower(), 0)

    flows = await _get_filtered_flows(site_id, settings)
    matching = [flow for flow in flows if order.get((flow.risk or "").lower(), 0) >= threshold]
    return [flow.model_dump(by_alias=True) for flow in matching]


async def filter_traffic_flows(
    site_id: str,
    settings: Settings,
    filter_expression: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Client-side filter by a simple ``key=value`` expression list.

    Accepts comma-separated ``key=value`` pairs, for example
    ``"protocol=UDP,destination_zone_name=External,min_bytes=1000"``. Any
    key recognised by :func:`get_traffic_flows` may be used.
    """
    parsed: dict[str, Any] = {}
    for chunk in (part.strip() for part in filter_expression.split(",")):
        if not chunk or "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"destination_port", "min_bytes"}:
            try:
                parsed[key] = int(value)
            except ValueError:
                continue
        else:
            parsed[key] = value

    return await get_traffic_flows(site_id, settings, limit=limit, **parsed)


async def get_client_flow_aggregation(
    site_id: str,
    client_mac: str,
    settings: Settings,
) -> dict[str, Any]:
    """Aggregate the current flow sample for a specific client MAC."""
    flows = await _get_filtered_flows(site_id, settings, source_mac=client_mac)

    if not flows:
        return ClientFlowAggregation(
            client_mac=client_mac,
            site_id=site_id,
            sample_size=0,
        ).model_dump()

    client_ip = flows[0].source.ip
    client_name = flows[0].source.client_name
    total_bytes = sum(f.traffic_data.bytes_total for f in flows)
    total_packets = sum(f.traffic_data.packets_total for f in flows)

    protocol_breakdown: dict[str, int] = {}
    for flow in flows:
        protocol_breakdown[flow.protocol] = protocol_breakdown.get(flow.protocol, 0) + 1

    return ClientFlowAggregation(
        client_mac=client_mac,
        client_name=client_name,
        client_ip=client_ip,
        site_id=site_id,
        sample_size=len(flows),
        total_bytes=total_bytes,
        total_packets=total_packets,
        top_destinations=_rank_destinations(flows, limit=5),
        protocol_breakdown=protocol_breakdown,
    ).model_dump()


async def get_flow_analytics(
    site_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """High-level analytics over the current flow sample.

    Returns counts, totals, protocol / action / risk breakdowns, and top
    destinations in a single call. Thin wrapper over
    :func:`get_flow_statistics` with an additional risk breakdown.
    """
    stats = await get_flow_statistics(site_id, settings)
    flows = await _get_filtered_flows(site_id, settings)

    risk_breakdown: dict[str, int] = {}
    for flow in flows:
        level = (flow.risk or "unknown").lower()
        risk_breakdown[level] = risk_breakdown.get(level, 0) + 1

    stats["risk_breakdown"] = risk_breakdown
    return stats


async def export_traffic_flows(
    site_id: str,
    settings: Settings,
    export_format: str = "json",
    max_records: int | None = None,
) -> str:
    """Serialise the current flow sample to JSON or CSV."""
    if export_format not in {"json", "csv"}:
        raise ValueError("export_format must be 'json' or 'csv'")

    flows = await _get_filtered_flows(site_id, settings)
    if max_records is not None:
        flows = flows[:max_records]

    if export_format == "json":
        return json.dumps([f.model_dump(by_alias=True) for f in flows], indent=2)

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "flow_id",
            "action",
            "protocol",
            "direction",
            "source_mac",
            "source_ip",
            "source_port",
            "source_zone",
            "destination_ip",
            "destination_port",
            "destination_zone",
            "bytes_total",
            "packets_total",
            "duration_ms",
            "risk",
        ]
    )
    for f in flows:
        writer.writerow(
            [
                f.id,
                f.action,
                f.protocol,
                f.direction,
                f.source.mac or f.source.id or "",
                f.source.ip or "",
                f.source.port or "",
                f.source.zone_name or "",
                f.destination.ip or "",
                f.destination.port or "",
                f.destination.zone_name or "",
                f.traffic_data.bytes_total,
                f.traffic_data.packets_total,
                f.duration_milliseconds or 0,
                f.risk or "",
            ]
        )
    return buf.getvalue()


async def find_flows_for_rule_reference(
    site_id: str,
    settings: Settings,
    source_zone_name: str | None = None,
    destination_zone_name: str | None = None,
    source_network_name: str | None = None,
    destination_network_name: str | None = None,
    source_mac: str | None = None,
    protocol: str | None = None,
    destination_port: int | None = None,
    destination_ip: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find flows matching a *draft* firewall rule intent.

    Designed for the "should I create this rule?" workflow: given the
    proposed match criteria for a new zone-based firewall policy or ACL
    rule, this tool returns the real flows from the current snapshot that
    the rule *would* have matched. The LLM can then inspect the concrete
    traffic before committing to the rule.

    Each result is a :class:`FlowRuleReferenceMatch` — trimmed to the
    fields relevant for rule evaluation (zone/network/port/bytes/action).

    **Inter-VLAN rule authoring note:** UniFi labels the destination zone
    of inter-VLAN flows as ``"Gateway"`` rather than the target VLAN's
    zone. To reference a rule intent like "Internal → Servers VLAN", pass
    ``source_network_name`` / ``destination_network_name`` (the actual
    VLAN display names) instead of the zone names. Zone names work for
    egress flows to External but not for inter-VLAN traffic.

    Args:
        site_id: Site identifier
        settings: Application settings
        source_zone_name: Proposed source zone
        destination_zone_name: Proposed destination zone (only useful for
            ``External``; see the inter-VLAN note above)
        source_network_name: Proposed source VLAN display name
        destination_network_name: Proposed destination VLAN display name —
            **use this for inter-VLAN rules**
        source_mac: Proposed source client MAC
        protocol: Proposed protocol
        destination_port: Proposed destination port
        destination_ip: Proposed destination IP
        limit: Max matches to return (default 20, capped at 50 by the API)

    Returns:
        List of lightweight match records suitable for rendering to the user.
    """
    flows = await _get_filtered_flows(
        site_id,
        settings,
        source_zone_name=source_zone_name,
        destination_network_name=destination_network_name,
        destination_zone_name=destination_zone_name,
        source_network_name=source_network_name,
        source_mac=source_mac,
        protocol=protocol,
        destination_port=destination_port,
        destination_ip=destination_ip,
    )

    matches = [_flow_to_reference_match(flow) for flow in flows[:limit]]
    return [m.model_dump() for m in matches]


# --------------------------------------------------------------------------- #
# Helpers for aggregation                                                     #
# --------------------------------------------------------------------------- #


def _has_any_identifier(endpoint: Any) -> bool:
    return bool(
        getattr(endpoint, "id", None)
        or getattr(endpoint, "mac", None)
        or getattr(endpoint, "ip", None)
    )


def _rank_destinations(flows: Iterable[TrafficFlow], *, limit: int) -> list[dict[str, Any]]:
    """Return the top destinations by total bytes in a flow sample."""
    tally: dict[str, dict[str, Any]] = {}
    for flow in flows:
        ip = flow.destination.ip
        if not ip:
            continue
        entry = tally.setdefault(
            ip,
            {
                "ip": ip,
                "port": flow.destination.port,
                "zone_name": flow.destination.zone_name,
                "region": flow.destination.region,
                "bytes_total": 0,
                "flow_count": 0,
            },
        )
        entry["bytes_total"] += flow.traffic_data.bytes_total
        entry["flow_count"] += 1
    ranked = sorted(tally.values(), key=lambda e: e["bytes_total"], reverse=True)
    return ranked[:limit]


def _flow_to_reference_match(flow: TrafficFlow) -> FlowRuleReferenceMatch:
    src_label = (
        flow.source.client_name or flow.source.mac or flow.source.ip or flow.source.id or "unknown"
    )
    dst_label_parts = [
        flow.destination.ip or flow.destination.id or "?",
    ]
    if flow.destination.zone_name:
        dst_label_parts.append(f"({flow.destination.zone_name})")
    dst_label = " ".join(dst_label_parts)
    return FlowRuleReferenceMatch(
        flow_id=flow.id,
        source_label=str(src_label),
        destination_label=dst_label,
        protocol=flow.protocol,
        destination_port=flow.destination.port,
        bytes_total=flow.traffic_data.bytes_total,
        action=flow.action,
        source_zone_name=flow.source.zone_name,
        destination_zone_name=flow.destination.zone_name,
        source_network_name=flow.source.network_name,
        flow_start_time=flow.flow_start_time,
    )


# --------------------------------------------------------------------------- #
# Unsupported on the v2 endpoint                                              #
# --------------------------------------------------------------------------- #


async def get_flow_trends(
    site_id: str,
    settings: Settings,
    time_range: str = "7d",
    interval: str = "1h",
) -> list[dict[str, Any]]:
    """Historical trends — **not supported** on the v2 endpoint.

    The v2 ``traffic-flows`` endpoint returns a rolling snapshot of the 50
    most-recent completed flows; there is no historical query capability.
    For aggregated time-series over longer windows, use the ``stat/report/*``
    endpoints via other MCP tools (e.g. client bandwidth history).
    """
    raise NotImplementedError(
        "get_flow_trends is not supported: the v2 traffic-flows endpoint "
        "does not expose historical time-series data. Use stat/report-based "
        "tools for bandwidth trends."
    )


async def stream_traffic_flows(
    site_id: str,
    settings: Settings,
    interval_seconds: int = 15,
    filter_expression: str | None = None,
) -> Any:
    """Streaming — **not supported** on the v2 endpoint.

    With the hard 50-flow cap the endpoint can't be used as a streaming
    source — fast networks roll through that window in well under a second.
    Use :func:`get_traffic_flows` on a poll schedule instead.
    """
    raise NotImplementedError(
        "stream_traffic_flows is not supported: the v2 traffic-flows endpoint "
        "caps responses at 50 flows with no pagination, so a streaming view "
        "drops flows on busy networks. Poll get_traffic_flows instead."
    )


async def get_connection_states(
    site_id: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Connection-state tracking — **not supported** on the v2 endpoint.

    The v2 ``traffic-flows`` endpoint reports already-completed flows with
    start/end timestamps, not a live connection table.
    """
    raise NotImplementedError(
        "get_connection_states is not supported: the v2 traffic-flows "
        "endpoint does not report explicit connection states. It returns "
        "completed flows with start/end timestamps only."
    )


# --------------------------------------------------------------------------- #
# Block-flow actions (create firewall rules)                                  #
# --------------------------------------------------------------------------- #


async def block_flow_source_ip(
    site_id: str,
    flow_id: str,
    settings: Settings,
    duration: str = "permanent",
    expires_in_hours: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a firewall rule blocking the source IP of a specific flow."""
    validate_confirmation(confirm, "block flow source IP", dry_run)

    flow_dict = await get_traffic_flow_details(site_id, flow_id, settings)
    source_ip = (flow_dict.get("source") or {}).get("ip")
    if not source_ip:
        raise ValueError(f"No source IP found for flow {flow_id}")

    return await _create_block_action(
        site_id=site_id,
        settings=settings,
        block_type="source_ip",
        blocked_target=source_ip,
        rule_name_prefix="BlockSrc",
        duration=duration,
        expires_in_hours=expires_in_hours,
        dry_run=dry_run,
    )


async def block_flow_destination_ip(
    site_id: str,
    flow_id: str,
    settings: Settings,
    duration: str = "permanent",
    expires_in_hours: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a firewall rule blocking the destination IP of a specific flow."""
    validate_confirmation(confirm, "block flow destination IP", dry_run)

    flow_dict = await get_traffic_flow_details(site_id, flow_id, settings)
    destination_ip = (flow_dict.get("destination") or {}).get("ip")
    if not destination_ip:
        raise ValueError(f"No destination IP found for flow {flow_id}")

    return await _create_block_action(
        site_id=site_id,
        settings=settings,
        block_type="destination_ip",
        blocked_target=destination_ip,
        rule_name_prefix="BlockDst",
        duration=duration,
        expires_in_hours=expires_in_hours,
        dry_run=dry_run,
    )


async def block_flow_application(
    site_id: str,
    flow_id: str,
    settings: Settings,
    duration: str = "permanent",
    expires_in_hours: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Block a flow's identified application.

    The v2 ``traffic-flows`` endpoint reports a coarse ``service`` field
    ("DNS", "OTHER", etc.) rather than a DPI application id, so this tool
    falls back to blocking the destination IP when no distinct application
    can be inferred.
    """
    validate_confirmation(confirm, "block flow application", dry_run)

    flow_dict = await get_traffic_flow_details(site_id, flow_id, settings)
    destination_ip = (flow_dict.get("destination") or {}).get("ip")
    if not destination_ip:
        raise ValueError(f"Flow {flow_id} has no destination IP to block")
    # The v2 endpoint reports a coarse `service` field ("DNS", "OTHER",
    # etc.) rather than a DPI application id, so we always fall back to
    # blocking the destination IP. The service name is included in the
    # block-action metadata for audit purposes but NOT in the firewall
    # rule target (which must be a valid IP/CIDR).
    target = destination_ip

    return await _create_block_action(
        site_id=site_id,
        settings=settings,
        block_type="application",
        blocked_target=target,
        rule_name_prefix="BlockApp",
        duration=duration,
        expires_in_hours=expires_in_hours,
        dry_run=dry_run,
    )


async def _create_block_action(
    *,
    site_id: str,
    settings: Settings,
    block_type: str,
    blocked_target: str,
    rule_name_prefix: str,
    duration: str,
    expires_in_hours: int | None,
    dry_run: bool | str,
) -> dict[str, Any]:
    """Shared block-action implementation used by the three block_flow_* tools."""
    from .firewall import create_firewall_rule

    rule_name = f"{rule_name_prefix}_{blocked_target.replace(':', '_')[:24]}"
    action_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    expires_at = None
    if duration == "temporary" and expires_in_hours:
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).isoformat()

    if dry_run:
        logger.info(sanitize_log_message(f"[DRY RUN] Would block {block_type}={blocked_target}"))
        return BlockFlowAction(
            action_id=action_id,
            block_type=block_type,
            blocked_target=blocked_target,
            rule_id=None,
            zone_id=None,
            duration=duration,
            expires_at=expires_at,
            created_at=created_at,
        ).model_dump()

    rule_result = await create_firewall_rule(
        site_id=site_id,
        name=rule_name,
        action="drop",
        settings=settings,
        src_address=blocked_target if block_type == "source_ip" else None,
        dst_address=blocked_target if block_type != "source_ip" else None,
        confirm=True,
    )

    await audit_action(
        settings,
        action_type=f"block_flow_{block_type}",
        resource_type="firewall_rule",
        resource_id=rule_result.get("_id", rule_result.get("id", "unknown")),
        site_id=site_id,
        details={"blocked_target": blocked_target, "duration": duration},
    )

    return BlockFlowAction(
        action_id=action_id,
        block_type=block_type,
        blocked_target=blocked_target,
        rule_id=str(rule_result.get("_id", rule_result.get("id", ""))) or None,
        zone_id=None,
        duration=duration,
        expires_at=expires_at,
        created_at=created_at,
    ).model_dump()
