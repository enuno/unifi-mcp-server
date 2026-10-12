"""Unit tests for src/memory.py (optional Supermemory-backed notes)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src import memory
from src.memory import MemoryClient


def _settings(
    enabled: bool = True, api_key: str | None = "sm-key"  # pragma: allowlist secret
) -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.supermemory_enabled = enabled
    settings.supermemory_api_key = api_key
    return settings


@pytest.fixture
def sdk() -> MagicMock:
    client = MagicMock()
    client.documents.add = AsyncMock()
    client.search.memories = AsyncMock()
    factory = MagicMock(return_value=client)
    with (
        patch.object(memory, "SUPERMEMORY_AVAILABLE", True),
        patch.object(memory, "AsyncSupermemory", factory),
    ):
        yield factory


class TestInit:
    def test_disabled_by_setting(self, sdk: MagicMock) -> None:
        client = MemoryClient(_settings(enabled=False))
        assert client.enabled is False
        sdk.assert_not_called()

    def test_missing_package(self) -> None:
        logger = MagicMock()
        with patch.object(memory, "SUPERMEMORY_AVAILABLE", False):
            client = MemoryClient(_settings(), logger=logger)

        assert client.enabled is False
        assert "not installed" in logger.warning.call_args.args[0]

    def test_missing_api_key(self, sdk: MagicMock) -> None:
        logger = MagicMock()
        client = MemoryClient(_settings(api_key=None), logger=logger)

        assert client.enabled is False
        assert "SUPERMEMORY_API_KEY" in logger.warning.call_args.args[0]
        sdk.assert_not_called()

    def test_enabled_builds_sdk_client(self, sdk: MagicMock) -> None:
        client = MemoryClient(_settings())

        assert client.enabled is True
        sdk.assert_called_once_with(api_key="sm-key")  # pragma: allowlist secret


class TestRemember:
    @pytest.mark.asyncio
    async def test_disabled_returns_none(self) -> None:
        assert await MemoryClient(_settings(enabled=False)).remember("n", "site") is None

    @pytest.mark.asyncio
    async def test_stores_scoped_note(self, sdk: MagicMock) -> None:
        sdk.return_value.documents.add.return_value = MagicMock(id="doc-1")
        client = MemoryClient(_settings())

        assert await client.remember("VLAN 30 moved", "default") == "doc-1"
        sdk.return_value.documents.add.assert_awaited_once_with(
            content="VLAN 30 moved", container_tag="default", metadata={}
        )

    @pytest.mark.asyncio
    async def test_error_returns_none(self, sdk: MagicMock) -> None:
        sdk.return_value.documents.add.side_effect = RuntimeError("quota")
        client = MemoryClient(_settings())

        assert await client.remember("n", "site", metadata={"by": "op"}) is None


class TestRecall:
    @pytest.mark.asyncio
    async def test_disabled_returns_empty(self) -> None:
        assert await MemoryClient(_settings(enabled=False)).recall("q", "site") == []

    @pytest.mark.asyncio
    async def test_returns_dumped_results(self, sdk: MagicMock) -> None:
        hit = MagicMock()
        hit.model_dump.return_value = {"memory": "VLAN 30 moved"}
        sdk.return_value.search.memories.return_value = MagicMock(results=[hit])
        client = MemoryClient(_settings())

        assert await client.recall("vlan", "default", limit=3) == [{"memory": "VLAN 30 moved"}]
        sdk.return_value.search.memories.assert_awaited_once_with(
            q="vlan", container_tag="default", limit=3
        )

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, sdk: MagicMock) -> None:
        sdk.return_value.search.memories.side_effect = RuntimeError("down")
        assert await MemoryClient(_settings()).recall("q", "site") == []
