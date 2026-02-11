"""Unit tests for validator functions."""

import pytest

from src.utils.exceptions import ValidationError
from src.utils.validators import (
    validate_confirmation,
    validate_device_id,
    validate_ip_address,
    validate_limit_offset,
    validate_mac_address,
    validate_port,
    validate_site_id,
)


class TestValidateMacAddress:
    def test_valid_colon_separated(self):
        result = validate_mac_address("00:11:22:33:44:55")
        assert result == "00:11:22:33:44:55"

    def test_valid_hyphen_separated(self):
        result = validate_mac_address("00-11-22-33-44-55")
        assert result == "00:11:22:33:44:55"

    def test_valid_dot_separated(self):
        result = validate_mac_address("0011.2233.4455")
        assert result == "00:11:22:33:44:55"

    def test_valid_no_separator(self):
        result = validate_mac_address("001122334455")
        assert result == "00:11:22:33:44:55"

    def test_valid_uppercase(self):
        result = validate_mac_address("AA:BB:CC:DD:EE:FF")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_valid_mixed_case(self):
        result = validate_mac_address("Aa:Bb:Cc:Dd:Ee:Ff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_invalid_too_short(self):
        with pytest.raises(ValidationError, match="Invalid MAC address"):
            validate_mac_address("00:11:22:33:44")

    def test_invalid_too_long(self):
        with pytest.raises(ValidationError, match="Invalid MAC address"):
            validate_mac_address("00:11:22:33:44:55:66")

    def test_invalid_characters(self):
        with pytest.raises(ValidationError, match="Invalid MAC address"):
            validate_mac_address("00:11:22:33:44:GG")


class TestValidateIpAddress:
    def test_valid_ip(self):
        result = validate_ip_address("192.168.2.1")
        assert result == "192.168.2.1"

    def test_valid_ip_zeros(self):
        result = validate_ip_address("0.0.0.0")
        assert result == "0.0.0.0"

    def test_valid_ip_max(self):
        result = validate_ip_address("255.255.255.255")
        assert result == "255.255.255.255"

    def test_invalid_too_few_octets(self):
        with pytest.raises(ValidationError, match="Invalid IP address"):
            validate_ip_address("192.168.1")

    def test_invalid_too_many_octets(self):
        with pytest.raises(ValidationError, match="Invalid IP address"):
            validate_ip_address("192.168.2.1.1")

    def test_invalid_octet_too_high(self):
        with pytest.raises(ValidationError, match="Invalid IP address"):
            validate_ip_address("192.168.1.256")

    def test_invalid_negative_octet(self):
        with pytest.raises(ValidationError, match="Invalid IP address"):
            validate_ip_address("192.168.1.-1")

    def test_invalid_non_numeric(self):
        with pytest.raises(ValidationError, match="Invalid IP address"):
            validate_ip_address("192.168.1.abc")


class TestValidatePort:
    def test_valid_port_min(self):
        result = validate_port(1)
        assert result == 1

    def test_valid_port_max(self):
        result = validate_port(65535)
        assert result == 65535

    def test_valid_port_common(self):
        assert validate_port(80) == 80
        assert validate_port(443) == 443
        assert validate_port(22) == 22

    def test_invalid_port_zero(self):
        with pytest.raises(ValidationError, match="Invalid port"):
            validate_port(0)

    def test_invalid_port_too_high(self):
        with pytest.raises(ValidationError, match="Invalid port"):
            validate_port(65536)

    def test_invalid_port_negative(self):
        with pytest.raises(ValidationError, match="Invalid port"):
            validate_port(-1)


class TestValidateSiteId:
    def test_valid_default(self):
        result = validate_site_id("default")
        assert result == "default"

    def test_valid_with_hyphen(self):
        result = validate_site_id("my-site")
        assert result == "my-site"

    def test_valid_with_underscore(self):
        result = validate_site_id("my_site")
        assert result == "my_site"

    def test_valid_alphanumeric(self):
        result = validate_site_id("Site123")
        assert result == "Site123"

    def test_invalid_empty(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_site_id("")

    def test_invalid_none(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_site_id(None)

    def test_invalid_special_chars(self):
        with pytest.raises(ValidationError, match="Invalid site ID"):
            validate_site_id("site@123")

    def test_invalid_spaces(self):
        with pytest.raises(ValidationError, match="Invalid site ID"):
            validate_site_id("my site")


class TestValidateDeviceId:
    def test_valid_device_id(self):
        result = validate_device_id("507f1f77bcf86cd799439011")
        assert result == "507f1f77bcf86cd799439011"

    def test_valid_device_id_uppercase(self):
        result = validate_device_id("507F1F77BCF86CD799439011")
        assert result == "507f1f77bcf86cd799439011"

    def test_invalid_empty(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_device_id("")

    def test_invalid_none(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_device_id(None)

    def test_invalid_too_short(self):
        with pytest.raises(ValidationError, match="Invalid device ID"):
            validate_device_id("507f1f77bcf86cd79943901")

    def test_invalid_too_long(self):
        with pytest.raises(ValidationError, match="Invalid device ID"):
            validate_device_id("507f1f77bcf86cd7994390111")

    def test_invalid_non_hex(self):
        with pytest.raises(ValidationError, match="Invalid device ID"):
            validate_device_id("507f1f77bcf86cd79943901g")


class TestValidateConfirmation:
    def test_valid_confirm_true(self):
        validate_confirmation(True, "test_operation")

    def test_invalid_confirm_false(self):
        with pytest.raises(ValidationError, match="requires confirmation"):
            validate_confirmation(False, "test_operation")

    def test_invalid_confirm_none(self):
        with pytest.raises(ValidationError, match="requires confirmation"):
            validate_confirmation(None, "test_operation")

    def test_operation_name_in_message(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_confirmation(False, "delete_network")
        assert "delete_network" in str(exc_info.value)


class TestValidateLimitOffset:
    def test_defaults(self):
        limit, offset = validate_limit_offset()
        assert limit == 100
        assert offset == 0

    def test_custom_limit(self):
        limit, offset = validate_limit_offset(limit=50)
        assert limit == 50
        assert offset == 0

    def test_custom_offset(self):
        limit, offset = validate_limit_offset(offset=10)
        assert limit == 100
        assert offset == 10

    def test_custom_both(self):
        limit, offset = validate_limit_offset(limit=25, offset=50)
        assert limit == 25
        assert offset == 50

    def test_min_limit(self):
        limit, offset = validate_limit_offset(limit=1)
        assert limit == 1

    def test_max_limit(self):
        limit, offset = validate_limit_offset(limit=1000)
        assert limit == 1000

    def test_invalid_limit_zero(self):
        with pytest.raises(ValidationError, match="Limit must be"):
            validate_limit_offset(limit=0)

    def test_invalid_limit_too_high(self):
        with pytest.raises(ValidationError, match="Limit must be"):
            validate_limit_offset(limit=1001)

    def test_invalid_offset_negative(self):
        with pytest.raises(ValidationError, match="Offset must be"):
            validate_limit_offset(offset=-1)

    def test_zero_offset_valid(self):
        limit, offset = validate_limit_offset(offset=0)
        assert offset == 0
