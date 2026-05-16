"""Unit tests for data sanitization utilities."""

import os
from unittest.mock import patch

from src.utils.sanitize import (
    _redact_value,
    is_production,
    sanitize_dict,
    sanitize_for_logging,
    sanitize_list,
    sanitize_log_message,
    sanitize_sensitive_data,
)


class TestRedactValue:
    """Tests for _redact_value."""

    def test_none_returns_none_string(self):
        """None value returns 'None'."""
        assert _redact_value("ip", None) == "None"

    def test_mac_partial_redaction(self):
        """MAC address shows last octet."""
        result = _redact_value("mac", "AA:BB:CC:DD:EE:FF")
        assert result == "**:**:**:**:**:FF"

    def test_ip_partial_redaction(self):
        """IP address shows last octet."""
        result = _redact_value("ip", "192.168.1.100")
        assert result == "***.***.***.100"

    def test_short_value_full_redaction(self):
        """Values ≤4 chars are fully redacted."""
        assert _redact_value("password", "abc") == "***"

    def test_long_value_partial_redaction(self):
        """Longer values show last 2 chars."""
        assert _redact_value("password", "mysecretpass") == "***ss"

    def test_full_redaction_when_partial_false(self):
        """partial=False forces full redaction."""
        assert _redact_value("password", "mysecretpass", partial=False) == "***"

    def test_non_sensitive_key_not_in_partial_fields(self):
        """Key not in PARTIAL_REDACT_FIELDS gets standard redaction."""
        result = _redact_value("token", "abcdefghij")
        assert result == "***ij"


class TestSanitizeDict:
    """Tests for sanitize_dict."""

    def test_sensitive_fields_redacted(self):
        """Sensitive fields are redacted."""
        data = {"mac": "AA:BB:CC:DD:EE:FF", "name": "test-device"}
        result = sanitize_dict(data)
        assert "**" in result["mac"]
        assert "***" in result["name"]

    def test_non_sensitive_fields_preserved(self):
        """Non-sensitive fields pass through unchanged."""
        data = {"port": 8080, "enabled": True}
        result = sanitize_dict(data)
        assert result["port"] == 8080
        assert result["enabled"] is True

    def test_nested_dict_sanitized(self):
        """Nested dicts are sanitized recursively."""
        data = {"config": {"password": "secret123"}}
        result = sanitize_dict(data)
        assert "secret" not in result["config"]["password"]

    def test_list_values_sanitized(self):
        """List values containing dicts are sanitized."""
        data = {"clients": [{"mac": "AA:BB:CC:DD:EE:FF"}]}
        result = sanitize_dict(data)
        assert "**" in result["clients"][0]["mac"]

    def test_non_dict_input_returned_as_is(self):
        """Non-dict input is returned unchanged."""
        assert sanitize_dict("not a dict") == "not a dict"  # type: ignore[arg-type]

    def test_empty_dict(self):
        """Empty dict returns empty dict."""
        assert sanitize_dict({}) == {}


class TestSanitizeList:
    """Tests for sanitize_list."""

    def test_list_of_dicts_sanitized(self):
        """List of dicts gets each dict sanitized."""
        data = [{"mac": "AA:BB:CC:DD:EE:FF"}, {"port": 80}]
        result = sanitize_list(data)
        assert "**" in result[0]["mac"]
        assert result[1]["port"] == 80

    def test_non_dict_items_preserved(self):
        """Non-dict list items are not modified."""
        data = ["item1", 42, None]
        result = sanitize_list(data)
        assert result == ["item1", 42, None]

    def test_non_list_returned_as_is(self):
        """Non-list input is returned unchanged."""
        assert sanitize_list("not a list") == "not a list"  # type: ignore[arg-type]


class TestSanitizeLogMessage:
    """Tests for sanitize_log_message."""

    def test_mac_address_redacted(self):
        """MAC addresses in messages are redacted."""
        msg = "Client AA:BB:CC:DD:EE:FF connected"
        result = sanitize_log_message(msg)
        assert "AA:BB:CC:DD:EE:FF" not in result
        assert "**:**:**:**:**:" in result

    def test_ip_address_redacted(self):
        """IP addresses in messages are redacted."""
        msg = "Device at 192.168.1.50 is online"
        result = sanitize_log_message(msg)
        assert "192.168.1.50" not in result
        assert "***.***.***.50" in result

    def test_zero_ip_preserved(self):
        """0.0.0.0 is preserved as a wildcard address."""
        msg = "Binding to 0.0.0.0"
        result = sanitize_log_message(msg)
        assert "0.0.0.0" in result

    def test_context_appended(self):
        """Context dict is sanitized and appended."""
        result = sanitize_log_message("event", context={"port": 443})
        assert "Context:" in result
        assert "443" in result

    def test_no_context(self):
        """No context means no context suffix."""
        result = sanitize_log_message("plain message")
        assert "Context:" not in result


class TestIsProduction:
    """Tests for is_production."""

    def test_production_env(self):
        """Returns True when ENVIRONMENT=production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert is_production() is True

    def test_prod_shorthand(self):
        """Returns True when ENVIRONMENT=prod."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            assert is_production() is True

    def test_development_env(self):
        """Returns False for development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert is_production() is False

    def test_default_is_not_production(self):
        """Default ENVIRONMENT is development."""
        env = {k: v for k, v in os.environ.items() if k != "ENVIRONMENT"}
        with patch.dict(os.environ, env, clear=True):
            assert is_production() is False


class TestSanitizeForLogging:
    """Tests for sanitize_for_logging."""

    def test_dict_sanitized_in_production(self):
        """Dict is sanitized in production mode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            data = {"mac": "AA:BB:CC:DD:EE:FF"}
            result = sanitize_for_logging(data)
            assert isinstance(result, dict)
            assert "AA:BB:CC:DD:EE:FF" not in str(result)

    def test_list_sanitized_in_production(self):
        """List is sanitized in production mode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            data = [{"password": "secret"}]
            result = sanitize_for_logging(data)
            assert isinstance(result, list)
            assert "secret" not in str(result)

    def test_string_sanitized_in_production(self):
        """String is sanitized in production mode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            result = sanitize_for_logging("client 192.168.1.1 online")
            assert "192.168.1.1" not in str(result)

    def test_not_sanitized_in_development(self):
        """Data is returned as-is in development without force_sanitize."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            data = {"mac": "AA:BB:CC:DD:EE:FF"}
            result = sanitize_for_logging(data)
            assert result == data

    def test_force_sanitize_overrides_dev(self):
        """force_sanitize=True sanitizes even in development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            data = {"mac": "AA:BB:CC:DD:EE:FF"}
            result = sanitize_for_logging(data, force_sanitize=True)
            assert isinstance(result, dict)
            assert "AA:BB:CC:DD:EE:FF" not in str(result)


class TestSanitizeSensitiveData:
    """Tests for sanitize_sensitive_data (legacy alias)."""

    def test_dict_input(self):
        """Dict input is sanitized via sanitize_dict."""
        data = {"password": "secret"}
        result = sanitize_sensitive_data(data)
        assert isinstance(result, dict)
        assert "secret" not in str(result)

    def test_list_input(self):
        """List input is sanitized via sanitize_list."""
        data = [{"mac": "AA:BB:CC:DD:EE:FF"}]
        result = sanitize_sensitive_data(data)
        assert isinstance(result, list)

    def test_other_type_returned_as_is(self):
        """Non-dict, non-list input is returned unchanged."""
        result = sanitize_sensitive_data("plain string")  # type: ignore[arg-type]
        assert result == "plain string"
