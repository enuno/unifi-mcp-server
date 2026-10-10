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


def test_duration_histogram_has_inf_bucket_equal_to_count() -> None:
    registry = MetricsRegistry()
    _record(registry, "get_device", "success", 0.05)
    _record(registry, "get_device", "success", 7.0)
    _record(registry, "get_device", "error", 60.0)  # above the largest finite bucket

    lines = registry.render(version="0.5.0", api_type="local").splitlines()
    prefix = "unifi_mcp_tool_call_duration_seconds"
    buckets = [line for line in lines if line.startswith(f"{prefix}_bucket")]

    # the finite buckets do not include the 60s call; +Inf does, and it comes last
    assert buckets[-2] == f'{prefix}_bucket{{tool="get_device",le="10"}} 2'
    assert buckets[-1] == f'{prefix}_bucket{{tool="get_device",le="+Inf"}} 3'
    assert f'{prefix}_count{{tool="get_device"}} 3' in lines
    # +Inf must be the last bucket before _sum and _count
    assert lines.index(buckets[-1]) + 1 == lines.index(f'{prefix}_sum{{tool="get_device"}} 67.05')


def test_inf_bucket_is_emitted_for_every_tool() -> None:
    registry = MetricsRegistry()
    _record(registry, "tool_a", "success", 0.01)
    _record(registry, "tool_b", "success", 0.01, times=4)

    body = registry.render(version="0.5.0", api_type="local")

    assert 'unifi_mcp_tool_call_duration_seconds_bucket{tool="tool_a",le="+Inf"} 1' in body
    assert 'unifi_mcp_tool_call_duration_seconds_bucket{tool="tool_b",le="+Inf"} 4' in body


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

    assert body.count("tool_b") == 9  # total + 5 buckets + +Inf bucket + sum + count
    new_body = registry.render(version="0.5.0", api_type="local")
    assert 'unifi_mcp_tool_calls_total{tool="tool_b",status="success"} 6' in new_body


def test_controller_calls_are_counted_per_controller() -> None:
    registry = MetricsRegistry()
    registry.record_controller_call("hq")
    registry.record_controller_call("hq")
    registry.record_controller_call("branch")

    body = registry.render(version="0.5.0", api_type="local")

    assert "# TYPE unifi_mcp_controller_calls_total counter" in body
    assert 'unifi_mcp_controller_calls_total{controller="hq"} 2' in body
    assert 'unifi_mcp_controller_calls_total{controller="branch"} 1' in body


def test_controller_label_cardinality_is_capped(monkeypatch) -> None:
    monkeypatch.setattr("src.utils.metrics.MAX_CONTROLLER_LABELS", 2)
    registry = MetricsRegistry()
    for name in ("a", "b", "c", "d", "a"):
        registry.record_controller_call(name)

    body = registry.render(version="0.5.0", api_type="local")

    assert 'unifi_mcp_controller_calls_total{controller="a"} 2' in body
    assert 'unifi_mcp_controller_calls_total{controller="other"} 2' in body
    assert 'controller="c"' not in body
