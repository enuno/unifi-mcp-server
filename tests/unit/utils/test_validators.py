"""Unit tests for validator functions."""

import pytest

from src.utils.exceptions import ValidationError
from src.utils.validators import (
    coerce_bool,
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


class TestCoerceBool:
    def test_bool_true(self):
        assert coerce_bool(True) is True

    def test_bool_false(self):
        assert coerce_bool(False) is False

    def test_string_true(self):
        assert coerce_bool("true") is True

    def test_string_true_uppercase(self):
        assert coerce_bool("True") is True

    def test_string_true_mixed_case(self):
        assert coerce_bool("TRUE") is True

    def test_string_false(self):
        assert coerce_bool("false") is False

    def test_string_false_uppercase(self):
        assert coerce_bool("False") is False

    def test_string_one(self):
        assert coerce_bool("1") is True

    def test_string_zero(self):
        assert coerce_bool("0") is False

    def test_string_yes(self):
        assert coerce_bool("yes") is True

    def test_string_no(self):
        assert coerce_bool("no") is False

    def test_none(self):
        assert coerce_bool(None) is False

    def test_empty_string(self):
        assert coerce_bool("") is False

    def test_int_one(self):
        assert coerce_bool(1) is True

    def test_int_zero(self):
        assert coerce_bool(0) is False


class TestValidateConfirmation:
    def test_valid_confirm_true(self):
        validate_confirmation(True, "test_operation")

    def test_valid_confirm_string_true(self):
        validate_confirmation("true", "test_operation")

    def test_valid_confirm_string_true_uppercase(self):
        validate_confirmation("True", "test_operation")

    def test_valid_confirm_string_one(self):
        validate_confirmation("1", "test_operation")

    def test_invalid_confirm_false(self):
        with pytest.raises(ValidationError, match="requires confirmation"):
            validate_confirmation(False, "test_operation")

    def test_invalid_confirm_string_false(self):
        with pytest.raises(ValidationError, match="requires confirmation"):
            validate_confirmation("false", "test_operation")

    def test_invalid_confirm_none(self):
        with pytest.raises(ValidationError, match="requires confirmation"):
            validate_confirmation(None, "test_operation")

    def test_operation_name_in_message(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_confirmation(False, "delete_network")
        assert "delete_network" in str(exc_info.value)

    def test_dry_run_skips_confirmation_when_confirm_false(self):
        # Should NOT raise - dry_run=True bypasses confirmation
        validate_confirmation(False, "test_operation", dry_run=True)

    def test_dry_run_skips_confirmation_when_confirm_none(self):
        validate_confirmation(None, "test_operation", dry_run=True)

    def test_dry_run_string_true_skips_confirmation(self):
        validate_confirmation(False, "test_operation", dry_run="true")

    def test_dry_run_false_still_requires_confirmation(self):
        with pytest.raises(ValidationError, match="requires confirmation"):
            validate_confirmation(False, "test_operation", dry_run=False)

    def test_dry_run_string_false_still_requires_confirmation(self):
        with pytest.raises(ValidationError, match="requires confirmation"):
            validate_confirmation(False, "test_operation", dry_run="false")

    def test_dry_run_default_is_false(self):
        # Without dry_run param, confirm=False should still raise
        with pytest.raises(ValidationError, match="requires confirmation"):
            validate_confirmation(False, "test_operation")


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


class TestDuplicateResourceError:
    """Tests for DuplicateResourceError exception."""

    def test_basic_creation(self):
        from src.utils.exceptions import DuplicateResourceError

        err = DuplicateResourceError("port_profile", "IoT Profile", "abc123")
        assert err.resource_type == "port_profile"
        assert err.resource_name == "IoT Profile"
        assert err.existing_id == "abc123"
        assert "IoT Profile" in str(err)
        assert "already exists" in str(err)
        assert "abc123" in str(err)

    def test_details_dict(self):
        from src.utils.exceptions import DuplicateResourceError

        err = DuplicateResourceError("network", "Guest LAN", "net456")
        assert err.details["resource_type"] == "network"
        assert err.details["name"] == "Guest LAN"
        assert err.details["existing_id"] == "net456"

    def test_is_unifi_exception(self):
        from src.utils.exceptions import DuplicateResourceError, UniFiMCPException

        err = DuplicateResourceError("port_profile", "Test", "id1")
        assert isinstance(err, UniFiMCPException)


class TestConfirmationRequiredError:
    """Tests for ConfirmationRequiredError exception."""

    def test_basic_creation(self):
        from src.utils.exceptions import ConfirmationRequiredError

        err = ConfirmationRequiredError("delete_network")
        assert err.operation == "delete_network"
        assert "delete_network" in str(err)
        assert "requires confirmation" in str(err)

    def test_details_dict(self):
        from src.utils.exceptions import ConfirmationRequiredError

        err = ConfirmationRequiredError("restart_device")
        assert err.details["operation"] == "restart_device"

    def test_is_unifi_exception(self):
        from src.utils.exceptions import ConfirmationRequiredError, UniFiMCPException

        err = ConfirmationRequiredError("test")
        assert isinstance(err, UniFiMCPException)


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_basic_creation(self):
        from src.utils.exceptions import RateLimitError

        err = RateLimitError()
        assert err.status_code == 429
        assert err.retry_after is None
        assert "Rate limit" in str(err)

    def test_with_retry_after(self):
        from src.utils.exceptions import RateLimitError

        err = RateLimitError(retry_after=60)
        assert err.retry_after == 60
        assert err.status_code == 429

    def test_custom_message(self):
        from src.utils.exceptions import RateLimitError

        err = RateLimitError(message="Too many requests", retry_after=30)
        assert "Too many requests" in str(err)
        assert err.retry_after == 30
