"""Webhook receiver for UniFi events.

This module provides a webhook receiver that listens for UniFi events
and processes them asynchronously. It includes signature verification,
event validation, and rate limiting.

The route is a plain Starlette endpoint, so it mounts on any app with
``add_route`` (Starlette, FastAPI, or the Starlette app behind FastMCP's HTTP
transport). It fails closed: without ``WEBHOOK_SECRET`` every request is
refused, and every request must carry a valid ``X-UniFi-Signature``.
"""

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import Settings
from ..utils import get_logger


class WebhookEvent(BaseModel):
    """UniFi webhook event model."""

    event_type: str = Field(..., description="Event type (e.g., device.online)")
    timestamp: datetime = Field(..., description="Event timestamp")
    site_id: str = Field(..., description="Site identifier")
    data: dict[str, Any] = Field(..., description="Event data")
    event_id: str | None = Field(None, description="Unique event identifier")

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Validate event type format."""
        if not v or "." not in v:
            raise ValueError("Event type must be in format 'category.action'")
        return v.lower()


class WebhookReceiver:
    """Webhook receiver for UniFi events."""

    def __init__(
        self,
        settings: Settings,
        app: Any | None = None,
        path: str = "/webhooks/unifi",
    ):
        """Initialize webhook receiver.

        Args:
            settings: Application settings
            app: Optional app to mount the route on (anything with ``add_route``)
            path: Webhook endpoint path
        """
        self.settings = settings
        self.path = path
        self.logger = get_logger(__name__, settings.log_level)
        self.handlers: dict[str, list[Callable]] = {}
        self._event_cache: dict[str, datetime] = {}
        self._rate_limit_cache: dict[str, list[datetime]] = {}

        secret = getattr(settings, "webhook_secret", None)
        if isinstance(secret, SecretStr):
            secret = secret.get_secret_value()
        self.webhook_secret: str | None = secret or None
        if not self.webhook_secret:
            self.logger.warning(
                "WEBHOOK_SECRET not configured: the webhook receiver will refuse every "
                "request. Set WEBHOOK_SECRET to accept signed UniFi webhooks."
            )

        if app is not None:
            self.register_routes(app)

    def register_routes(self, app: Any) -> None:
        """Mount the webhook endpoint (POST only) on an app.

        Args:
            app: A Starlette-compatible application exposing ``add_route``
        """
        app.add_route(self.path, self.handle_request, methods=["POST"])
        self.logger.info(f"Webhook receiver registered at {self.path}")

    async def handle_request(self, request: Request) -> JSONResponse:
        """Starlette endpoint: verify, parse and dispatch one webhook delivery."""
        body = await request.body()
        status_code, payload = await self.receive(body, request.headers.get("x-unifi-signature"))
        return JSONResponse(payload, status_code=status_code)

    async def receive(self, body: bytes, signature: str | None) -> tuple[int, dict[str, Any]]:
        """Verify and process a raw webhook delivery.

        Args:
            body: Raw request body
            signature: Value of the ``X-UniFi-Signature`` header, if any

        Returns:
            HTTP status code and JSON response body
        """
        if not self.webhook_secret:
            return 503, {"detail": "Webhook receiver is not configured"}
        if not signature:
            self.logger.warning("Missing webhook signature")
            return 401, {"detail": "Missing signature"}
        try:
            body_str = body.decode("utf-8")
        except UnicodeDecodeError:
            return 400, {"detail": "Webhook payload must be UTF-8"}
        if not self._verify_signature(body_str, signature):
            self.logger.warning("Invalid webhook signature")
            return 401, {"detail": "Invalid signature"}

        try:
            event_data = json.loads(body_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in webhook payload: {e}")
            return 400, {"detail": "Invalid JSON payload"}
        if not isinstance(event_data, dict):
            return 400, {"detail": "Webhook payload must be a JSON object"}
        try:
            event = WebhookEvent(**event_data)
        except ValidationError as e:
            fields = ", ".join(".".join(str(p) for p in err["loc"]) for err in e.errors())
            self.logger.error(f"Invalid webhook event: {fields}")
            return 400, {"detail": f"Invalid webhook event: {fields}"}

        if self._is_duplicate(event):
            self.logger.debug(f"Ignoring duplicate event: {event.event_id}")
            return 200, {"status": "duplicate", "event_id": event.event_id}

        if not self._check_rate_limit(event.site_id):
            self.logger.warning(f"Rate limit exceeded for site: {event.site_id}")
            return 429, {"detail": "Rate limit exceeded"}

        try:
            await self._process_event(event)
        except Exception as e:
            self.logger.error(f"Error processing webhook: {e}")
            return 500, {"detail": "Internal server error"}

        return 200, {
            "status": "success",
            "event_id": event.event_id,
            "event_type": event.event_type,
        }

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register an event handler.

        Args:
            event_type: Event type to handle (e.g., "device.online")
            handler: Async handler function
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []

        self.handlers[event_type].append(handler)
        self.logger.info(f"Registered handler for event type: {event_type}")

    def unregister_handler(self, event_type: str, handler: Callable) -> None:
        """Unregister an event handler.

        Args:
            event_type: Event type
            handler: Handler function to remove
        """
        if event_type in self.handlers:
            self.handlers[event_type].remove(handler)
            self.logger.info(f"Unregistered handler for event type: {event_type}")

    async def _process_event(self, event: WebhookEvent) -> None:
        """Process a webhook event.

        Args:
            event: Webhook event to process
        """
        self.logger.info(
            f"Processing webhook event: {event.event_type} "
            f"(site: {event.site_id}, id: {event.event_id})"
        )

        # Get handlers for this event type
        handlers = self.handlers.get(event.event_type, [])

        # Also get wildcard handlers (e.g., "device.*")
        event_category = event.event_type.split(".")[0]
        wildcard_handlers = self.handlers.get(f"{event_category}.*", [])

        all_handlers = handlers + wildcard_handlers

        if not all_handlers:
            self.logger.debug(f"No handlers registered for event type: {event.event_type}")
            return

        # Execute handlers
        for handler in all_handlers:
            try:
                await handler(event)
            except Exception as e:
                self.logger.error(
                    f"Error in handler for {event.event_type}: {e}",
                    exc_info=True,
                )

    def _verify_signature(self, payload: str, signature: str) -> bool:
        """Verify webhook signature.

        Args:
            payload: Request payload
            signature: Signature from X-UniFi-Signature header

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            return False

        expected_signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    def _is_duplicate(self, event: WebhookEvent) -> bool:
        """Check if event is a duplicate.

        Args:
            event: Webhook event

        Returns:
            True if duplicate, False otherwise
        """
        if not event.event_id:
            return False

        # Clean old cache entries (older than 5 minutes)
        cutoff = datetime.now() - timedelta(minutes=5)
        self._event_cache = {eid: ts for eid, ts in self._event_cache.items() if ts > cutoff}

        # Check if event ID exists
        if event.event_id in self._event_cache:
            return True

        # Add to cache
        self._event_cache[event.event_id] = datetime.now()
        return False

    def _check_rate_limit(
        self,
        site_id: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> bool:
        """Check rate limit for a site.

        Args:
            site_id: Site identifier
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds

        Returns:
            True if within rate limit, False otherwise
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=window_seconds)

        # Initialize or clean rate limit cache for this site
        if site_id not in self._rate_limit_cache:
            self._rate_limit_cache[site_id] = []

        # Remove old requests
        self._rate_limit_cache[site_id] = [
            ts for ts in self._rate_limit_cache[site_id] if ts > cutoff
        ]

        # Check limit
        if len(self._rate_limit_cache[site_id]) >= max_requests:
            return False

        # Add current request
        self._rate_limit_cache[site_id].append(now)
        return True
