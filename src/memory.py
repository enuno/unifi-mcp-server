"""Supermemory-backed storage for operator notes and context.

Provides an optional store for notes/context that should persist across MCP
tool calls (e.g. operator annotations on network changes). Degrades
gracefully if the `supermemory` package is not installed or no API key is
configured.
"""

import logging
from typing import Any

try:
    from supermemory import AsyncSupermemory

    SUPERMEMORY_AVAILABLE = True
except ImportError:
    SUPERMEMORY_AVAILABLE = False
    AsyncSupermemory: Any = None

from .config import Settings
from .utils import get_logger


class MemoryClient:
    """Async Supermemory client with graceful degradation."""

    def __init__(self, settings: Settings, logger: logging.Logger | None = None):
        """Initialize memory client.

        Args:
            settings: Application settings
            logger: Optional logger instance
        """
        self.settings = settings
        self.logger = logger or get_logger(__name__, settings.log_level)
        self.enabled = settings.supermemory_enabled and bool(settings.supermemory_api_key)
        self._client: Any = None

        if settings.supermemory_enabled and not SUPERMEMORY_AVAILABLE:
            self.logger.warning(
                "Supermemory not available (supermemory package not installed). "
                "Memory storage is disabled. Install with: pip install supermemory"
            )
            self.enabled = False
        elif settings.supermemory_enabled and not settings.supermemory_api_key:
            self.logger.warning(
                "SUPERMEMORY_API_KEY not set. Memory storage is disabled."
            )
            self.enabled = False

        if self.enabled:
            self._client = AsyncSupermemory(api_key=settings.supermemory_api_key)

    async def remember(
        self,
        content: str,
        container_tag: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Store a note, scoped to a container tag (e.g. a site ID).

        Args:
            content: Note/context text to store
            container_tag: Identifier to scope the memory (e.g. site ID)
            metadata: Optional metadata to attach

        Returns:
            The stored document ID, or None if storage failed/disabled
        """
        if not self.enabled or not self._client:
            return None

        try:
            response = await self._client.documents.add(
                content=content,
                container_tag=container_tag,
                metadata=metadata or {},
            )
            return response.id
        except Exception as e:
            self.logger.error(f"Supermemory remember error: {e}")
            return None

    async def recall(
        self,
        query: str,
        container_tag: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search stored notes, scoped to a container tag.

        Args:
            query: Search query
            container_tag: Identifier to scope the search (e.g. site ID)
            limit: Maximum number of results to return

        Returns:
            List of matching memory results (empty if disabled/failed)
        """
        if not self.enabled or not self._client:
            return []

        try:
            response = await self._client.search.memories(
                q=query,
                container_tag=container_tag,
                limit=limit,
            )
            return [result.model_dump() for result in response.results]
        except Exception as e:
            self.logger.error(f"Supermemory recall error: {e}")
            return []
