"""Shared fixtures for A2A unit tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp.resources.function_resource import FunctionResource
from fastmcp.tools.function_tool import FunctionTool

from src.config.config import Settings


class FakeProvider:
    """Stand-in for a FastMCP provider exposing a ``_components`` mapping."""

    def __init__(self, components: dict[str, Any]) -> None:
        self._components = components


class FakeMCP:
    """Minimal FastMCP stand-in exposing the attributes the A2A layer reads."""

    def __init__(self, components: dict[str, Any] | None = None, name: str = "Fake UniFi") -> None:
        self.providers = [FakeProvider(components or {})]
        self._mcp_server = type("Server", (), {"name": name})()


def make_tool(fn: Any, **kwargs: Any) -> FunctionTool:
    """Build a real ``FunctionTool`` so ``isinstance`` checks in src/ still hold."""
    return FunctionTool.from_function(fn, **kwargs)


def make_resource(fn: Any, uri: str, **kwargs: Any) -> FunctionResource:
    """Build a real ``FunctionResource`` for resource-discovery assertions."""
    return FunctionResource.from_function(fn, uri=uri, **kwargs)


def delete_site_device(site_id: str, confirm: bool = False) -> dict[str, Any]:
    """Delete a device from the site."""
    return {"ok": True}


def list_site_clients(site_id: str) -> dict[str, Any]:
    """List clients for a site."""
    return {"clients": []}


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Return Settings configured for local controller access."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.0.2.10")
    return Settings()


@pytest.fixture
def cloud_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Return Settings configured for cloud access."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
    return Settings()
