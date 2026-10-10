"""Redis-based caching for UniFi MCP Server.

This module provides caching capabilities to reduce API calls and improve performance.
Supports configurable TTL per resource type and graceful degradation if Redis is unavailable.
"""

import asyncio
import hashlib
import json
import logging
import weakref
from collections.abc import Callable
from functools import wraps
from typing import Any

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    from redis.exceptions import RedisError

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    # Placeholders; every use is guarded by REDIS_AVAILABLE.
    redis = None  # type: ignore[assignment, unused-ignore]
    Redis = None  # type: ignore[assignment, misc, unused-ignore]
    RedisError = Exception  # type: ignore[assignment, misc, unused-ignore]

from .config import Settings
from .utils import get_logger
from .utils.metrics import REGISTRY as METRICS

#: Connection pools shared by every CacheClient, one per event loop and Redis
#: location. ``@cached`` builds a CacheClient per call; sharing the pool keeps
#: that from opening a new TCP connection each time. Keyed by loop because an
#: asyncio connection must not be reused from a different loop, and weakly so a
#: closed loop's pools are dropped with it.
_pools: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[tuple[Any, ...], Any]]" = (
    weakref.WeakKeyDictionary()
)


def _shared_pool(settings: Settings) -> Any:
    """Return the connection pool for the configured Redis location.

    ``REDIS_URL`` takes precedence over the individual host/port/db/password
    settings.

    Args:
        settings: Application settings

    Returns:
        A ``redis.asyncio.ConnectionPool`` bound to the running event loop
    """
    pools = _pools.setdefault(asyncio.get_running_loop(), {})
    key: tuple[Any, ...]
    if settings.redis_url:
        key = ("url", settings.redis_url)
    else:
        key = (settings.redis_host, settings.redis_port, settings.redis_db, settings.redis_password)

    pool = pools.get(key)
    if pool is None:
        options: dict[str, Any] = {
            "decode_responses": True,
            "socket_timeout": 5.0,
            "socket_connect_timeout": 5.0,
        }
        if settings.redis_url:
            pool = redis.ConnectionPool.from_url(settings.redis_url, **options)
        else:
            pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                **options,
            )
        pools[key] = pool
    return pool


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
            self._redis = redis.Redis(connection_pool=_shared_pool(self.settings))

            # Test connection
            await self._redis.ping()
            self._connected = True
            # Never log REDIS_URL: it can carry the password.
            location = (
                "REDIS_URL"
                if self.settings.redis_url
                else f"{self.settings.redis_host}:{self.settings.redis_port}"
            )
            self.logger.info(f"Connected to Redis at {location}")
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
        """Disconnect from Redis, leaving the shared connection pool open."""
        if self._redis:
            try:
                await self._redis.aclose(close_connection_pool=False)
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


#: Tool modules whose read tools are cached, and the CacheConfig family that
#: sets their TTL. Statistics and RF-health tools are live metrics: never cached.
CACHED_MODULES = {
    "devices": "devices",
    "clients": "clients",
    "sites": "sites",
    "networks": "networks",
    "wifi": "wlans",
}

_UNCACHED_MARKERS = ("statistics", "rf_health")

#: Version segment of every read-cache key; bump to invalidate everything.
KEY_VERSION = "v1"


def cache_family(module: str, tool_name: str) -> str | None:
    """Return the cache family of a read tool, or None if it is not cached."""
    if any(marker in tool_name for marker in _UNCACHED_MARKERS):
        return None
    return CACHED_MODULES.get(module)


def redis_configured(settings: Settings) -> bool:
    """Whether Redis was configured explicitly (a local Redis is never used by accident)."""
    return bool(settings.redis_url) or "redis_host" in settings.model_fields_set


class ReadCache:
    """Read-through cache for read tools, shared across servers through Redis.

    Keys are ``unifi:v1:{controller}:{family}:{tool}:{args-hash}``. A
    successful or failed write to a controller deletes every key of that
    controller; TTLs (:class:`CacheConfig`) bound staleness for changes made
    outside this server. Redis errors bypass the cache; they never fail a call.
    Concurrent identical misses in one process share a single controller call.
    """

    def __init__(self, settings: Settings) -> None:
        """Create a cache over the configured Redis."""
        self._settings = settings
        self.logger = get_logger(__name__, settings.log_level)
        self._inflight: dict[str, asyncio.Task[Any]] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> "ReadCache | None":
        """Return a cache if caching is enabled and Redis is explicitly configured."""
        if not settings.cache_enabled or not redis_configured(settings):
            return None
        if not REDIS_AVAILABLE:
            get_logger(__name__).warning(
                "Redis is configured but the redis package is not installed; read caching is "
                "off. Install with: pip install 'unifi-mcp-server[fleet]'"
            )
            return None
        return cls(settings)

    def _redis(self) -> Any:
        return redis.Redis(connection_pool=_shared_pool(self._settings))

    @staticmethod
    def key(controller: str, family: str, tool: str, arguments: dict[str, Any]) -> str:
        """Build the key of one read."""
        digest = hashlib.sha256(
            json.dumps(arguments, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:32]
        return f"unifi:{KEY_VERSION}:{controller}:{family}:{tool}:{digest}"

    async def read_through(
        self, key: str, ttl: int, loader: Callable[[], Any], *, fresh: bool = False
    ) -> Any:
        """Return the cached value of ``key``, or load, cache and return it.

        Args:
            key: From :meth:`key`
            ttl: Seconds to keep a loaded value
            loader: Zero-argument coroutine function calling the tool
            fresh: Skip the cached value (the loaded one still replaces it)
        """
        if not fresh:
            cached = await self._get(key)
            if cached is not _MISS:
                METRICS.record_cache("hit")
                return cached
            inflight = self._inflight.get(key)
            if inflight is not None:
                METRICS.record_cache("hit")
                return await asyncio.shield(inflight)
        METRICS.record_cache("miss")
        task = asyncio.ensure_future(self._load_and_store(key, ttl, loader))
        if not fresh:
            self._inflight[key] = task
            task.add_done_callback(lambda _: self._inflight.pop(key, None))
        return await asyncio.shield(task)

    async def _load_and_store(self, key: str, ttl: int, loader: Callable[[], Any]) -> Any:
        value = await loader()
        try:
            serialized = json.dumps(value)
            cacheable = json.loads(serialized) == value
        except (TypeError, ValueError):
            cacheable = False
        if cacheable:
            try:
                await self._redis().setex(key, ttl, serialized)
            except RedisError as e:
                self.logger.warning(f"Read cache unavailable, not storing: {e}")
        return value

    async def _get(self, key: str) -> Any:
        try:
            raw = await self._redis().get(key)
        except RedisError as e:
            self.logger.warning(f"Read cache unavailable, reading from the controller: {e}")
            return _MISS
        return _MISS if raw is None else json.loads(raw)

    async def invalidate_controller(self, controller: str) -> None:
        """Delete every cached read of ``controller`` (after any write to it)."""
        try:
            client = self._redis()
            keys = [k async for k in client.scan_iter(match=f"unifi:{KEY_VERSION}:{controller}:*")]
            if keys:
                await client.delete(*keys)
        except RedisError as e:
            self.logger.error(
                f"Read cache invalidation for controller {controller} failed; cached reads may "
                f"be stale until they expire: {e}"
            )


_MISS = object()
