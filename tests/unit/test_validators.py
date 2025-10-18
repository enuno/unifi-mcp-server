"""Unit tests for validator functions."""

import pytest

from src.utils import ValidationError, validators


class TestMACAddressValidator:
    """Test suite for MAC address validation."""

    def test_valid_mac_colon_separated(self) -> None:
        """Test valid MAC address with colons."""
        result = validators.validate_mac_address("aa:bb:cc:dd:ee:ff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_valid_mac_hyphen_separated(self) -> None:
        """Test valid MAC address with hyphens."""
        result = validators.validate_mac_address("AA-BB-CC-DD-EE-FF")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_valid_mac_no_separator(self) -> None:
        """Test valid MAC address without separators."""
        result = validators.validate_mac_address("aabbccddeeff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_invalid_mac_address(self) -> None:
        """Test invalid MAC address."""
        with pytest.raises(ValidationError, match="Invalid MAC address"):
            validators.validate_mac_address("invalid")

    def test_mac_wrong_length(self) -> None:
        """Test MAC address with wrong length."""
        with pytest.raises(ValidationError):
            validators.validate_mac_address("aa:bb:cc:dd:ee")


class TestIPAddressValidator:
    """Test suite for IP address validation."""

    def test_valid_ip_address(self) -> None:
        """Test valid IP address."""
        result = validators.validate_ip_address("192.168.1.1")
        assert result == "192.168.1.1"

    def test_invalid_ip_format(self) -> None:
        """Test invalid IP address format."""
        with pytest.raises(ValidationError, match="Invalid IP address"):
            validators.validate_ip_address("192.168.1")

    def test_invalid_ip_octet(self) -> None:
        """Test invalid IP address octet."""
        with pytest.raises(ValidationError):
            validators.validate_ip_address("192.168.1.256")

    def test_invalid_ip_characters(self) -> None:
        """Test IP address with invalid characters."""
        with pytest.raises(ValidationError):
            validators.validate_ip_address("192.168.1.abc")


class TestPortValidator:
    """Test suite for port validation."""

    def test_valid_port(self) -> None:
        """Test valid port number."""
        assert validators.validate_port(8080) == 8080
        assert validators.validate_port(1) == 1
        assert validators.validate_port(65535) == 65535

    def test_invalid_port_too_low(self) -> None:
        """Test port number too low."""
        with pytest.raises(ValidationError, match="Invalid port"):
            validators.validate_port(0)

    def test_invalid_port_too_high(self) -> None:
        """Test port number too high."""
        with pytest.raises(ValidationError, match="Invalid port"):
            validators.validate_port(99999)


class TestSiteIDValidator:
    """Test suite for site ID validation."""

    def test_valid_site_id(self) -> None:
        """Test valid site ID."""
        assert validators.validate_site_id("default") == "default"
        assert validators.validate_site_id("site-123") == "site-123"
        assert validators.validate_site_id("my_site") == "my_site"

    def test_empty_site_id(self) -> None:
        """Test empty site ID."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validators.validate_site_id("")

    def test_invalid_site_id_characters(self) -> None:
        """Test site ID with invalid characters."""
        with pytest.raises(ValidationError, match="Invalid site ID"):
            validators.validate_site_id("site@123")


class TestDeviceIDValidator:
    """Test suite for device ID validation."""

    def test_valid_device_id(self) -> None:
        """Test valid device ID."""
        device_id = "507f1f77bcf86cd799439011"
        result = validators.validate_device_id(device_id)
        assert result == device_id.lower()

    def test_invalid_device_id_length(self) -> None:
        """Test device ID with wrong length."""
        with pytest.raises(ValidationError, match="Invalid device ID"):
            validators.validate_device_id("short")

    def test_invalid_device_id_characters(self) -> None:
        """Test device ID with invalid characters."""
        with pytest.raises(ValidationError):
            validators.validate_device_id("xxxxxxxxxxxxxxxxxxxxxxxx")


class TestConfirmationValidator:
    """Test suite for confirmation validation."""

    def test_confirmation_provided(self) -> None:
        """Test with confirmation provided."""
        # Should not raise error
        validators.validate_confirmation(True, "test_operation")

    def test_confirmation_missing(self) -> None:
        """Test without confirmation."""
        with pytest.raises(ValidationError, match="requires confirmation"):
            validators.validate_confirmation(False, "test_operation")

    def test_confirmation_none(self) -> None:
        """Test with None confirmation."""
        with pytest.raises(ValidationError, match="requires confirmation"):
            validators.validate_confirmation(None, "test_operation")


class TestLimitOffsetValidator:
    """Test suite for pagination validation."""

    def test_default_values(self) -> None:
        """Test default limit and offset."""
        limit, offset = validators.validate_limit_offset()
        assert limit == 100
        assert offset == 0

    def test_custom_values(self) -> None:
        """Test custom limit and offset."""
        limit, offset = validators.validate_limit_offset(50, 10)
        assert limit == 50
        assert offset == 10

    def test_invalid_limit_too_high(self) -> None:
        """Test limit exceeding maximum."""
        with pytest.raises(ValidationError, match="between 1 and 1000"):
            validators.validate_limit_offset(2000, 0)

    def test_invalid_limit_too_low(self) -> None:
        """Test limit below minimum."""
        with pytest.raises(ValidationError, match="between 1 and 1000"):
            validators.validate_limit_offset(0, 0)

    def test_invalid_offset_negative(self) -> None:
        """Test negative offset."""
        with pytest.raises(ValidationError, match="must be non-negative"):
            validators.validate_limit_offset(100, -1)
