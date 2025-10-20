"""Redis-based caching for UniFi MCP Server.

This module provides caching capabilities to reduce API calls and improve performance.
Supports configurable TTL per resource type and graceful degradation if Redis is unavailable.
"""

import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

try:
    import redis.asyncio as redis  # type: ignore[import-untyped]
    from redis.asyncio import Redis  # type: ignore[import-untyped]
    from redis.exceptions import RedisError  # type: ignore[import-untyped]

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None  # type: ignore[assignment]
    RedisError = Exception  # type: ignore[assignment]

from .config import Settings
from .utils import get_logger


class CacheConfig:
    """Cache TTL configuration for different resource types."""

    # Default TTLs in seconds
    SITES: int = 300  # 5 minutes - sites change rarely
    DEVICES: int = 60  # 1 minute - devices change occasionally
    CLIENTS: int = 30  # 30 seconds - clients connect/disconnect frequently
    NETWORKS: int = 300  # 5 minutes - networks change rarely
    WLANS: int = 300  # 5 minutes - WLANs change rarely
    FIREWALL_RULES: int = 300  # 5 minutes - firewall rules change rarely
    PORT_FORWARDS: int = 300  # 5 minutes - port forwards change rarely
    DPI_STATS: int = 120  # 2 minutes - DPI stats update frequently
    TOPOLOGY: int = 60  # 1 minute - topology can change
    ALERTS: int = 30  # 30 seconds - alerts are time-sensitive
    EVENTS: int = 30  # 30 seconds - events are time-sensitive

    @classmethod
    def get_ttl(cls, resource_type: str) -> int:
        """Get TTL for a resource type.

        Args:
            resource_type: Resource type (sites, devices, clients, etc.)

        Returns:
            TTL in seconds
        """
        return getattr(cls, resource_type.upper(), 60)


class CacheClient:
    """Async Redis cache client with graceful degradation."""

    def __init__(
        self,
        settings: Settings,
        enabled: bool = True,
        logger: logging.Logger | None = None,
    ):
        """Initialize cache client.

        Args:
            settings: Application settings
            enabled: Enable/disable caching
            logger: Optional logger instance
        """
        self.settings = settings
        self.enabled = enabled and REDIS_AVAILABLE
        self.logger = logger or get_logger(__name__, settings.log_level)
        self._redis: Redis | None = None
        self._connected = False

        if not REDIS_AVAILABLE and enabled:
            self.logger.warning(
                "Redis not available (redis package not installed). "
                "Caching is disabled. Install with: pip install redis"
            )
            self.enabled = False

    async def connect(self) -> bool:
        """Connect to Redis.

        Returns:
            True if connected successfully, False otherwise
        """
        if not self.enabled:
            return False

        if self._connected and self._redis:
            return True

        try:
            # Get Redis settings from environment or use defaults
            redis_host = getattr(self.settings, "redis_host", "localhost")
            redis_port = getattr(self.settings, "redis_port", 6379)
            redis_db = getattr(self.settings, "redis_db", 0)
            redis_password = getattr(self.settings, "redis_password", None)

            self._redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )

            # Test connection
            await self._redis.ping()
            self._connected = True
            self.logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
            return True

        except Exception as e:
            self.logger.warning(
                f"Failed to connect to Redis: {e}. Caching disabled for this session."
            )
            self._redis = None
            self._connected = False
            self.enabled = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            try:
                await self._redis.aclose()
                self.logger.info("Disconnected from Redis")
            except Exception as e:
                self.logger.error(f"Error disconnecting from Redis: {e}")
            finally:
                self._redis = None
                self._connected = False

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/error
        """
        if not self.enabled or not self._redis:
            return None

        try:
            value = await self._redis.get(key)
            if value:
                self.logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            else:
                self.logger.debug(f"Cache MISS: {key}")
                return None
        except (RedisError, json.JSONDecodeError) as e:
            self.logger.error(f"Cache get error for key '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self._redis:
            return False

        try:
            serialized = json.dumps(value)
            if ttl:
                await self._redis.setex(key, ttl, serialized)
            else:
                await self._redis.set(key, serialized)
            self.logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except (RedisError, TypeError, ValueError) as e:
            self.logger.error(f"Cache set error for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        if not self.enabled or not self._redis:
            return False

        try:
            result = await self._redis.delete(key)
            if result:
                self.logger.debug(f"Cache DELETE: {key}")
            return bool(result)
        except RedisError as e:
            self.logger.error(f"Cache delete error for key '{key}': {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "sites:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self._redis:
            return 0

        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted: int = await self._redis.delete(*keys)
                self.logger.debug(f"Cache DELETE pattern '{pattern}': {deleted} keys")
                return deleted
            return 0
        except RedisError as e:
            self.logger.error(f"Cache delete pattern error for '{pattern}': {e}")
            return 0

    async def clear(self) -> bool:
        """Clear all cache data.

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self._redis:
            return False

        try:
            await self._redis.flushdb()
            self.logger.info("Cache CLEARED")
            return True
        except RedisError as e:
            self.logger.error(f"Cache clear error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        if not self.enabled or not self._redis:
            return False

        try:
            return bool(await self._redis.exists(key))
        except RedisError as e:
            self.logger.error(f"Cache exists error for key '{key}': {e}")
            return False

    def build_key(
        self,
        resource_type: str,
        site_id: str | None = None,
        resource_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Build a cache key.

        Args:
            resource_type: Type of resource (sites, devices, clients, etc.)
            site_id: Optional site identifier
            resource_id: Optional resource identifier
            **kwargs: Additional key components

        Returns:
            Cache key string
        """
        parts = [resource_type]

        if site_id:
            parts.append(site_id)

        if resource_id:
            parts.append(resource_id)

        # Add additional components
        for key, value in sorted(kwargs.items()):
            if value is not None:
                parts.append(f"{key}:{value}")

        return ":".join(parts)


def cached(
    resource_type: str,
    ttl: int | None = None,
    key_builder: Callable[..., str] | None = None,
) -> Callable[[Callable], Callable]:
    """Decorator for caching function results.

    Args:
        resource_type: Type of resource being cached
        ttl: Time to live in seconds (uses CacheConfig if not specified)
        key_builder: Optional custom key builder function

    Example:
        @cached(resource_type="sites", ttl=300)
        async def get_sites(settings: Settings):
            # Function implementation
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract settings from arguments
            settings = None
            for arg in args:
                if isinstance(arg, Settings):
                    settings = arg
                    break
            if not settings and "settings" in kwargs:
                settings = kwargs["settings"]

            if not settings:
                # No settings, can't use cache - call function directly
                return await func(*args, **kwargs)

            # Initialize cache client
            cache = CacheClient(settings)
            await cache.connect()

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key builder using function name and args
                key_parts = [resource_type, func.__name__]
                # Add site_id if present in kwargs
                if "site_id" in kwargs:
                    key_parts.append(kwargs["site_id"])
                cache_key = ":".join(str(p) for p in key_parts if p)

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                await cache.disconnect()
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            cache_ttl = ttl if ttl is not None else CacheConfig.get_ttl(resource_type)
            await cache.set(cache_key, result, ttl=cache_ttl)
            await cache.disconnect()

            return result

        return wrapper

    return decorator


async def warm_cache(settings: Settings) -> dict[str, int]:
    """Pre-populate cache with frequently accessed data.

    Args:
        settings: Application settings

    Returns:
        Dictionary with counts of warmed cache entries per resource type
    """
    from .api import UniFiClient

    logger = get_logger(__name__, settings.log_level)
    cache = CacheClient(settings)

    if not await cache.connect():
        logger.warning("Cache warming skipped - Redis not available")
        return {}

    warmed = {"sites": 0, "devices": 0, "networks": 0}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Warm sites cache
            try:
                response = await client.get("/ea/sites")
                sites = response.get("data", [])
                for site in sites:
                    site_id = site.get("id")
                    if site_id:
                        key = cache.build_key("sites", resource_id=site_id)
                        await cache.set(key, site, ttl=CacheConfig.SITES)
                        warmed["sites"] += 1
                logger.info(f"Warmed cache for {warmed['sites']} sites")
            except Exception as e:
                logger.error(f"Failed to warm sites cache: {e}")

            # Warm devices cache for each site
            for site in sites:
                site_id = site.get("id")
                if not site_id:
                    continue

                try:
                    response = await client.get(f"/ea/sites/{site_id}/devices")
                    devices = response.get("data", [])
                    key = cache.build_key("devices", site_id=site_id)
                    await cache.set(key, devices, ttl=CacheConfig.DEVICES)
                    warmed["devices"] += len(devices)
                except Exception as e:
                    logger.error(f"Failed to warm devices cache for site {site_id}: {e}")

            logger.info(f"Cache warming complete: {warmed}")

    except Exception as e:
        logger.error(f"Cache warming failed: {e}")

    finally:
        await cache.disconnect()

    return warmed


async def invalidate_cache(
    settings: Settings,
    resource_type: str | None = None,
    site_id: str | None = None,
) -> int:
    """Invalidate cache entries.

    Args:
        settings: Application settings
        resource_type: Optional resource type to invalidate (all if not specified)
        site_id: Optional site ID to invalidate (all sites if not specified)

    Returns:
        Number of cache entries invalidated
    """
    logger = get_logger(__name__, settings.log_level)
    cache = CacheClient(settings)

    if not await cache.connect():
        logger.warning("Cache invalidation skipped - Redis not available")
        return 0

    try:
        if resource_type and site_id:
            pattern = f"{resource_type}:{site_id}:*"
        elif resource_type:
            pattern = f"{resource_type}:*"
        elif site_id:
            pattern = f"*:{site_id}:*"
        else:
            # Clear all
            await cache.clear()
            logger.info("Invalidated all cache entries")
            return -1  # Unknown count

        deleted = await cache.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted} cache entries (pattern: {pattern})")
        return deleted

    finally:
        await cache.disconnect()
