"""Default webhook handlers clear the server's read cache on state changes.

A webhook payload does not say which controller sent it, so every
controller's cached reads are cleared: exact for one controller, and only
extra cache misses (never stale reads) in a fleet.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.webhooks.handlers import WebhookEventHandler
from src.webhooks.receiver import WebhookEvent

STATE_CHANGES = ["device.online", "device.offline", "client.connected", "client.disconnected"]
INFORMATIONAL = ["alert.raised", "event.occurred"]


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    return settings


def _event(event_type: str) -> WebhookEvent:
    return WebhookEvent(
        event_type=event_type,
        timestamp=datetime(2026, 10, 10),
        site_id="default",
        data={"mac": "00:11:22:33:44:55"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", STATE_CHANGES)
async def test_state_changes_clear_the_read_cache(event_type: str) -> None:
    read_cache = MagicMock()
    read_cache.invalidate_all = AsyncMock()
    handlers = WebhookEventHandler(_settings(), read_cache=read_cache).get_default_handlers()

    await handlers[event_type](_event(event_type))

    read_cache.invalidate_all.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", INFORMATIONAL)
async def test_informational_events_keep_the_cache(event_type: str) -> None:
    read_cache = MagicMock()
    read_cache.invalidate_all = AsyncMock()
    handlers = WebhookEventHandler(_settings(), read_cache=read_cache).get_default_handlers()

    await handlers[event_type](_event(event_type))

    read_cache.invalidate_all.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", STATE_CHANGES)
async def test_without_a_read_cache_nothing_touches_redis(event_type: str) -> None:
    # The legacy invalidate_cache() dialed localhost:6379 on every event even
    # when Redis was not configured.
    handlers = WebhookEventHandler(_settings()).get_default_handlers()

    with patch("src.cache.CacheClient") as legacy_client:
        await handlers[event_type](_event(event_type))

    legacy_client.assert_not_called()
