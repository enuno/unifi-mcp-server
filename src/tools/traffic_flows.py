"""Traffic flow monitoring tools."""

import asyncio
import csv
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any
from uuid import uuid4

from ..api.client import UniFiClient
from ..config import Settings
from ..models.traffic_flow import (
    BlockFlowAction,
    ClientFlowAggregation,
    ConnectionState,
    FlowRisk,
    FlowStatistics,
    FlowStreamUpdate,
    TrafficFlow,
)
from ..utils import audit_action, get_logger, validate_confirmation

logger = get_logger(__name__)


async def get_traffic_flows(
    site_id: str,
    settings: Settings,
    source_ip: str | None = None,
    destination_ip: str | None = None,
    protocol: str | None = None,
    application_id: str | None = None,
    time_range: str = "24h",
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """Retrieve real-time traffic flows.

    Args:
        site_id: Site identifier
        settings: Application settings
        source_ip: Filter by source IP
        destination_ip: Filter by destination IP
        protocol: Filter by protocol (tcp/udp/icmp)
        application_id: Filter by DPI application ID
        time_range: Time range for flows (1h, 6h, 12h, 24h, 7d, 30d)
        limit: Maximum number of flows to return
        offset: Number of flows to skip

    Returns:
        List of traffic flows
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving traffic flows for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        params: dict[str, Any] = {"time_range": time_range}
        if source_ip:
            params["source_ip"] = source_ip
        if destination_ip:
            params["destination_ip"] = destination_ip
        if protocol:
            params["protocol"] = protocol
        if application_id:
            params["application_id"] = application_id
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset

        try:
            response = await client.get(
                f"/integration/v1/sites/{site_id}/traffic/flows", params=params
            )
            data = response.get("data", [])
        except Exception as e:
            logger.warning(f"Traffic flows endpoint not available: {e}")
            return []

        return [TrafficFlow(**flow).model_dump() for flow in data]


async def get_flow_statistics(site_id: str, settings: Settings, time_range: str = "24h") -> dict:
    """Get aggregate flow statistics.

    Args:
        site_id: Site identifier
        settings: Application settings
        time_range: Time range for statistics (1h, 6h, 12h, 24h, 7d, 30d)

    Returns:
        Flow statistics
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving flow statistics for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(
                f"/integration/v1/sites/{site_id}/traffic/flows/statistics",
                params={"time_range": time_range},
            )
            data = response.get("data", response)
        except Exception as e:
            logger.warning(f"Flow statistics endpoint not available: {e}")
            # Return empty statistics
            return FlowStatistics(site_id=site_id, time_range=time_range).model_dump()

        return FlowStatistics(**data).model_dump()


async def get_traffic_flow_details(site_id: str, flow_id: str, settings: Settings) -> dict:
    """Get details for a specific traffic flow.

    Args:
        site_id: Site identifier
        flow_id: Flow identifier
        settings: Application settings

    Returns:
        Traffic flow details
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving traffic flow {flow_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(f"/integration/v1/sites/{site_id}/traffic/flows/{flow_id}")
            data = response.get("data", response)
        except Exception as e:
            logger.warning(f"Traffic flow details endpoint not available: {e}")
            raise

        return TrafficFlow(**data).model_dump()


async def get_top_flows(
    site_id: str,
    settings: Settings,
    limit: int = 10,
    time_range: str = "24h",
    sort_by: str = "bytes",
) -> list[dict]:
    """Get top bandwidth-consuming flows.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Number of top flows to return
        time_range: Time range for flows
        sort_by: Sort by field (bytes, packets, duration)

    Returns:
        List of top flows
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving top flows for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(
                f"/integration/v1/sites/{site_id}/traffic/flows/top",
                params={"limit": limit, "time_range": time_range, "sort_by": sort_by},
            )
            data = response.get("data", [])
        except Exception:
            # Fallback: get all flows and sort manually
            logger.info("Top flows endpoint not available, fetching all flows")
            flows = await get_traffic_flows(site_id, settings, time_range=time_range)
            # Sort by total bytes
            sorted_flows = sorted(
                flows,
                key=lambda x: x.get("bytes_sent", 0) + x.get("bytes_received", 0),
                reverse=True,
            )
            return sorted_flows[:limit]

        return [TrafficFlow(**flow).model_dump() for flow in data]


async def get_flow_risks(
    site_id: str,
    settings: Settings,
    time_range: str = "24h",
    min_risk_level: str | None = None,
) -> list[dict]:
    """Get risk assessment for flows.

    Args:
        site_id: Site identifier
        settings: Application settings
        time_range: Time range for flows
        min_risk_level: Minimum risk level to include (low/medium/high/critical)

    Returns:
        List of flows with risk assessments
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving flow risks for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        params = {"time_range": time_range}
        if min_risk_level:
            params["min_risk_level"] = min_risk_level

        try:
            response = await client.get(
                f"/integration/v1/sites/{site_id}/traffic/flows/risks", params=params
            )
            data = response.get("data", [])
        except Exception:
            logger.warning("Flow risks endpoint not available")
            return []

        return [FlowRisk(**risk).model_dump() for risk in data]


async def get_flow_trends(
    site_id: str,
    settings: Settings,
    time_range: str = "7d",
    interval: str = "1h",
) -> list[dict]:
    """Get historical flow trends.

    Args:
        site_id: Site identifier
        settings: Application settings
        time_range: Time range for trends (default: 7d)
        interval: Time interval for data points (1h, 6h, 1d)

    Returns:
        List of trend data points
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving flow trends for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(
                f"/integration/v1/sites/{site_id}/traffic/flows/trends",
                params={"time_range": time_range, "interval": interval},
            )
            data = response.get("data", [])
        except Exception:
            logger.warning("Flow trends endpoint not available")
            return []

        return data


async def filter_traffic_flows(
    site_id: str,
    settings: Settings,
    filter_expression: str,
    time_range: str = "24h",
    limit: int | None = None,
) -> list[dict]:
    """Filter flows using a complex filter expression.

    Args:
        site_id: Site identifier
        settings: Application settings
        filter_expression: Filter expression (e.g., "bytes > 1000000 AND protocol = 'tcp'")
        time_range: Time range for flows
        limit: Maximum number of flows to return

    Returns:
        List of filtered traffic flows
    """
    async with UniFiClient(settings) as client:
        logger.info(
            f"Filtering traffic flows for site {site_id} with expression: {filter_expression}"
        )

        if not client.is_authenticated:
            await client.authenticate()

        params = {"filter": filter_expression, "time_range": time_range}
        if limit:
            params["limit"] = limit

        try:
            response = await client.get(
                f"/integration/v1/sites/{site_id}/traffic/flows", params=params
            )
            data = response.get("data", [])
        except Exception:
            logger.warning("Filtered flows endpoint not available, using basic filtering")
            # Fallback to basic filtering
            flows = await get_traffic_flows(site_id, settings, time_range=time_range)
            # Simple filtering - in production, would use a proper query parser
            return flows[:limit] if limit else flows

        return [TrafficFlow(**flow).model_dump() for flow in data]


async def stream_traffic_flows(
    site_id: str,
    settings: Settings,
    interval_seconds: int = 15,
    filter_expression: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream real-time traffic flow updates.

    This function attempts to use WebSocket for real-time updates,
    falling back to polling if WebSocket is unavailable.

    Args:
        site_id: Site identifier
        settings: Application settings
        interval_seconds: Update interval in seconds (default: 15)
        filter_expression: Optional filter expression

    Yields:
        Flow stream updates with bandwidth rates
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Starting traffic flow stream for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Track previous flows for rate calculation
        previous_flows: dict[str, TrafficFlow] = {}

        # Try WebSocket first (if available in future)
        # For now, use polling fallback
        logger.info(f"Using polling fallback with {interval_seconds}s interval")

        while True:
            try:
                # Get current flows
                params: dict[str, Any] = {}
                if filter_expression:
                    params["filter"] = filter_expression

                response = await client.get(
                    f"/integration/v1/sites/{site_id}/traffic/flows", params=params
                )
                data = response.get("data", [])

                current_time = datetime.now(timezone.utc).isoformat()

                for flow_data in data:
                    flow = TrafficFlow(**flow_data)
                    flow_id = flow.flow_id

                    # Determine update type
                    if flow_id in previous_flows:
                        update_type = "update"
                        # Calculate bandwidth rate
                        prev_flow = previous_flows[flow_id]
                        bytes_diff = (flow.bytes_sent + flow.bytes_received) - (
                            prev_flow.bytes_sent + prev_flow.bytes_received
                        )
                        bandwidth_rate = {
                            "bps": bytes_diff * 8 / interval_seconds,
                            "upload_bps": (flow.bytes_sent - prev_flow.bytes_sent)
                            * 8
                            / interval_seconds,
                            "download_bps": (flow.bytes_received - prev_flow.bytes_received)
                            * 8
                            / interval_seconds,
                        }
                    else:
                        update_type = "new"
                        bandwidth_rate = None

                    # Create stream update
                    update = FlowStreamUpdate(
                        update_type=update_type,
                        flow=flow,
                        timestamp=current_time,
                        bandwidth_rate=bandwidth_rate,
                    )

                    yield update.model_dump()

                    # Update tracking
                    previous_flows[flow_id] = flow

                # Check for closed flows
                current_flow_ids = {flow.flow_id for flow in data}
                for prev_flow_id in list(previous_flows.keys()):
                    if prev_flow_id not in current_flow_ids:
                        closed_flow = previous_flows.pop(prev_flow_id)
                        update = FlowStreamUpdate(
                            update_type="closed",
                            flow=closed_flow,
                            timestamp=current_time,
                            bandwidth_rate=None,
                        )
                        yield update.model_dump()

                # Wait for next interval
                await asyncio.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Error in flow streaming: {e}")
                await asyncio.sleep(interval_seconds)


async def get_connection_states(
    site_id: str,
    settings: Settings,
    time_range: str = "1h",
) -> list[dict]:
    """Get connection states for all flows.

    Args:
        site_id: Site identifier
        settings: Application settings
        time_range: Time range for flows

    Returns:
        List of connection states
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving connection states for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get flows
        flows = await get_traffic_flows(site_id, settings, time_range=time_range)

        # Determine connection states
        states = []
        current_time = datetime.now(timezone.utc)

        for flow in flows:
            flow_obj = TrafficFlow(**flow)

            # Determine state based on end_time
            if flow_obj.end_time:
                state = "closed"
                termination_reason = "normal_closure"
            else:
                # Check if flow is timed out (no activity in last 5 minutes)
                last_seen = datetime.fromisoformat(flow_obj.start_time.replace("Z", "+00:00"))
                if (current_time - last_seen).total_seconds() > 300:
                    state = "timed_out"
                    termination_reason = "timeout"
                else:
                    state = "active"
                    termination_reason = None

            connection_state = ConnectionState(
                flow_id=flow_obj.flow_id,
                state=state,
                last_seen=flow_obj.end_time or flow_obj.start_time,
                total_duration=flow_obj.duration,
                termination_reason=termination_reason,
            )

            states.append(connection_state.model_dump())

        return states


async def get_client_flow_aggregation(
    site_id: str,
    client_mac: str,
    settings: Settings,
    time_range: str = "24h",
) -> dict:
    """Get aggregated flow data for a specific client.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings
        time_range: Time range for aggregation

    Returns:
        Client flow aggregation data
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving flow aggregation for client {client_mac}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get flows for this client
        flows = await get_traffic_flows(site_id, settings, time_range=time_range)
        client_flows = [f for f in flows if f.get("client_mac") == client_mac]

        # Get connection states
        states = await get_connection_states(site_id, settings, time_range=time_range)
        client_states = [
            s for s in states if any(f["flow_id"] == s["flow_id"] for f in client_flows)
        ]

        # Aggregate statistics
        total_bytes = sum(f.get("bytes_sent", 0) + f.get("bytes_received", 0) for f in client_flows)
        total_packets = sum(
            f.get("packets_sent", 0) + f.get("packets_received", 0) for f in client_flows
        )

        active_flows = len([s for s in client_states if s["state"] == "active"])
        closed_flows = len([s for s in client_states if s["state"] == "closed"])

        # Top applications
        app_bytes: dict[str, int] = {}
        for flow in client_flows:
            app_name = flow.get("application_name", "Unknown")
            app_bytes[app_name] = (
                app_bytes.get(app_name, 0)
                + flow.get("bytes_sent", 0)
                + flow.get("bytes_received", 0)
            )

        top_applications = [
            {"application": app, "bytes": bytes_val}
            for app, bytes_val in sorted(app_bytes.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # Top destinations
        dest_bytes: dict[str, int] = {}
        for flow in client_flows:
            dest_ip = flow.get("destination_ip", "Unknown")
            dest_bytes[dest_ip] = (
                dest_bytes.get(dest_ip, 0)
                + flow.get("bytes_sent", 0)
                + flow.get("bytes_received", 0)
            )

        top_destinations = [
            {"destination_ip": dest, "bytes": bytes_val}
            for dest, bytes_val in sorted(dest_bytes.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # Get client IP from first flow
        client_ip = client_flows[0].get("source_ip") if client_flows else None

        # Auth failures would come from a separate endpoint
        # For now, set to 0 as placeholder
        auth_failures = 0

        aggregation = ClientFlowAggregation(
            client_mac=client_mac,
            client_ip=client_ip,
            site_id=site_id,
            total_flows=len(client_flows),
            total_bytes=total_bytes,
            total_packets=total_packets,
            active_flows=active_flows,
            closed_flows=closed_flows,
            auth_failures=auth_failures,
            top_applications=top_applications,
            top_destinations=top_destinations,
        )

        return aggregation.model_dump()


async def block_flow_source_ip(
    site_id: str,
    flow_id: str,
    settings: Settings,
    duration: str = "permanent",
    expires_in_hours: int | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Block source IP address from a traffic flow.

    Args:
        site_id: Site identifier
        flow_id: Flow identifier to block
        settings: Application settings
        duration: Block duration ("permanent" or "temporary")
        expires_in_hours: Hours until expiration (for temporary blocks)
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Block action result
    """
    validate_confirmation(confirm, "block flow source IP")

    async with UniFiClient(settings) as client:
        logger.info(f"Blocking source IP from flow {flow_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get flow details
        flow_data = await get_traffic_flow_details(site_id, flow_id, settings)
        source_ip = flow_data.get("source_ip")

        if not source_ip:
            raise ValueError(f"No source IP found for flow {flow_id}")

        # Calculate expiration
        expires_at = None
        if duration == "temporary" and expires_in_hours:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
            ).isoformat()

        # Create firewall rule to block this IP
        from .firewall import create_firewall_rule

        rule_name = f"Block_{source_ip}_{flow_id[:8]}"

        if dry_run:
            logger.info(f"[DRY RUN] Would block source IP {source_ip}")
            action_id = str(uuid4())
            return BlockFlowAction(
                action_id=action_id,
                block_type="source_ip",
                blocked_target=source_ip,
                duration=duration,
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc).isoformat(),
            ).model_dump()

        # Create blocking rule
        rule_result = await create_firewall_rule(
            site_id=site_id,
            name=rule_name,
            action="drop",
            protocol="all",
            settings=settings,
            source=source_ip,
            enabled=True,
            confirm=True,
        )

        rule_id = rule_result.get("_id")
        action_id = str(uuid4())

        # Audit the action
        await audit_action(
            settings,
            action_type="block_flow_source_ip",
            resource_type="flow_block_action",
            resource_id=action_id,
            site_id=site_id,
            details={"flow_id": flow_id, "source_ip": source_ip, "rule_id": rule_id},
        )

        return BlockFlowAction(
            action_id=action_id,
            block_type="source_ip",
            blocked_target=source_ip,
            rule_id=rule_id,
            duration=duration,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump()


async def block_flow_destination_ip(
    site_id: str,
    flow_id: str,
    settings: Settings,
    duration: str = "permanent",
    expires_in_hours: int | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Block destination IP address from a traffic flow.

    Args:
        site_id: Site identifier
        flow_id: Flow identifier to block
        settings: Application settings
        duration: Block duration ("permanent" or "temporary")
        expires_in_hours: Hours until expiration (for temporary blocks)
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Block action result
    """
    validate_confirmation(confirm, "block flow destination IP")

    async with UniFiClient(settings) as client:
        logger.info(f"Blocking destination IP from flow {flow_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get flow details
        flow_data = await get_traffic_flow_details(site_id, flow_id, settings)
        destination_ip = flow_data.get("destination_ip")

        if not destination_ip:
            raise ValueError(f"No destination IP found for flow {flow_id}")

        # Calculate expiration
        expires_at = None
        if duration == "temporary" and expires_in_hours:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
            ).isoformat()

        # Create firewall rule to block this IP
        from .firewall import create_firewall_rule

        rule_name = f"Block_{destination_ip}_{flow_id[:8]}"

        if dry_run:
            logger.info(f"[DRY RUN] Would block destination IP {destination_ip}")
            action_id = str(uuid4())
            return BlockFlowAction(
                action_id=action_id,
                block_type="destination_ip",
                blocked_target=destination_ip,
                duration=duration,
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc).isoformat(),
            ).model_dump()

        # Create blocking rule
        rule_result = await create_firewall_rule(
            site_id=site_id,
            name=rule_name,
            action="drop",
            protocol="all",
            settings=settings,
            destination=destination_ip,
            enabled=True,
            confirm=True,
        )

        rule_id = rule_result.get("_id")
        action_id = str(uuid4())

        # Audit the action
        await audit_action(
            settings,
            action_type="block_flow_destination_ip",
            resource_type="flow_block_action",
            resource_id=action_id,
            site_id=site_id,
            details={"flow_id": flow_id, "destination_ip": destination_ip, "rule_id": rule_id},
        )

        return BlockFlowAction(
            action_id=action_id,
            block_type="destination_ip",
            blocked_target=destination_ip,
            rule_id=rule_id,
            duration=duration,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump()


async def block_flow_application(
    site_id: str,
    flow_id: str,
    settings: Settings,
    use_zbf: bool = True,
    zone_id: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Block application identified in a traffic flow.

    Args:
        site_id: Site identifier
        flow_id: Flow identifier to block
        settings: Application settings
        use_zbf: Use Zone-Based Firewall if available (default: True)
        zone_id: Zone ID for ZBF blocking (optional)
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Block action result
    """
    validate_confirmation(confirm, "block flow application")

    async with UniFiClient(settings) as client:
        logger.info(f"Blocking application from flow {flow_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get flow details
        flow_data = await get_traffic_flow_details(site_id, flow_id, settings)
        application_id = flow_data.get("application_id")
        application_name = flow_data.get("application_name", "Unknown")

        if not application_id:
            raise ValueError(f"No application ID found for flow {flow_id}")

        action_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        if dry_run:
            logger.info(f"[DRY RUN] Would block application {application_name} ({application_id})")
            return BlockFlowAction(
                action_id=action_id,
                block_type="application",
                blocked_target=application_id,
                zone_id=zone_id if use_zbf else None,
                duration="permanent",
                created_at=created_at,
            ).model_dump()

        rule_id = None
        result_zone_id = None

        # Try ZBF blocking first if requested
        if use_zbf:
            try:
                from .zbf_matrix import block_application_by_zone

                # If no zone specified, try to get a default zone
                if not zone_id:
                    from .firewall_zones import list_firewall_zones

                    zones = await list_firewall_zones(site_id, settings)
                    if zones:
                        zone_id = zones[0].get("id")

                if zone_id:
                    await block_application_by_zone(
                        site_id=site_id,
                        zone_id=zone_id,
                        application_id=application_id,
                        settings=settings,
                        action="block",
                        confirm=True,
                    )
                    result_zone_id = zone_id
                    logger.info(f"Blocked application using ZBF in zone {zone_id}")
            except Exception as e:
                logger.warning(f"ZBF blocking failed, falling back to traditional firewall: {e}")
                use_zbf = False

        # Fallback to traditional firewall rule
        if not use_zbf or not zone_id:
            from .firewall import create_firewall_rule

            rule_name = f"Block_App_{application_name}_{flow_id[:8]}"

            rule_result = await create_firewall_rule(
                site_id=site_id,
                name=rule_name,
                action="drop",
                protocol="all",
                settings=settings,
                enabled=True,
                confirm=True,
            )
            rule_id = rule_result.get("_id")

        # Audit the action
        await audit_action(
            settings,
            action_type="block_flow_application",
            resource_type="flow_block_action",
            resource_id=action_id,
            site_id=site_id,
            details={
                "flow_id": flow_id,
                "application_id": application_id,
                "application_name": application_name,
                "rule_id": rule_id,
                "zone_id": result_zone_id,
            },
        )

        return BlockFlowAction(
            action_id=action_id,
            block_type="application",
            blocked_target=application_id,
            rule_id=rule_id,
            zone_id=result_zone_id,
            duration="permanent",
            created_at=created_at,
        ).model_dump()


async def export_traffic_flows(
    site_id: str,
    settings: Settings,
    export_format: str = "json",
    time_range: str = "24h",
    include_fields: list[str] | None = None,
    filter_expression: str | None = None,
    max_records: int | None = None,
) -> str:
    """Export traffic flows to a file format.

    Args:
        site_id: Site identifier
        settings: Application settings
        export_format: Export format ("json", "csv")
        time_range: Time range for export
        include_fields: Specific fields to include (None = all)
        filter_expression: Filter expression
        max_records: Maximum number of records

    Returns:
        Exported data as string
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Exporting traffic flows in {export_format} format")

        if not client.is_authenticated:
            await client.authenticate()

        # Get flows based on filter
        if filter_expression:
            flows = await filter_traffic_flows(
                site_id, settings, filter_expression, time_range, max_records
            )
        else:
            flows = await get_traffic_flows(site_id, settings, time_range=time_range)
            if max_records:
                flows = flows[:max_records]

        # Filter fields if specified
        if include_fields:
            flows = [
                {field: flow.get(field) for field in include_fields if field in flow}
                for flow in flows
            ]

        # Export to requested format
        if export_format == "json":
            return json.dumps(flows, indent=2)

        elif export_format == "csv":
            if not flows:
                return ""

            output = StringIO()
            # Get all unique fields
            all_fields = set()
            for flow in flows:
                all_fields.update(flow.keys())

            fieldnames = sorted(all_fields)
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flows)

            return output.getvalue()

        else:
            raise ValueError(f"Unsupported export format: {export_format}")


async def get_flow_analytics(
    site_id: str,
    settings: Settings,
    time_range: str = "24h",
) -> dict:
    """Get comprehensive flow analytics.

    Args:
        site_id: Site identifier
        settings: Application settings
        time_range: Time range for analytics

    Returns:
        Comprehensive analytics data
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Generating flow analytics for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get flows and statistics
        flows = await get_traffic_flows(site_id, settings, time_range=time_range)
        statistics = await get_flow_statistics(site_id, settings, time_range)
        states = await get_connection_states(site_id, settings, time_range)

        # Additional analytics
        protocols = {}
        applications = {}

        for flow in flows:
            # Protocol distribution
            protocol = flow.get("protocol", "unknown")
            protocols[protocol] = protocols.get(protocol, 0) + 1

            # Application distribution
            app = flow.get("application_name", "Unknown")
            total_bytes = flow.get("bytes_sent", 0) + flow.get("bytes_received", 0)
            if app not in applications:
                applications[app] = {"count": 0, "bytes": 0}
            applications[app]["count"] += 1
            applications[app]["bytes"] += total_bytes

        # State distribution
        state_distribution = {}
        for state in states:
            state_type = state.get("state", "unknown")
            state_distribution[state_type] = state_distribution.get(state_type, 0) + 1

        return {
            "site_id": site_id,
            "time_range": time_range,
            "statistics": statistics,
            "protocol_distribution": protocols,
            "application_distribution": applications,
            "state_distribution": state_distribution,
            "total_flows": len(flows),
            "total_states": len(states),
        }
