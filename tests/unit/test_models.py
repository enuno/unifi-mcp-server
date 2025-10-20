"""Unit tests for data models."""

from src.models import Client, Device, Network, Site


class TestSiteModel:
    """Test suite for Site model."""

    def test_site_creation_minimal(self) -> None:
        """Test site creation with minimal data."""
        site = Site(_id="default", name="Default Site")
        assert site.id == "default"
        assert site.name == "Default Site"
        assert site.desc is None

    def test_site_creation_full(self) -> None:
        """Test site creation with full data."""
        site = Site(
            _id="site-123",
            name="Test Site",
            desc="Test site description",
            role="admin",
        )
        assert site.id == "site-123"
        assert site.name == "Test Site"
        assert site.desc == "Test site description"
        assert site.role == "admin"

    def test_site_alias_field(self) -> None:
        """Test field alias for _id."""
        data = {"_id": "test", "name": "Test"}
        site = Site(**data)
        assert site.id == "test"


class TestDeviceModel:
    """Test suite for Device model."""

    def test_device_creation_minimal(self) -> None:
        """Test device creation with minimal data."""
        device = Device(
            _id="507f1f77bcf86cd799439011",
            model="U6-LR",
            type="uap",
            mac="aa:bb:cc:dd:ee:ff",
            state=1,
        )
        assert device.id == "507f1f77bcf86cd799439011"
        assert device.model == "U6-LR"
        assert device.type == "uap"
        assert device.mac == "aa:bb:cc:dd:ee:ff"
        assert device.state == 1

    def test_device_creation_full(self) -> None:
        """Test device creation with full data."""
        device = Device(
            _id="507f1f77bcf86cd799439011",
            name="AP-Office",
            model="U6-LR",
            type="uap",
            mac="aa:bb:cc:dd:ee:ff",
            ip="192.168.1.10",
            state=1,
            adopted=True,
            version="6.5.55",
            uptime=86400,
            cpu=25.5,
            mem=45.2,
        )
        assert device.name == "AP-Office"
        assert device.ip == "192.168.1.10"
        assert device.uptime == 86400
        assert device.cpu == 25.5


class TestClientModel:
    """Test suite for Client model."""

    def test_client_creation_minimal(self) -> None:
        """Test client creation with minimal data."""
        client = Client(mac="aa:bb:cc:dd:ee:01")
        assert client.mac == "aa:bb:cc:dd:ee:01"
        assert client.ip is None

    def test_client_creation_full(self) -> None:
        """Test client creation with full data."""
        client = Client(
            mac="aa:bb:cc:dd:ee:01",
            ip="192.168.1.100",
            hostname="laptop-001",
            is_wired=False,
            signal=-45,
            tx_bytes=1024000,
            rx_bytes=2048000,
            vlan=10,
        )
        assert client.mac == "aa:bb:cc:dd:ee:01"
        assert client.ip == "192.168.1.100"
        assert client.hostname == "laptop-001"
        assert client.is_wired is False
        assert client.signal == -45
        assert client.vlan == 10

    def test_client_wireless_fields(self) -> None:
        """Test wireless-specific fields."""
        client = Client(
            mac="aa:bb:cc:dd:ee:01",
            is_wired=False,
            essid="MyWiFi",
            channel=6,
            radio="ng",
            signal=-50,
            rssi=-52,
        )
        assert client.essid == "MyWiFi"
        assert client.channel == 6
        assert client.radio == "ng"


class TestNetworkModel:
    """Test suite for Network model."""

    def test_network_creation_minimal(self) -> None:
        """Test network creation with minimal data."""
        network = Network(
            _id="507f191e810c19729de860ea",
            name="LAN",
            purpose="corporate",
        )
        assert network.id == "507f191e810c19729de860ea"
        assert network.name == "LAN"
        assert network.purpose == "corporate"

    def test_network_creation_full(self) -> None:
        """Test network creation with full data."""
        network = Network(
            _id="507f191e810c19729de860ea",
            name="LAN",
            purpose="corporate",
            vlan_enabled=True,
            vlan_id=1,
            ip_subnet="192.168.1.0/24",
            dhcpd_enabled=True,
            dhcpd_start="192.168.1.100",
            dhcpd_stop="192.168.1.254",
            dhcpd_leasetime=86400,
        )
        assert network.vlan_id == 1
        assert network.ip_subnet == "192.168.1.0/24"
        assert network.dhcpd_enabled is True
        assert network.dhcpd_start == "192.168.1.100"
        assert network.dhcpd_leasetime == 86400

    def test_network_vlan_fields(self) -> None:
        """Test VLAN-specific fields."""
        network = Network(
            _id="test",
            name="Guest",
            purpose="guest",
            vlan_id=100,
        )
        assert network.vlan_id == 100
