"""Network topology data models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TopologyNode(BaseModel):
    """A node in the network topology (device, client, or network)."""

    node_id: str = Field(..., description="Unique node identifier")
    node_type: Literal["device", "client", "network"] = Field(..., description="Type of node")
    name: str | None = Field(None, description="Node name")
    mac: str | None = Field(None, description="MAC address (for devices/clients)")
    ip: str | None = Field(None, description="IP address")
    model: str | None = Field(None, description="Device model (for devices)")
    type_detail: str | None = Field(None, description="Device type detail (uap, usw, ugw, etc.)")

    # Position and connectivity
    uplink_device_id: str | None = Field(
        None, description="ID of uplink device this node connects to"
    )
    uplink_port: int | None = Field(None, description="Uplink port number")
    uplink_depth: int | None = Field(0, description="Depth in network hierarchy (0=gateway)")

    # Status
    state: int | None = Field(None, description="Node state (0=offline, 1=online)")
    adopted: bool | None = Field(None, description="Whether device is adopted")

    # Coordinates for visualization
    x_coordinate: float | None = Field(None, description="X coordinate for layout")
    y_coordinate: float | None = Field(None, description="Y coordinate for layout")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "node_id": "507f1f77bcf86cd799439011",
                "node_type": "device",
                "name": "AP-Office",
                "mac": "aa:bb:cc:dd:ee:ff",
                "ip": "192.168.2.10",
                "model": "U6-LR",
                "type_detail": "uap",
                "uplink_device_id": "507f1f77bcf86cd799439012",
                "uplink_port": 5,
                "uplink_depth": 1,
                "state": 1,
                "adopted": True,
            }
        },
    )


class TopologyConnection(BaseModel):
    """A connection between two nodes in the network topology."""

    connection_id: str = Field(..., description="Unique connection identifier")
    source_node_id: str = Field(..., description="Source node ID")
    target_node_id: str = Field(..., description="Target node ID")
    connection_type: Literal["wired", "wireless", "uplink"] = Field(
        ..., description="Type of connection"
    )

    # Port information
    source_port: int | None = Field(None, description="Source port number")
    target_port: int | None = Field(None, description="Target port number")
    port_name: str | None = Field(None, description="Port name/description")

    # Connection quality
    speed_mbps: int | None = Field(None, description="Connection speed in Mbps")
    duplex: str | None = Field(None, description="Duplex mode (full/half)")
    link_quality: int | None = Field(None, description="Link quality percentage (0-100)")

    # Status
    status: str | None = Field(None, description="Connection status (up/down)")
    is_uplink: bool = Field(False, description="Whether this is an uplink connection")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "connection_id": "conn_001",
                "source_node_id": "507f1f77bcf86cd799439011",
                "target_node_id": "507f1f77bcf86cd799439012",
                "connection_type": "wired",
                "source_port": 5,
                "target_port": 1,
                "speed_mbps": 1000,
                "duplex": "full",
                "link_quality": 100,
                "status": "up",
                "is_uplink": True,
            }
        },
    )


class NetworkDiagram(BaseModel):
    """Complete network topology structure."""

    site_id: str = Field(..., description="Site identifier")
    site_name: str | None = Field(None, description="Site name")
    generated_at: str = Field(..., description="Timestamp when topology was generated (ISO)")

    # Topology data
    nodes: list[TopologyNode] = Field(default_factory=list, description="All nodes in the topology")
    connections: list[TopologyConnection] = Field(
        default_factory=list, description="All connections between nodes"
    )

    # Summary statistics
    total_devices: int = Field(0, description="Total number of devices")
    total_clients: int = Field(0, description="Total number of clients")
    total_connections: int = Field(0, description="Total number of connections")
    max_depth: int = Field(0, description="Maximum depth in network hierarchy")

    # Layout metadata
    layout_algorithm: str | None = Field(None, description="Algorithm used for node positioning")
    has_coordinates: bool = Field(False, description="Whether nodes have position coordinates")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "site_id": "507f1f77bcf86cd799439013",
                "site_name": "Default",
                "generated_at": "2025-01-24T12:00:00Z",
                "nodes": [],
                "connections": [],
                "total_devices": 5,
                "total_clients": 12,
                "total_connections": 16,
                "max_depth": 3,
                "has_coordinates": False,
            }
        },
    )
