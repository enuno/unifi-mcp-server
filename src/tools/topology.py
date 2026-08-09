"""Network topology tools for UniFi MCP Server."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Literal, cast

from src.api.client import UniFiClient
from src.config import Settings
from src.models.topology import NetworkDiagram, TopologyConnection, TopologyNode
from src.utils.exceptions import (
    APIError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
    ValidationError,
)

# The Integration API reports "ONLINE"; older/legacy payloads use "CONNECTED".
_ONLINE_DEVICE_STATES = frozenset({"ONLINE", "CONNECTED"})

# Upper bound on in-flight per-device detail lookups. The enrichment pass issues
# one request per device, so a large site would otherwise queue hundreds of
# requests behind the client's rate limiter at once.
_UPLINK_DETAIL_CONCURRENCY = 8


def _extract_device_detail(response: Any) -> dict[str, Any] | None:
    """Unwrap a per-device detail response into the device object.

    Args:
        response: Raw detail response, either the device itself or wrapped in
            ``data`` as an object or a single-element list

    Returns:
        The device object, or None if the response carries none
    """
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return data[0] if data and isinstance(data[0], dict) else None
        return response
    return None


async def _fetch_legacy_stats(
    client: UniFiClient, site_id: str
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Fetch the legacy stat records that carry port and link-speed detail.

    The integration API's uplink object is only ``{"deviceId": ...}``: it names
    the parent but reports neither the ports a link lands on nor its negotiated
    speed, so a graph built from it alone has edges with no properties. The
    legacy ``stat/device`` and ``stat/sta`` routes do carry that detail
    (``port_idx``, ``uplink_remote_port``, ``speed``, ``sw_port``,
    ``wired_rate_mbps``), so fetch each once and join on MAC.

    Best-effort by design: a controller that refuses these routes yields empty
    maps, degrading to a graph without port detail rather than no graph at all.

    Args:
        client: Authenticated API client
        site_id: Resolved site identifier

    Returns:
        ``(devices_by_mac, clients_by_mac)``, both keyed by lowercased MAC
    """

    async def by_mac(endpoint: str) -> dict[str, dict[str, Any]]:
        try:
            response = await client.get(endpoint)
        except (APIError, NetworkError) as exc:
            client.logger.debug(f"No legacy detail from {endpoint}: {exc}")
            return {}
        rows = response if isinstance(response, list) else response.get("data", [])
        indexed: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            mac = (row.get("mac") or "").lower()
            if mac:
                indexed[mac] = row
        return indexed

    devices, clients = await asyncio.gather(
        by_mac(f"/ea/sites/{site_id}/devices"),
        by_mac(f"/ea/sites/{site_id}/sta"),
    )
    return devices, clients


async def _merge_device_uplinks(
    client: UniFiClient, devices_endpoint: str, devices: list[dict[str, Any]]
) -> None:
    """Populate each device's ``uplink`` from the per-device detail route.

    The device *list* endpoint omits ``uplink`` entirely, so a topology built
    from it alone contains no device-to-device edges. The detail route does
    carry it, as ``{"deviceId": ...}``.

    Lookups run concurrently, bounded by ``_UPLINK_DETAIL_CONCURRENCY``. A
    device whose lookup fails with a per-device API error keeps no uplink rather
    than failing the whole graph, but a systemic failure — an authentication
    rejection or an exhausted rate limit, which every other lookup is hitting
    too — propagates instead of quietly yielding a graph with missing edges.

    Args:
        client: Authenticated API client
        devices_endpoint: Base devices endpoint for the resolved site
        devices: Device dicts to enrich in place

    Raises:
        AuthenticationError: If the controller rejects the credentials
        RateLimitError: If the rate limit is exhausted after retries
    """
    semaphore = asyncio.Semaphore(_UPLINK_DETAIL_CONCURRENCY)

    async def fetch(device: dict[str, Any]) -> None:
        """Fetch one device's detail record and copy its uplink onto ``device``.

        Args:
            device: Device dict to enrich in place; skipped when it already
                carries an ``uplink`` or has no ``id``
        """
        device_id = device.get("id")
        if not device_id or isinstance(device.get("uplink"), dict):
            return
        async with semaphore:
            try:
                response = await client.get(f"{devices_endpoint}/{device_id}")
            except (AuthenticationError, RateLimitError):
                # Systemic, not device-specific: every other lookup is failing
                # the same way, so a degraded graph would misrepresent the site.
                raise
            except (APIError, NetworkError) as exc:
                # One bad device must not sink the graph. Narrow on purpose:
                # anything else is a bug and should fail loudly.
                client.logger.debug(f"No uplink detail for device {device_id}: {exc}")
                return
        detail = _extract_device_detail(response)
        if detail is not None and isinstance(detail.get("uplink"), dict):
            device["uplink"] = detail["uplink"]

    await asyncio.gather(*(fetch(device) for device in devices))


def _resolve_depth(device_id: str, uplinks: dict[str, str], cache: dict[str, int]) -> int:
    """Return a device's hop count from the gateway.

    Walks the uplink chain rather than trusting device ordering, so depth is
    correct regardless of the order the API returns devices in. A cycle in the
    reported uplinks is broken by treating the repeated device as a root.

    Args:
        device_id: Device to resolve
        uplinks: Device ID -> uplink device ID
        cache: Memo of already-resolved depths, updated in place

    Returns:
        Hop count, 0 for a device with no uplink
    """
    chain: list[str] = []
    seen: set[str] = set()
    current = device_id

    while current not in cache:
        if current in seen:
            cache[current] = 0
            break
        seen.add(current)
        parent = uplinks.get(current)
        if parent is None:
            cache[current] = 0
            break
        chain.append(current)
        current = parent

    depth = cache[current]
    for node in reversed(chain):
        # A node already in the cache is the cycle root this walk just pinned to
        # 0. Keep that value and continue counting from it, rather than
        # overwriting the root and inflating everything downstream of it.
        cached = cache.get(node)
        if cached is not None:
            depth = cached
            continue
        depth += 1
        cache[node] = depth
    return cache[device_id]


async def get_network_topology(
    site_id: str,
    settings: Settings,
    include_coordinates: bool = False,
) -> dict:
    """Retrieve complete network topology graph.

    Fetches the network topology including all devices, clients, and their
    interconnections. Optionally includes position coordinates for visualization.

    Args:
        site_id: Site identifier ("default" for default site)
        settings: Application settings with UniFi controller connection info
        include_coordinates: Whether to calculate node position coordinates

    Returns:
        Network diagram dictionary with nodes, connections, and statistics

    Example:
        ```python
        topology = await get_network_topology("default", settings, include_coordinates=True)
        print(f"Total devices: {topology['total_devices']}")
        print(f"Total clients: {topology['total_clients']}")
        ```
    """
    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()

        actual_site_id = await client.resolve_site_id(site_id)

        # Fetch devices and clients from UniFi Integration API
        devices_endpoint = client.settings.get_integration_path(f"sites/{actual_site_id}/devices")
        clients_endpoint = client.settings.get_integration_path(f"sites/{actual_site_id}/clients")

        # Fetch all devices and clients (handle pagination)
        device_nodes = []
        offset = 0
        while True:
            response = await client.get(f"{devices_endpoint}?offset={offset}&limit=100")
            data = response if isinstance(response, list) else response.get("data", [])
            if not data:
                break
            device_nodes.extend(data)
            offset += len(data)
            if len(data) < 100:
                break

        client_nodes = []
        offset = 0
        while True:
            response = await client.get(f"{clients_endpoint}?offset={offset}&limit=100")
            data = response if isinstance(response, list) else response.get("data", [])
            if not data:
                break
            client_nodes.extend(data)
            offset += len(data)
            if len(data) < 100:
                break

        # The list endpoint above returns no `uplink` key; without this the
        # graph would contain client edges only, with every device a root.
        await _merge_device_uplinks(client, devices_endpoint, device_nodes)

        # Ports and link speeds live only on the legacy stat routes.
        legacy_devices, legacy_clients = await _fetch_legacy_stats(client, actual_site_id)

        # Convert devices to topology nodes
        nodes = []
        connections = []
        depth_map: dict[str, int] = {}  # Track network depth for each device

        # Uplink chain must be known up front: depth cannot be derived from a
        # single pass unless parents happen to precede children.
        uplinks: dict[str, str] = {}
        for device in device_nodes:
            device_id = device.get("id", "")
            uplink_device_id = (device.get("uplink") or {}).get("deviceId")
            if device_id and uplink_device_id:
                uplinks[device_id] = uplink_device_id

        # First pass: Create all device nodes and calculate depth
        for device in device_nodes:
            device_id = device.get("id", "")
            uplink_info = device.get("uplink") or {}
            uplink_device_id = uplink_info.get("deviceId")
            is_online = device.get("state") in _ONLINE_DEVICE_STATES

            legacy_device = legacy_devices.get((device.get("macAddress") or "").lower(), {})
            legacy_uplink = legacy_device.get("uplink") or {}

            _resolve_depth(device_id, uplinks, depth_map)

            node = TopologyNode(
                node_id=device_id,
                node_type="device",
                name=device.get("name"),
                mac=device.get("macAddress"),
                ip=device.get("ipAddress"),
                model=device.get("model"),
                # Legacy carries the short type code (usw/uap/udm); the
                # integration API has no equivalent, so fall back to the model.
                type_detail=legacy_device.get("type") or device.get("model"),
                uplink_device_id=uplink_device_id,
                uplink_port=legacy_uplink.get("port_idx"),
                uplink_depth=depth_map.get(device_id, 0),
                state=1 if is_online else 0,
                adopted=True,  # All returned devices are adopted
            )
            nodes.append(node)

            # Create connection if device has uplink
            if uplink_device_id:
                conn = TopologyConnection(
                    connection_id=f"conn_{device_id}_uplink",
                    source_node_id=device_id,
                    target_node_id=uplink_device_id,
                    connection_type="uplink",
                    source_port=legacy_uplink.get("port_idx"),
                    target_port=legacy_uplink.get("uplink_remote_port"),
                    speed_mbps=legacy_uplink.get("speed"),
                    duplex="full" if legacy_uplink.get("full_duplex") else None,
                    is_uplink=True,
                    status="up" if is_online else "down",
                )
                connections.append(conn)

        # Process clients
        for client_data in client_nodes:
            client_id = client_data.get("id", "")
            client_type = client_data.get("type", "WIRED")
            uplink_device_id = client_data.get("uplinkDeviceId")

            node = TopologyNode(
                node_id=client_id,
                node_type="client",
                name=client_data.get("name"),
                mac=client_data.get("macAddress"),
                ip=client_data.get("ipAddress"),
                state=1,  # All returned clients are connected
            )
            nodes.append(node)

            # Create connection for client
            if uplink_device_id:
                conn_type = "wired" if client_type == "WIRED" else "wireless"
                legacy_client = legacy_clients.get(
                    (client_data.get("macAddress") or "").lower(), {}
                )
                target_port = None
                speed_mbps = None
                if conn_type == "wired":
                    target_port = legacy_client.get("sw_port")
                    speed_mbps = legacy_client.get("wired_rate_mbps")
                else:
                    # Wireless negotiated rate is reported in kbps.
                    tx_rate_kbps = legacy_client.get("tx_rate")
                    if tx_rate_kbps:
                        speed_mbps = int(tx_rate_kbps) // 1000 or None

                conn = TopologyConnection(
                    connection_id=f"conn_client_{client_id}",
                    source_node_id=client_id,
                    target_node_id=uplink_device_id,
                    connection_type=conn_type,
                    target_port=target_port,
                    speed_mbps=speed_mbps,
                    is_uplink=False,
                    status="up",
                )
                connections.append(conn)

        # Calculate statistics
        total_devices = len([n for n in nodes if n.node_type == "device"])
        total_clients = len([n for n in nodes if n.node_type == "client"])
        max_depth = max([n.uplink_depth for n in nodes if n.uplink_depth is not None], default=0)

        # Build network diagram
        diagram = NetworkDiagram(
            site_id=actual_site_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            nodes=nodes,
            connections=connections,
            total_devices=total_devices,
            total_clients=total_clients,
            total_connections=len(connections),
            max_depth=max_depth,
            has_coordinates=include_coordinates,
        )

        return diagram.model_dump()


async def get_device_connections(
    site_id: str,
    device_id: str | None,
    settings: Settings,
) -> list[dict]:
    """Get device interconnection details.

    Retrieves detailed connection information for a specific device or all devices.

    Args:
        site_id: Site identifier
        device_id: Specific device ID, or None for all devices
        settings: Application settings

    Returns:
        List of connection dictionaries

    Example:
        ```python
        connections = await get_device_connections("default", "switch_001", settings)
        for conn in connections:
            print(f"{conn['source_node_id']} -> {conn['target_node_id']}")
        ```
    """
    topology = await get_network_topology(site_id, settings)

    connections = cast(list[dict[str, Any]], topology.get("connections", []))

    if device_id:
        # Filter connections for specific device
        connections = [
            conn
            for conn in connections
            if conn.get("source_node_id") == device_id or conn.get("target_node_id") == device_id
        ]

    return connections


async def get_port_mappings(
    site_id: str,
    device_id: str,
    settings: Settings,
) -> dict:
    """Get port-level connection mappings for a device.

    Retrieves detailed information about which ports are connected to which devices/clients.

    Args:
        site_id: Site identifier
        device_id: Device ID
        settings: Application settings

    Returns:
        Dictionary with device_id and port mapping information

    Example:
        ```python
        ports = await get_port_mappings("default", "switch_001", settings)
        for port_num, connected_device in ports['ports'].items():
            print(f"Port {port_num}: {connected_device}")
        ```
    """
    topology = await get_network_topology(site_id, settings)

    connections = topology.get("connections", [])

    # Build port mapping
    port_map = {}

    for conn in connections:
        if conn.get("source_node_id") == device_id:
            port_num = conn.get("source_port")
            if port_num is not None:
                port_map[port_num] = {
                    "connected_to": conn.get("target_node_id"),
                    "connection_type": conn.get("connection_type"),
                    "speed_mbps": conn.get("speed_mbps"),
                    "status": conn.get("status"),
                }
        elif conn.get("target_node_id") == device_id:
            port_num = conn.get("target_port")
            if port_num is not None:
                port_map[port_num] = {
                    "connected_to": conn.get("source_node_id"),
                    "connection_type": conn.get("connection_type"),
                    "speed_mbps": conn.get("speed_mbps"),
                    "status": conn.get("status"),
                }

    return {"device_id": device_id, "ports": port_map}


async def export_topology(
    site_id: str,
    format: Literal["json", "graphml", "dot"],
    settings: Settings,
) -> str:
    """Export network topology in various formats.

    Exports the network topology as JSON, GraphML (XML), or DOT (Graphviz) format.

    Args:
        site_id: Site identifier
        format: Export format ("json", "graphml", or "dot")
        settings: Application settings

    Returns:
        Topology data as a formatted string

    Raises:
        ValidationError: If invalid format is specified

    Example:
        ```python
        # Export as JSON
        json_data = await export_topology("default", "json", settings)

        # Export as GraphML for network visualization tools
        graphml_data = await export_topology("default", "graphml", settings)

        # Export as DOT for Graphviz
        dot_data = await export_topology("default", "dot", settings)
        ```
    """
    if format not in ["json", "graphml", "dot"]:
        raise ValidationError(
            f"Invalid export format: {format}. Must be 'json', 'graphml', or 'dot'"
        )

    topology = await get_network_topology(site_id, settings)

    if format == "json":
        return json.dumps(topology, indent=2)

    elif format == "graphml":
        # Generate GraphML XML
        nodes = topology.get("nodes", [])
        connections = topology.get("connections", [])

        graphml = ['<?xml version="1.0" encoding="UTF-8"?>']
        graphml.append('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">')
        graphml.append('  <graph id="UniFi Network" edgedefault="directed">')

        # Add nodes
        for node in nodes:
            node_id = node.get("node_id", "")
            node_type = node.get("node_type", "")
            name = node.get("name", "")
            graphml.append(f'    <node id="{node_id}">')
            graphml.append(f'      <data key="type">{node_type}</data>')
            graphml.append(f'      <data key="name">{name}</data>')
            graphml.append("    </node>")

        # Add edges
        for conn in connections:
            source = conn.get("source_node_id", "")
            target = conn.get("target_node_id", "")
            conn_type = conn.get("connection_type", "")
            graphml.append(f'    <edge source="{source}" target="{target}">')
            graphml.append(f'      <data key="type">{conn_type}</data>')
            graphml.append("    </edge>")

        graphml.append("  </graph>")
        graphml.append("</graphml>")

        return "\n".join(graphml)

    elif format == "dot":
        # Generate DOT format
        nodes = topology.get("nodes", [])
        connections = topology.get("connections", [])

        dot = ["digraph UniFiNetwork {"]
        dot.append("  node [shape=box];")

        # Add nodes
        for node in nodes:
            node_id = node.get("node_id", "")
            name = node.get("name", node_id)
            node_type = node.get("node_type", "")
            dot.append(f'  "{node_id}" [label="{name}\\n({node_type})"];')

        # Add edges
        for conn in connections:
            source = conn.get("source_node_id", "")
            target = conn.get("target_node_id", "")
            conn_type = conn.get("connection_type", "")
            dot.append(f'  "{source}" -> "{target}" [label="{conn_type}"];')

        dot.append("}")

        return "\n".join(dot)

    return ""


async def get_topology_statistics(
    site_id: str,
    settings: Settings,
) -> dict:
    """Get network topology statistics.

    Retrieves statistical summary of the network topology including device counts,
    client counts, connection counts, and network depth.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Dictionary with topology statistics

    Example:
        ```python
        stats = await get_topology_statistics("default", settings)
        print(f"Devices: {stats['total_devices']}")
        print(f"Clients: {stats['total_clients']}")
        print(f"Max network depth: {stats['max_depth']}")
        ```
    """
    topology = await get_network_topology(site_id, settings)

    return {
        "site_id": topology.get("site_id"),
        "total_devices": topology.get("total_devices", 0),
        "total_clients": topology.get("total_clients", 0),
        "total_connections": topology.get("total_connections", 0),
        "max_depth": topology.get("max_depth", 0),
        "generated_at": topology.get("generated_at"),
    }
