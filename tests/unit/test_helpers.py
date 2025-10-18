"""Unit tests for helper functions."""

from src.utils import helpers


class TestFormattingFunctions:
    """Test suite for formatting helper functions."""

    def test_format_uptime(self) -> None:
        """Test uptime formatting."""
        assert helpers.format_uptime(0) == "0m"
        assert helpers.format_uptime(60) == "1m"
        assert helpers.format_uptime(3600) == "1h 0m"
        assert helpers.format_uptime(3660) == "1h 1m"
        assert helpers.format_uptime(86400) == "1d 0h 0m"
        assert helpers.format_uptime(90061) == "1d 1h 1m"

    def test_format_bytes(self) -> None:
        """Test bytes formatting."""
        assert "0.00 B" in helpers.format_bytes(0)
        assert "1.00 KB" in helpers.format_bytes(1024)
        assert "1.00 MB" in helpers.format_bytes(1024 * 1024)
        assert "1.00 GB" in helpers.format_bytes(1024 * 1024 * 1024)

    def test_format_percentage(self) -> None:
        """Test percentage formatting."""
        assert helpers.format_percentage(0.5) == "50.0%"
        assert helpers.format_percentage(0.123) == "12.3%"
        assert helpers.format_percentage(45.6) == "45.6%"  # Already in 0-100 range


class TestDictionaryHelpers:
    """Test suite for dictionary helper functions."""

    def test_sanitize_dict(self) -> None:
        """Test dictionary sanitization."""
        data = {
            "username": "test",
            "password": "secret",
            "api_key": "key123",
            "email": "test@example.com",
        }

        sanitized = helpers.sanitize_dict(data)

        assert "username" in sanitized
        assert "email" in sanitized
        assert "password" not in sanitized
        assert "api_key" not in sanitized

    def test_sanitize_dict_custom_exclusions(self) -> None:
        """Test sanitization with custom exclusions."""
        data = {"username": "test", "custom_secret": "hidden"}

        sanitized = helpers.sanitize_dict(data, exclude_keys=["custom_secret"])

        assert "username" in sanitized
        assert "custom_secret" not in sanitized

    def test_merge_dicts(self) -> None:
        """Test dictionary merging."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = helpers.merge_dicts(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}
        assert base == {"a": 1, "b": 2}  # Original unchanged


class TestDeviceTypeParser:
    """Test suite for device type parsing."""

    def test_parse_ap_types(self) -> None:
        """Test parsing AP device types."""
        assert helpers.parse_device_type("UAP-AC-Pro") == "ap"
        assert helpers.parse_device_type("U6-LR") == "ap"
        assert helpers.parse_device_type("U7-Pro") == "ap"

    def test_parse_switch_types(self) -> None:
        """Test parsing switch device types."""
        assert helpers.parse_device_type("USW-24-POE") == "switch"
        assert helpers.parse_device_type("UniFi Switch 8") == "switch"

    def test_parse_gateway_types(self) -> None:
        """Test parsing gateway device types."""
        assert helpers.parse_device_type("USG-Pro-4") == "gateway"
        assert helpers.parse_device_type("UDM-Pro") == "gateway"
        assert helpers.parse_device_type("UXG-Max") == "gateway"

    def test_parse_nvr_types(self) -> None:
        """Test parsing NVR device types."""
        assert helpers.parse_device_type("UNVR-Pro") == "nvr"
        assert helpers.parse_device_type("NVR") == "nvr"

    def test_parse_unknown_type(self) -> None:
        """Test parsing unknown device type."""
        assert helpers.parse_device_type("Unknown Device") == "unknown"


class TestURIBuilder:
    """Test suite for URI building."""

    def test_build_simple_uri(self) -> None:
        """Test building simple URI."""
        uri = helpers.build_uri("sites")
        assert uri == "sites://"

    def test_build_uri_with_parts(self) -> None:
        """Test building URI with path parts."""
        uri = helpers.build_uri("sites", "default", "devices")
        assert uri == "sites://default/devices"

    def test_build_uri_with_query(self) -> None:
        """Test building URI with query parameters."""
        uri = helpers.build_uri("sites", "default", query={"limit": 10, "offset": 0})
        assert "sites://default" in uri
        assert "limit=10" in uri
        assert "offset=0" in uri

    def test_build_uri_filters_none_query_values(self) -> None:
        """Test that None query values are filtered out."""
        uri = helpers.build_uri("sites", query={"limit": 10, "filter": None})
        assert "limit=10" in uri
        assert "filter" not in uri


class TestTimestampFunctions:
    """Test suite for timestamp functions."""

    def test_get_timestamp(self) -> None:
        """Test getting Unix timestamp."""
        timestamp = helpers.get_timestamp()
        assert isinstance(timestamp, int)
        assert timestamp > 0

    def test_get_iso_timestamp(self) -> None:
        """Test getting ISO timestamp."""
        iso_ts = helpers.get_iso_timestamp()
        assert isinstance(iso_ts, str)
        assert "T" in iso_ts  # ISO format contains 'T'
        assert "+" in iso_ts or "Z" in iso_ts  # Timezone info
