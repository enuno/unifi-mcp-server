"""Confirmation and dry-run gates on the previously ungated write tools.

Nine tools issued a PATCH or POST with no confirmation gate at all — the four
Protect device writers, the three live-view/viewer writers, the alarm webhook,
and the speed test trigger. Every other mutating tool in the server requires
``confirm``; these did not, so nothing stood between a tool call and a write.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.tools import diagnostics, protect_devices, protect_events, protect_views
from src.utils.exceptions import ValidationError

# (module, tool name, client symbol to patch, required kwargs)
GATED_TOOLS = [
    (protect_devices, "update_protect_device", "ProtectClient", {"device_id": "device-1"}),
    (protect_devices, "update_protect_light", "ProtectClient", {"light_id": "light-1"}),
    (protect_devices, "update_protect_sensor", "ProtectClient", {"sensor_id": "sensor-1"}),
    (protect_devices, "update_protect_chime", "ProtectClient", {"chime_id": "chime-1"}),
    (protect_views, "update_protect_viewer", "ProtectClient", {"viewer_id": "viewer-1"}),
    (protect_views, "update_protect_live_view", "ProtectClient", {"live_view_id": "lv-1"}),
    (protect_views, "create_protect_live_view", "ProtectClient", {"live_view": {"name": "x"}}),
    (protect_events, "send_protect_alarm_webhook", "ProtectClient", {"webhook_id": "hook-1"}),
    (diagnostics, "run_speed_test", "UniFiClient", {"site_id": "default"}),
]

IDS = [f"{m.__name__.rsplit('.', 1)[-1]}.{n}" for m, n, _, _ in GATED_TOOLS]


@pytest.fixture
def settings():
    mock = MagicMock()
    mock.log_level = "INFO"
    mock.get_protect_integration_path = MagicMock(
        side_effect=lambda e: f"/integration/v1/{e.lstrip('/')}"
    )
    return mock


@pytest.mark.asyncio
@pytest.mark.parametrize(("module", "name", "client_symbol", "kwargs"), GATED_TOOLS, ids=IDS)
async def test_write_is_refused_without_confirm(module, name, client_symbol, kwargs, settings):
    """Calling without confirm raises and constructs no client."""
    tool = getattr(module, name)
    with patch.object(module, client_symbol) as client_cls:
        with pytest.raises(ValidationError):
            await tool(settings=settings, **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("module", "name", "client_symbol", "kwargs"), GATED_TOOLS, ids=IDS)
async def test_string_false_confirm_is_refused(module, name, client_symbol, kwargs, settings):
    """confirm="false" must not pass the gate.

    MCP clients serialise booleans as strings over JSON-RPC, and a bare
    truthiness check would let the string through — that is the shape of the
    bypass that has to stay impossible here.
    """
    tool = getattr(module, name)
    with patch.object(module, client_symbol) as client_cls:
        with pytest.raises(ValidationError):
            await tool(settings=settings, confirm="false", **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("module", "name", "client_symbol", "kwargs"), GATED_TOOLS, ids=IDS)
async def test_dry_run_performs_no_write(module, name, client_symbol, kwargs, settings):
    """dry_run returns a preview and issues no request."""
    tool = getattr(module, name)
    with patch.object(module, client_symbol) as client_cls:
        result = await tool(settings=settings, dry_run=True, **kwargs)
        client_cls.assert_not_called()

    assert result["dry_run"] is True
    assert result["operation"] == name


@pytest.mark.asyncio
@pytest.mark.parametrize(("module", "name", "client_symbol", "kwargs"), GATED_TOOLS, ids=IDS)
async def test_string_true_dry_run_performs_no_write(module, name, client_symbol, kwargs, settings):
    """dry_run="true" is honoured, matching coerce_bool semantics."""
    tool = getattr(module, name)
    with patch.object(module, client_symbol) as client_cls:
        result = await tool(settings=settings, dry_run="true", **kwargs)
        client_cls.assert_not_called()

    assert result["dry_run"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(("module", "name", "client_symbol", "kwargs"), GATED_TOOLS, ids=IDS)
async def test_dry_run_does_not_require_confirm(module, name, client_symbol, kwargs, settings):
    """A preview is not a mutation, so it needs no confirmation."""
    tool = getattr(module, name)
    with patch.object(module, client_symbol):
        result = await tool(settings=settings, dry_run=True, confirm=False, **kwargs)
    assert result["dry_run"] is True


def test_every_gated_tool_exposes_both_parameters():
    """The gate must stay visible in the public signature.

    Tooling that reasons about which tools mutate does so from the signature,
    so losing either parameter would silently make a write tool look like a
    read tool again.
    """
    for module, name, _, _ in GATED_TOOLS:
        tool = getattr(module, name)
        params = tool.__code__.co_varnames[: tool.__code__.co_argcount]
        assert "confirm" in params, f"{name} lost its confirm parameter"
        assert "dry_run" in params, f"{name} lost its dry_run parameter"
