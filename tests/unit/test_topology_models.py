"""Unit tests for topology data models."""

import pytest
from pydantic import ValidationError

from src.models.topology import NetworkDiagram, TopologyConnection, TopologyNode


class TestTopologyNode:
    """Test suite for TopologyNode model."""

    def test_create_device_node(self) -> None:
        """Test creating a device node with all fields."""
        node = TopologyNode(
            node_id="device_001",
            node_type="device",
            name="AP-Office",
            mac="aa:bb:cc:dd:ee:ff",
            ip="192.168.2.10",
            model="U6-LR",
            type_detail="uap",
            uplink_device_id="gateway_001",
            uplink_port=5,
            uplink_depth=1,
            state=1,
            adopted=True,
            x_coordinate=100.0,
            y_coordinate=200.0,
        )

        assert node.node_id == "device_001"
        assert node.node_type == "device"
        assert node.name == "AP-Office"
        assert node.mac == "aa:bb:cc:dd:ee:ff"
        assert node.ip == "192.168.2.10"
        assert node.model == "U6-LR"
        assert node.type_detail == "uap"
        assert node.uplink_device_id == "gateway_001"
        assert node.uplink_port == 5
        assert node.uplink_depth == 1
        assert node.state == 1
        assert node.adopted is True
        assert node.x_coordinate == 100.0
        assert node.y_coordinate == 200.0

    def test_create_client_node(self) -> None:
        """Test creating a client node."""
        node = TopologyNode(
            node_id="client_001",
            node_type="client",
            name="iPhone",
            mac="11:22:33:44:55:66",
            ip="192.168.2.100",
            uplink_device_id="device_001",
            state=1,
        )

        assert node.node_id == "client_001"
        assert node.node_type == "client"
        assert node.name == "iPhone"
        assert node.mac == "11:22:33:44:55:66"
        assert node.model is None  # Clients don't have models
        assert node.type_detail is None

    def test_create_network_node(self) -> None:
        """Test creating a network node."""
        node = TopologyNode(
            node_id="network_001",
            node_type="network",
            name="Corporate VLAN",
            ip="192.168.1.0/24",
            uplink_depth=0,
        )

        assert node.node_id == "network_001"
        assert node.node_type == "network"
        assert node.name == "Corporate VLAN"
        assert node.mac is None  # Networks don't have MACs
        assert node.model is None

    def test_invalid_node_type(self) -> None:
        """Test that invalid node types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TopologyNode(
                node_id="invalid_001",
                node_type="invalid_type",  # type: ignore
            )

        assert "node_type" in str(exc_info.value)

    def test_minimal_node(self) -> None:
        """Test creating a node with minimal required fields."""
        node = TopologyNode(
            node_id="minimal_001",
            node_type="device",
        )

        assert node.node_id == "minimal_001"
        assert node.node_type == "device"
        assert node.name is None
        assert node.uplink_depth == 0  # Default value

    def test_node_json_serialization(self) -> None:
        """Test that nodes can be serialized to JSON."""
        node = TopologyNode(
            node_id="device_001",
            node_type="device",
            name="Test Device",
            state=1,
        )

        json_data = node.model_dump()
        assert json_data["node_id"] == "device_001"
        assert json_data["node_type"] == "device"
        assert json_data["name"] == "Test Device"


class TestTopologyConnection:
    """Test suite for TopologyConnection model."""

    def test_create_wired_connection(self) -> None:
        """Test creating a wired connection with all fields."""
        conn = TopologyConnection(
            connection_id="conn_001",
            source_node_id="device_001",
            target_node_id="device_002",
            connection_type="wired",
            source_port=5,
            target_port=1,
            port_name="Port 5",
            speed_mbps=1000,
            duplex="full",
            link_quality=100,
            status="up",
            is_uplink=True,
        )

        assert conn.connection_id == "conn_001"
        assert conn.source_node_id == "device_001"
        assert conn.target_node_id == "device_002"
        assert conn.connection_type == "wired"
        assert conn.source_port == 5
        assert conn.target_port == 1
        assert conn.port_name == "Port 5"
        assert conn.speed_mbps == 1000
        assert conn.duplex == "full"
        assert conn.link_quality == 100
        assert conn.status == "up"
        assert conn.is_uplink is True

    def test_create_wireless_connection(self) -> None:
        """Test creating a wireless connection."""
        conn = TopologyConnection(
            connection_id="conn_002",
            source_node_id="client_001",
            target_node_id="device_001",
            connection_type="wireless",
            link_quality=85,
            status="up",
            is_uplink=False,
        )

        assert conn.connection_id == "conn_002"
        assert conn.connection_type == "wireless"
        assert conn.link_quality == 85
        assert conn.is_uplink is False
        assert conn.source_port is None  # Wireless doesn't have ports
        assert conn.target_port is None

    def test_create_uplink_connection(self) -> None:
        """Test creating an uplink connection."""
        conn = TopologyConnection(
            connection_id="conn_003",
            source_node_id="device_001",
            target_node_id="gateway_001",
            connection_type="uplink",
            is_uplink=True,
            speed_mbps=10000,
            status="up",
        )

        assert conn.connection_type == "uplink"
        assert conn.is_uplink is True
        assert conn.speed_mbps == 10000

    def test_invalid_connection_type(self) -> None:
        """Test that invalid connection types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TopologyConnection(
                connection_id="invalid_001",
                source_node_id="device_001",
                target_node_id="device_002",
                connection_type="invalid_type",  # type: ignore
            )

        assert "connection_type" in str(exc_info.value)

    def test_minimal_connection(self) -> None:
        """Test creating a connection with minimal required fields."""
        conn = TopologyConnection(
            connection_id="minimal_001",
            source_node_id="device_001",
            target_node_id="device_002",
            connection_type="wired",
        )

        assert conn.connection_id == "minimal_001"
        assert conn.source_node_id == "device_001"
        assert conn.target_node_id == "device_002"
        assert conn.is_uplink is False  # Default value

    def test_connection_json_serialization(self) -> None:
        """Test that connections can be serialized to JSON."""
        conn = TopologyConnection(
            connection_id="conn_001",
            source_node_id="device_001",
            target_node_id="device_002",
            connection_type="wired",
            speed_mbps=1000,
        )

        json_data = conn.model_dump()
        assert json_data["connection_id"] == "conn_001"
        assert json_data["connection_type"] == "wired"
        assert json_data["speed_mbps"] == 1000


class TestNetworkDiagram:
    """Test suite for NetworkDiagram model."""

    def test_create_empty_diagram(self) -> None:
        """Test creating an empty network diagram."""
        diagram = NetworkDiagram(
            site_id="site_001",
            site_name="Default",
            generated_at="2025-01-24T12:00:00Z",
        )

        assert diagram.site_id == "site_001"
        assert diagram.site_name == "Default"
        assert diagram.generated_at == "2025-01-24T12:00:00Z"
        assert diagram.nodes == []
        assert diagram.connections == []
        assert diagram.total_devices == 0
        assert diagram.total_clients == 0
        assert diagram.total_connections == 0
        assert diagram.max_depth == 0
        assert diagram.has_coordinates is False
        assert diagram.layout_algorithm is None

    def test_create_diagram_with_nodes(self) -> None:
        """Test creating a diagram with nodes and connections."""
        node1 = TopologyNode(
            node_id="device_001",
            node_type="device",
            name="Gateway",
            uplink_depth=0,
        )
        node2 = TopologyNode(
            node_id="device_002",
            node_type="device",
            name="Switch",
            uplink_depth=1,
        )
        node3 = TopologyNode(
            node_id="client_001",
            node_type="client",
            name="Laptop",
            uplink_depth=2,
        )

        conn1 = TopologyConnection(
            connection_id="conn_001",
            source_node_id="device_002",
            target_node_id="device_001",
            connection_type="wired",
            is_uplink=True,
        )
        conn2 = TopologyConnection(
            connection_id="conn_002",
            source_node_id="client_001",
            target_node_id="device_002",
            connection_type="wired",
        )

        diagram = NetworkDiagram(
            site_id="site_001",
            generated_at="2025-01-24T12:00:00Z",
            nodes=[node1, node2, node3],
            connections=[conn1, conn2],
            total_devices=2,
            total_clients=1,
            total_connections=2,
            max_depth=2,
        )

        assert len(diagram.nodes) == 3
        assert len(diagram.connections) == 2
        assert diagram.total_devices == 2
        assert diagram.total_clients == 1
        assert diagram.total_connections == 2
        assert diagram.max_depth == 2

    def test_diagram_with_coordinates(self) -> None:
        """Test diagram with positioned nodes."""
        node = TopologyNode(
            node_id="device_001",
            node_type="device",
            x_coordinate=100.0,
            y_coordinate=200.0,
        )

        diagram = NetworkDiagram(
            site_id="site_001",
            generated_at="2025-01-24T12:00:00Z",
            nodes=[node],
            has_coordinates=True,
            layout_algorithm="force-directed",
        )

        assert diagram.has_coordinates is True
        assert diagram.layout_algorithm == "force-directed"
        assert diagram.nodes[0].x_coordinate == 100.0
        assert diagram.nodes[0].y_coordinate == 200.0

    def test_diagram_json_serialization(self) -> None:
        """Test that diagrams can be serialized to JSON."""
        node = TopologyNode(node_id="device_001", node_type="device")
        diagram = NetworkDiagram(
            site_id="site_001",
            generated_at="2025-01-24T12:00:00Z",
            nodes=[node],
            total_devices=1,
        )

        json_data = diagram.model_dump()
        assert json_data["site_id"] == "site_001"
        assert json_data["total_devices"] == 1
        assert len(json_data["nodes"]) == 1
        assert json_data["nodes"][0]["node_id"] == "device_001"

    def test_minimal_diagram(self) -> None:
        """Test creating a diagram with minimal required fields."""
        diagram = NetworkDiagram(
            site_id="site_001",
            generated_at="2025-01-24T12:00:00Z",
        )

        assert diagram.site_id == "site_001"
        assert diagram.generated_at == "2025-01-24T12:00:00Z"
        assert diagram.nodes == []  # Default empty list
        assert diagram.connections == []  # Default empty list
