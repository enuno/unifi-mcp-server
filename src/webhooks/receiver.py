"""Webhook receiver for UniFi events.

This module provides a webhook receiver that listens for UniFi events
and processes them asynchronously. It includes signature verification,
event validation, and rate limiting.
"""

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, validator

from ..config import Settings
from ..utils import get_logger


class WebhookEvent(BaseModel):
    """UniFi webhook event model."""

    event_type: str = Field(..., description="Event type (e.g., device.online)")
    timestamp: datetime = Field(..., description="Event timestamp")
    site_id: str = Field(..., description="Site identifier")
    data: dict[str, Any] = Field(..., description="Event data")
    event_id: str | None = Field(None, description="Unique event identifier")

    @validator("event_type")
    def validate_event_type(cls, v):
        """Validate event type format."""
        if not v or "." not in v:
            raise ValueError("Event type must be in format 'category.action'")
        return v.lower()


class WebhookReceiver:
    """Webhook receiver for UniFi events."""

    def __init__(
        self,
        settings: Settings,
        app: FastAPI | None = None,
        path: str = "/webhooks/unifi",
    ):
        """Initialize webhook receiver.

        Args:
            settings: Application settings
            app: Optional FastAPI app instance
            path: Webhook endpoint path
        """
        self.settings = settings
        self.path = path
        self.logger = get_logger(__name__, settings.log_level)
        self.handlers: dict[str, list[Callable]] = {}
        self._event_cache: dict[str, datetime] = {}
        self._rate_limit_cache: dict[str, list[datetime]] = {}

        # Get webhook secret from settings
        self.webhook_secret = getattr(settings, "webhook_secret", None)
        if not self.webhook_secret:
            self.logger.warning(
                "WEBHOOK_SECRET not configured. Signature verification disabled. "
                "Set WEBHOOK_SECRET environment variable for production use."
            )

        if app:
            self.register_routes(app)

    def register_routes(self, app: FastAPI) -> None:
        """Register webhook routes with FastAPI app.

        Args:
            app: FastAPI application instance
        """

        @app.post(self.path)
        async def receive_webhook(
            request: Request,
            x_unifi_signature: str | None = Header(None),
        ):
            """Receive and process UniFi webhook."""
            try:
                # Get request body
                body = await request.body()
                body_str = body.decode("utf-8")

                # Verify signature if secret is configured
                if self.webhook_secret and x_unifi_signature:
                    if not self._verify_signature(body_str, x_unifi_signature):
                        self.logger.warning("Invalid webhook signature")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid signature",
                        )
                elif self.webhook_secret and not x_unifi_signature:
                    self.logger.warning("Missing webhook signature")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Missing signature",
                    )

                # Parse event
                event_data = json.loads(body_str)
                event = WebhookEvent(**event_data)

                # Check for duplicate events
                if self._is_duplicate(event):
                    self.logger.debug(f"Ignoring duplicate event: {event.event_id}")
                    return {"status": "duplicate", "event_id": event.event_id}

                # Rate limiting check
                if not self._check_rate_limit(event.site_id):
                    self.logger.warning(f"Rate limit exceeded for site: {event.site_id}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded",
                    )

                # Process event
                await self._process_event(event)

                return {
                    "status": "success",
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                }

            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON in webhook payload: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON payload",
                ) from e
            except ValueError as e:
                self.logger.error(f"Invalid webhook event: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                ) from e
            except Exception as e:
                self.logger.error(f"Error processing webhook: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error",
                ) from e

        self.logger.info(f"Webhook receiver registered at {self.path}")

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
