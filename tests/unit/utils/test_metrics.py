"""Unit tests for the Prometheus text-exposition metrics registry."""

from __future__ import annotations

from src.utils.metrics import MetricsRegistry, _escape_label


def _record(
    registry: MetricsRegistry, tool: str, status: str, duration: float, times: int = 1
) -> None:
    for _ in range(times):
        registry.record_tool_call(tool, status, duration)


def test_render_includes_server_info_and_gauges() -> None:
    registry = MetricsRegistry()
    registry.note_tool_registered(3)

    body = registry.render(version="0.5.0", api_type="local")

    assert 'unifi_mcp_server_info{version="0.5.0",api_type="local"} 1' in body
    assert "unifi_mcp_process_start_time_seconds " in body
    assert "unifi_mcp_tools_registered 3" in body
    assert body.endswith("\n")


def test_render_escapes_label_values() -> None:
    registry = MetricsRegistry()
    _record(registry, 'weird"tool\\name', "success", 0.01)

    body = registry.render(version="0.5.0", api_type="local")

    assert 'tool="weird\\"tool\\\\name"' in body


def test_escape_label_handles_newlines() -> None:
    assert _escape_label("a\nb") == "a\\nb"


def test_tool_call_counters_by_status() -> None:
    registry = MetricsRegistry()
    _record(registry, "list_devices", "success", 0.05, times=3)
    _record(registry, "list_devices", "error", 0.2)

    body = registry.render(version="0.5.0", api_type="local")

    assert 'unifi_mcp_tool_calls_total{tool="list_devices",status="success"} 3' in body
    assert 'unifi_mcp_tool_calls_total{tool="list_devices",status="error"} 1' in body


def test_duration_histogram_buckets_are_cumulative() -> None:
    registry = MetricsRegistry()
    _record(registry, "get_device", "success", 0.05)  # lands in all 5 buckets
    _record(registry, "get_device", "success", 7.0)  # lands in 10.0 bucket only

    body = registry.render(version="0.5.0", api_type="local")

    # le=0.1: only the 0.05s call
    assert 'unifi_mcp_tool_call_duration_seconds_bucket{tool="get_device",le="0.1"} 1' in body
    # le=10: both calls
    assert 'unifi_mcp_tool_call_duration_seconds_bucket{tool="get_device",le="10"} 2' in body
    # sum/count aggregate both calls
    assert 'unifi_mcp_tool_call_duration_seconds_sum{tool="get_device"} 7.05' in body
    assert 'unifi_mcp_tool_call_duration_seconds_count{tool="get_device"} 2' in body


def test_negative_duration_is_clamped_to_zero() -> None:
    registry = MetricsRegistry()
    _record(registry, "tool_a", "success", -1.0)

    body = registry.render(version="0.5.0", api_type="local")

    assert 'unifi_mcp_tool_call_duration_seconds_sum{tool="tool_a"} 0' in body
    # clamped to 0 still lands in the smallest bucket
    assert 'unifi_mcp_tool_call_duration_seconds_bucket{tool="tool_a",le="0.1"} 1' in body


def test_render_with_no_data_is_valid() -> None:
    body = MetricsRegistry().render(version="0.5.0", api_type="cloud-ea")

    assert 'unifi_mcp_server_info{version="0.5.0",api_type="cloud-ea"} 1' in body
    assert "unifi_mcp_tool_calls_total" not in body
    assert "unifi_mcp_tool_call_duration_seconds_bucket" not in body


def test_snapshot_isolated_from_later_mutation() -> None:
    """A rendered body must not change when the registry is mutated afterwards."""
    registry = MetricsRegistry()
    _record(registry, "tool_b", "success", 0.1)
    body = registry.render(version="0.5.0", api_type="local")
    _record(registry, "tool_b", "success", 9.9, times=5)

    assert body.count("tool_b") == 8  # total + 5 buckets + sum + count
    new_body = registry.render(version="0.5.0", api_type="local")
    assert 'unifi_mcp_tool_calls_total{tool="tool_b",status="success"} 6' in new_body
