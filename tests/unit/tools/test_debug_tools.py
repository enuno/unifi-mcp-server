"""Unit tests for the DEBUG-only debug_api_request passthrough."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tool_registry import register_module_tools, tool_tier
from src.tools import debug as debug_tools
from src.tools.debug import debug_api_request
from src.utils.exceptions import ValidationError


class FakeMCP:
    """Records the names registered through ``mcp.tool()``."""

    def __init__(self) -> None:
        self.registered: list[str] = []

    def tool(self) -> Any:
        def decorator(fn: Any) -> Any:
            self.registered.append(fn.__name__)
            return fn

        return decorator


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.read_only = False
    settings.dry_run = False
    return settings


@pytest.fixture
def client() -> Any:
    with patch("src.tools.debug.UniFiClient") as client_class:
        client = AsyncMock()
        client.get = AsyncMock(return_value={"ok": 1})
        client.delete = AsyncMock(return_value={"deleted": 1})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client_class.return_value = client
        yield client


def test_debug_tool_is_destructive() -> None:
    assert tool_tier(debug_api_request) == "destructive"


def test_read_only_mode_does_not_register_debug_tool(mock_settings: MagicMock) -> None:
    mock_settings.read_only = True
    mcp: Any = FakeMCP()

    registered = register_module_tools(mcp, debug_tools, mock_settings)

    assert registered == []
    assert "debug_api_request" not in mcp.registered


def test_default_mode_registers_debug_tool(mock_settings: MagicMock) -> None:
    mcp: Any = FakeMCP()

    assert register_module_tools(mcp, debug_tools, mock_settings) == ["debug_api_request"]


async def test_get_reaches_the_endpoint(mock_settings: MagicMock, client: Any) -> None:
    result = await debug_api_request("/proxy/network/api/s/default/stat/device", mock_settings)

    assert result == {"ok": 1}
    client.get.assert_awaited_once_with("/proxy/network/api/s/default/stat/device")
    client.delete.assert_not_awaited()


async def test_delete_requires_confirm(mock_settings: MagicMock, client: Any) -> None:
    with pytest.raises(ValidationError, match="requires confirmation"):
        await debug_api_request("/x", mock_settings, method="DELETE")

    with pytest.raises(ValidationError, match="requires confirmation"):
        await debug_api_request("/x", mock_settings, method="delete", confirm="false")

    client.delete.assert_not_awaited()


async def test_confirmed_delete_reaches_the_endpoint(mock_settings: MagicMock, client: Any) -> None:
    result = await debug_api_request("/x", mock_settings, method="delete", confirm=True)

    assert result == {"deleted": 1}
    client.delete.assert_awaited_once_with("/x")


async def test_dry_run_sends_nothing(mock_settings: MagicMock, client: Any) -> None:
    result = await debug_api_request("/x", mock_settings, method="DELETE", dry_run=True)

    assert result == {
        "dry_run": True,
        "operation": "debug_api_request",
        "method": "DELETE",
        "endpoint": "/x",
    }
    client.get.assert_not_awaited()
    client.delete.assert_not_awaited()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH"])
async def test_unsupported_method_is_refused(
    mock_settings: MagicMock, client: Any, method: str
) -> None:
    with pytest.raises(ValidationError, match="not supported"):
        await debug_api_request("/x", mock_settings, method=method, confirm=True)


async def test_empty_endpoint_is_refused(mock_settings: MagicMock, client: Any) -> None:
    with pytest.raises(ValidationError, match="endpoint"):
        await debug_api_request("  ", mock_settings)
