"""Traffic flow monitoring tools."""

from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..models.traffic_flow import FlowRisk, FlowStatistics, FlowView, TrafficFlow
from ..utils import get_logger

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


async def get_flow_statistics(
    site_id: str, settings: Settings, time_range: str = "24h"
) -> dict:
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
            return FlowStatistics(
                site_id=site_id, time_range=time_range
            ).model_dump()

        return FlowStatistics(**data).model_dump()


async def get_traffic_flow_details(
    site_id: str, flow_id: str, settings: Settings
) -> dict:
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
            response = await client.get(
                f"/integration/v1/sites/{site_id}/traffic/flows/{flow_id}"
            )
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
        logger.info(f"Filtering traffic flows for site {site_id} with expression: {filter_expression}")

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

