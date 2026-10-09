"""Lightweight Prometheus-style metrics for the UniFi MCP Server.

Zero-dependency implementation of the Prometheus text exposition format
(``text/plain; version=0.0.4``), so the server can expose a ``/metrics``
endpoint for scraping without taking on a ``prometheus_client`` dependency.
Counters live for the process lifetime; collection is pull-based, so an
unscraped server pays only the (tiny) recording cost.

Instrumented at the single choke point every registered tool passes
through — :func:`src.tool_registry._make_tool_wrapper` — so coverage cannot
drift as new tool modules are added.
"""

from __future__ import annotations

import threading
import time

#: Duration histogram buckets in seconds. A tool call that lands in the
#: smallest bucket covers sub-100ms controller answers; the +Inf bucket is
#: implicit (its count equals ``_count`` and is not emitted separately).
_DURATION_BUCKETS: tuple[float, ...] = (0.1, 0.5, 1.0, 5.0, 10.0)

#: Process start, exported as ``unifi_mcp_process_start_time_seconds`` so
#: Prometheus can derive uptime without a restart counter.
PROCESS_START_TIME = time.time()


def _escape_label(value: str) -> str:
    """Escape a string for use as a Prometheus label value."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class MetricsRegistry:
    """In-process counters rendered as Prometheus text exposition.

    All mutations take an internal lock; recording happens on every tool
    call, and MCP servers can be driven from multiple asyncio tasks. Reads
    (``render``) copy under the same lock, so a scrape sees a consistent
    snapshot rather than a torn one.
    """

    def __init__(self) -> None:
        """Create an empty registry (thread-safe, process-lifetime data)."""
        self._lock = threading.Lock()
        self._tool_calls: dict[tuple[str, str], int] = {}
        self._duration_sum: dict[str, float] = {}
        self._duration_count: dict[str, int] = {}
        # One bucket-count list per tool, aligned with _DURATION_BUCKETS.
        self._duration_buckets: dict[str, list[int]] = {}
        self._registered_tools = 0

    def note_tool_registered(self, count: int = 1) -> None:
        """Record *count* tools registered on the server.

        Args:
            count: How many tool registrations to add (default 1)
        """
        with self._lock:
            self._registered_tools += count

    def record_tool_call(self, tool: str, status: str, duration: float) -> None:
        """Record one completed tool call.

        Args:
            tool: Public MCP tool name (used as the ``tool`` label)
            status: ``"success"`` or ``"error"`` (any exception)
            duration: Wall-clock seconds; negative values are clamped to 0
                as a defensive measure against clock artifacts
        """
        duration = max(duration, 0.0)
        with self._lock:
            key = (tool, status)
            self._tool_calls[key] = self._tool_calls.get(key, 0) + 1
            self._duration_sum[tool] = self._duration_sum.get(tool, 0.0) + duration
            self._duration_count[tool] = self._duration_count.get(tool, 0) + 1
            buckets = self._duration_buckets.setdefault(tool, [0] * len(_DURATION_BUCKETS))
            for index, boundary in enumerate(_DURATION_BUCKETS):
                if duration <= boundary:
                    buckets[index] += 1

    def render(self, *, version: str, api_type: str) -> str:
        """Render the registry in Prometheus text exposition format.

        Args:
            version: Server version for the ``unifi_mcp_server_info`` metric
            api_type: ``cloud-v1`` / ``cloud-ea`` / ``local`` info label

        Returns:
            Text body suitable for ``text/plain; version=0.0.4`` responses,
            always terminated by a trailing newline
        """
        lines: list[str] = []

        lines.append("# HELP unifi_mcp_server_info Server identity.")
        lines.append("# TYPE unifi_mcp_server_info gauge")
        escaped_version = _escape_label(version)
        escaped_api_type = _escape_label(api_type)
        lines.append(
            f'unifi_mcp_server_info{{version="{escaped_version}",api_type="{escaped_api_type}"}} 1'
        )

        lines.append(
            "# HELP unifi_mcp_process_start_time_seconds Process start time (unix seconds)."
        )
        lines.append("# TYPE unifi_mcp_process_start_time_seconds gauge")
        lines.append(f"unifi_mcp_process_start_time_seconds {PROCESS_START_TIME:.3f}")

        with self._lock:
            registered = self._registered_tools
            tool_calls = dict(self._tool_calls)
            duration_sum = dict(self._duration_sum)
            duration_count = dict(self._duration_count)
            duration_buckets = {tool: list(b) for tool, b in self._duration_buckets.items()}

        lines.append("# HELP unifi_mcp_tools_registered Tools registered on the server.")
        lines.append("# TYPE unifi_mcp_tools_registered gauge")
        lines.append(f"unifi_mcp_tools_registered {registered}")

        if tool_calls:
            lines.append(
                "# HELP unifi_mcp_tool_calls_total Completed tool calls by tool and status."
            )
            lines.append("# TYPE unifi_mcp_tool_calls_total counter")
            for (tool, status), count in sorted(tool_calls.items()):
                lines.append(
                    f'unifi_mcp_tool_calls_total{{tool="{_escape_label(tool)}",'
                    f'status="{_escape_label(status)}"}} {count}'
                )

        if duration_count:
            lines.append(
                "# HELP unifi_mcp_tool_call_duration_seconds Tool call wall-clock duration."
            )
            lines.append("# TYPE unifi_mcp_tool_call_duration_seconds histogram")
            for tool in sorted(duration_count):
                escaped_tool = _escape_label(tool)
                for index, boundary in enumerate(_DURATION_BUCKETS):
                    lines.append(
                        f'unifi_mcp_tool_call_duration_seconds_bucket{{tool="{escaped_tool}",'
                        f'le="{boundary:g}"}} {duration_buckets[tool][index]}'
                    )
                lines.append(
                    f'unifi_mcp_tool_call_duration_seconds_sum{{tool="{escaped_tool}"}} '
                    f"{duration_sum[tool]:g}"
                )
                lines.append(
                    f'unifi_mcp_tool_call_duration_seconds_count{{tool="{escaped_tool}"}} '
                    f"{duration_count[tool]}"
                )

        return "\n".join(lines) + "\n"


#: Process-wide registry shared by the tool wrapper and the /metrics route.
REGISTRY = MetricsRegistry()
