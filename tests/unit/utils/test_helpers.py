"""Unit tests for helper utility functions."""

from src.utils.helpers import (
    build_uri,
    first_response_item,
    format_bytes,
    format_percentage,
    format_uptime,
    get_iso_timestamp,
    get_timestamp,
    merge_dicts,
    parse_device_type,
    sanitize_dict,
)


class TestGetTimestamp:
    """Tests for get_timestamp function."""

    def test_returns_integer(self):
        """Test that get_timestamp returns an integer."""
        result = get_timestamp()
        assert isinstance(result, int)

    def test_returns_positive(self):
        """Test that timestamp is positive."""
        result = get_timestamp()
        assert result > 0

    def test_returns_reasonable_value(self):
        """Test that timestamp is reasonable (after 2024)."""
        result = get_timestamp()
        # Timestamp for 2024-01-01 is approximately 1704067200
        assert result > 1704067200


class TestGetIsoTimestamp:
    """Tests for get_iso_timestamp function."""

    def test_returns_string(self):
        """Test that get_iso_timestamp returns a string."""
        result = get_iso_timestamp()
        assert isinstance(result, str)

    def test_contains_t_separator(self):
        """Test that ISO timestamp contains T separator."""
        result = get_iso_timestamp()
        assert "T" in result

    def test_ends_with_timezone(self):
        """Test that timestamp ends with timezone info."""
        result = get_iso_timestamp()
        # Should end with +00:00 for UTC
        assert "+00:00" in result or "Z" in result


class TestFormatUptime:
    """Tests for format_uptime function."""

    def test_minutes_only(self):
        """Test formatting when less than an hour."""
        result = format_uptime(300)  # 5 minutes
        assert result == "5m"

    def test_hours_and_minutes(self):
        """Test formatting with hours and minutes."""
        result = format_uptime(7200)  # 2 hours
        assert result == "2h 0m"

    def test_hours_and_minutes_non_zero(self):
        """Test formatting with non-zero hours and minutes."""
        result = format_uptime(5430)  # 1h 30m 30s
        assert result == "1h 30m"

    def test_days_hours_minutes(self):
        """Test formatting with days, hours, and minutes."""
        result = format_uptime(90000)  # 1d 1h 0m
        assert result == "1d 1h 0m"

    def test_multiple_days(self):
        """Test formatting with multiple days."""
        result = format_uptime(259200)  # 3 days
        assert result == "3d 0h 0m"

    def test_complex_uptime(self):
        """Test complex uptime with days, hours, and minutes."""
        # 2 days, 4 hours, 30 minutes = 2*86400 + 4*3600 + 30*60
        result = format_uptime(2 * 86400 + 4 * 3600 + 30 * 60)
        assert result == "2d 4h 30m"

    def test_zero_uptime(self):
        """Test formatting with zero uptime."""
        result = format_uptime(0)
        assert result == "0m"


class TestFormatBytes:
    """Tests for format_bytes function."""

    def test_bytes(self):
        """Test formatting bytes."""
        result = format_bytes(500)
        assert result == "500.00 B"

    def test_kilobytes(self):
        """Test formatting kilobytes."""
        result = format_bytes(1024)
        assert result == "1.00 KB"

    def test_megabytes(self):
        """Test formatting megabytes."""
        result = format_bytes(1048576)
        assert result == "1.00 MB"

    def test_gigabytes(self):
        """Test formatting gigabytes."""
        result = format_bytes(1073741824)
        assert result == "1.00 GB"

    def test_terabytes(self):
        """Test formatting terabytes."""
        result = format_bytes(1099511627776)
        assert result == "1.00 TB"

    def test_petabytes(self):
        """Test formatting petabytes."""
        result = format_bytes(1125899906842624)
        assert result == "1.00 PB"

    def test_custom_precision(self):
        """Test formatting with custom precision."""
        result = format_bytes(1500, precision=1)
        assert result == "1.5 KB"

    def test_zero_bytes(self):
        """Test formatting zero bytes."""
        result = format_bytes(0)
        assert result == "0.00 B"

    def test_large_value(self):
        """Test formatting very large value (> PB)."""
        # 2 PB
        result = format_bytes(2 * 1125899906842624)
        assert result == "2.00 PB"


class TestFormatPercentage:
    """Tests for format_percentage function."""

    def test_decimal_format(self):
        """Test formatting decimal value (0-1 range)."""
        result = format_percentage(0.453)
        assert result == "45.3%"

    def test_integer_format(self):
        """Test formatting integer value (0-100 range)."""
        result = format_percentage(45.3)
        assert result == "45.3%"

    def test_zero(self):
        """Test formatting zero."""
        result = format_percentage(0)
        assert result == "0.0%"

    def test_hundred_percent(self):
        """Test formatting 100%."""
        result = format_percentage(100)
        assert result == "100.0%"

    def test_one_decimal(self):
        """Test formatting decimal 1.0 (100%)."""
        result = format_percentage(1.0)
        assert result == "100.0%"

    def test_custom_precision(self):
        """Test formatting with custom precision."""
        result = format_percentage(0.4567, precision=2)
        assert result == "45.67%"


class TestSanitizeDict:
    """Tests for sanitize_dict function."""

    def test_removes_password(self):
        """Test that password is removed."""
        data = {"username": "admin", "password": "secret123"}
        result = sanitize_dict(data)
        assert "username" in result
        assert "password" not in result

    def test_removes_api_key(self):
        """Test that api_key is removed."""
        data = {"name": "test", "api_key": "key123"}
        result = sanitize_dict(data)
        assert "name" in result
        assert "api_key" not in result

    def test_removes_secret(self):
        """Test that secret is removed."""
        data = {"id": "123", "secret": "mysecret"}
        result = sanitize_dict(data)
        assert "id" in result
        assert "secret" not in result

    def test_removes_token(self):
        """Test that token is removed."""
        data = {"user": "test", "token": "bearer123"}
        result = sanitize_dict(data)
        assert "user" in result
        assert "token" not in result

    def test_removes_x_api_key(self):
        """Test that x-api-key is removed."""
        data = {"data": "value", "x-api-key": "key123"}
        result = sanitize_dict(data)
        assert "data" in result
        assert "x-api-key" not in result

    def test_case_insensitive(self):
        """Test that removal is case-insensitive."""
        data = {"PASSWORD": "secret", "Api_Key": "key123"}
        result = sanitize_dict(data)
        assert "PASSWORD" not in result
        assert "Api_Key" not in result

    def test_custom_exclude_keys(self):
        """Test with custom exclude keys."""
        data = {"name": "test", "custom_secret": "value", "password": "pass"}
        result = sanitize_dict(data, exclude_keys=["custom_secret"])
        assert "name" in result
        assert "custom_secret" not in result
        assert "password" in result  # Not in custom list

    def test_preserves_safe_keys(self):
        """Test that safe keys are preserved."""
        data = {"name": "test", "email": "test@example.com", "id": "123"}
        result = sanitize_dict(data)
        assert result == data

    def test_empty_dict(self):
        """Test with empty dictionary."""
        result = sanitize_dict({})
        assert result == {}


class TestMergeDicts:
    """Tests for merge_dicts function."""

    def test_basic_merge(self):
        """Test basic dictionary merge."""
        base = {"a": 1, "b": 2}
        override = {"c": 3}
        result = merge_dicts(base, override)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_override_values(self):
        """Test that override values take precedence."""
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = merge_dicts(base, override)
        assert result == {"a": 1, "b": 3}

    def test_preserves_base(self):
        """Test that base dictionary is not modified."""
        base = {"a": 1}
        override = {"b": 2}
        merge_dicts(base, override)
        assert base == {"a": 1}

    def test_empty_base(self):
        """Test merge with empty base."""
        result = merge_dicts({}, {"a": 1})
        assert result == {"a": 1}

    def test_empty_override(self):
        """Test merge with empty override."""
        result = merge_dicts({"a": 1}, {})
        assert result == {"a": 1}

    def test_both_empty(self):
        """Test merge with both empty."""
        result = merge_dicts({}, {})
        assert result == {}


class TestParseDeviceType:
    """Tests for parse_device_type function."""

    def test_uap_device(self):
        """Test parsing UAP device type."""
        result = parse_device_type("UAP-AC-Pro")
        assert result == "ap"

    def test_u6_device(self):
        """Test parsing U6 device type."""
        result = parse_device_type("U6-LR")
        assert result == "ap"

    def test_u7_device(self):
        """Test parsing U7 device type."""
        result = parse_device_type("U7-Pro")
        assert result == "ap"

    def test_usw_device(self):
        """Test parsing USW switch type."""
        result = parse_device_type("USW-48-PoE")
        assert result == "switch"

    def test_switch_keyword(self):
        """Test parsing device with 'switch' keyword."""
        result = parse_device_type("Flex-Switch")
        assert result == "switch"

    def test_usg_device(self):
        """Test parsing USG gateway type."""
        result = parse_device_type("USG-Pro-4")
        assert result == "gateway"

    def test_udm_device(self):
        """Test parsing UDM gateway type."""
        result = parse_device_type("UDM-Pro")
        assert result == "gateway"

    def test_uxg_device(self):
        """Test parsing UXG gateway type."""
        result = parse_device_type("UXG-Pro")
        assert result == "gateway"

    def test_unvr_device(self):
        """Test parsing UNVR NVR type."""
        result = parse_device_type("UNVR-Pro")
        assert result == "nvr"

    def test_nvr_keyword(self):
        """Test parsing device with 'nvr' keyword."""
        result = parse_device_type("Network-NVR")
        assert result == "nvr"

    def test_unknown_device(self):
        """Test parsing unknown device type."""
        result = parse_device_type("Unknown-Model-123")
        assert result == "unknown"

    def test_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        result = parse_device_type("uap-ac-pro")
        assert result == "ap"


class TestBuildUri:
    """Tests for build_uri function."""

    def test_basic_uri(self):
        """Test building basic URI."""
        result = build_uri("sites", "default", "devices")
        assert result == "sites://default/devices"

    def test_single_part(self):
        """Test building URI with single part."""
        result = build_uri("sites", "default")
        assert result == "sites://default"

    def test_empty_parts(self):
        """Test building URI with no parts."""
        result = build_uri("sites")
        assert result == "sites://"

    def test_with_query_params(self):
        """Test building URI with query parameters."""
        result = build_uri("sites", "default", query={"limit": 10, "offset": 0})
        assert result == "sites://default?limit=10&offset=0"

    def test_query_params_skip_none(self):
        """Test that None query params are skipped."""
        result = build_uri("sites", "default", query={"limit": 10, "offset": None})
        assert result == "sites://default?limit=10"

    def test_empty_query(self):
        """Test building URI with empty query dict."""
        result = build_uri("sites", "default", query={})
        assert result == "sites://default"

    def test_multiple_query_params(self):
        """Test building URI with multiple query params."""
        result = build_uri(
            "sites", "default", "clients", query={"active": True, "type": "wireless"}
        )
        assert "sites://default/clients?" in result
        assert "active=True" in result
        assert "type=wireless" in result

    def test_skips_empty_parts(self):
        """Test that empty parts are skipped."""
        result = build_uri("sites", "", "default", None, "devices")
        assert result == "sites://default/devices"

    def test_query_all_none_values(self):
        """Test building URI when all query values are None."""
        result = build_uri("sites", "default", query={"limit": None, "offset": None})
        assert result == "sites://default"
        assert "?" not in result


class TestFirstResponseItem:
    """Tests for first_response_item function."""

    def test_data_wrapped_object(self):
        """Test extracting the object from a data-wrapped response."""
        assert first_response_item({"data": [{"_id": "abc"}]}) == {"_id": "abc"}

    def test_bare_list(self):
        """Test extracting the object when the response is a bare list."""
        assert first_response_item([{"_id": "abc"}]) == {"_id": "abc"}

    def test_returns_first_of_many(self):
        """Test that only the first item is returned."""
        assert first_response_item({"data": [{"n": 1}, {"n": 2}]}) == {"n": 1}

    def test_empty_data_list(self):
        """Test that an empty data list yields an empty dict, not IndexError.

        This is the regression case: an accepted write that is not echoed back
        used to raise IndexError while parsing the reply, leaving the caller
        unable to tell whether the write landed.
        """
        assert first_response_item({"data": []}) == {}

    def test_empty_bare_list(self):
        """Test that an empty bare list yields an empty dict."""
        assert first_response_item([]) == {}

    def test_non_dict_scalars_yield_empty_dict(self):
        """None or a scalar reply must not raise after the write landed."""
        for odd in (None, "ok", 1, True):
            assert first_response_item(odd) == {}

    def test_missing_data_key(self):
        """Test that a response with no data key yields an empty dict."""
        assert first_response_item({"meta": {"rc": "ok"}}) == {}

    def test_dict_data_is_the_item(self):
        """A single-object data wrapper yields that object.

        Some routes wrap one object rather than a list of one; treating
        it as malformed dropped the echo of a write that landed.
        """
        assert first_response_item({"data": {"_id": "abc"}}) == {"_id": "abc"}

    def test_scalar_data_yields_empty_dict(self):
        """A scalar data value still yields an empty dict."""
        assert first_response_item({"data": "ok"}) == {}

    def test_non_dict_item(self):
        """Test that a non-dict first item yields an empty dict."""
        assert first_response_item({"data": ["not-an-object"]}) == {}
