"""Webhook event handlers for UniFi events.

This module provides example event handlers and a handler management class.
"""

import logging
from typing import Any, Callable

from ..config import Settings
from ..utils import get_logger
from .receiver import WebhookEvent


class WebhookEventHandler:
    """Manages webhook event handlers and provides common handlers."""

    def __init__(self, settings: Settings):
        """Initialize event handler.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

    async def handle_device_online(self, event: WebhookEvent) -> None:
        """Handle device online event.

        Args:
            event: Webhook event
        """
        device_mac = event.data.get("mac")
        device_name = event.data.get("name", "Unknown")

        self.logger.info(
            f"Device came online: {device_name} ({device_mac}) in site {event.site_id}"
        )

        # Example: Invalidate device cache
        from ..cache import invalidate_cache

        await invalidate_cache(
            self.settings,
            resource_type="devices",
            site_id=event.site_id,
        )

    async def handle_device_offline(self, event: WebhookEvent) -> None:
        """Handle device offline event.

        Args:
            event: Webhook event
        """
        device_mac = event.data.get("mac")
        device_name = event.data.get("name", "Unknown")

        self.logger.warning(
            f"Device went offline: {device_name} ({device_mac}) in site {event.site_id}"
        )

        # Example: Invalidate device cache
        from ..cache import invalidate_cache

        await invalidate_cache(
            self.settings,
            resource_type="devices",
            site_id=event.site_id,
        )

    async def handle_client_connected(self, event: WebhookEvent) -> None:
        """Handle client connected event.

        Args:
            event: Webhook event
        """
        client_mac = event.data.get("mac")
        client_name = event.data.get("hostname", "Unknown")
        ssid = event.data.get("essid", "N/A")

        self.logger.info(
            f"Client connected: {client_name} ({client_mac}) to {ssid} "
            f"in site {event.site_id}"
        )

        # Example: Invalidate clients cache
        from ..cache import invalidate_cache

        await invalidate_cache(
            self.settings,
            resource_type="clients",
            site_id=event.site_id,
        )

    async def handle_client_disconnected(self, event: WebhookEvent) -> None:
        """Handle client disconnected event.

        Args:
            event: Webhook event
        """
        client_mac = event.data.get("mac")
        client_name = event.data.get("hostname", "Unknown")

        self.logger.info(
            f"Client disconnected: {client_name} ({client_mac}) from site {event.site_id}"
        )

        # Example: Invalidate clients cache
        from ..cache import invalidate_cache

        await invalidate_cache(
            self.settings,
            resource_type="clients",
            site_id=event.site_id,
        )

    async def handle_alert_raised(self, event: WebhookEvent) -> None:
        """Handle alert raised event.

        Args:
            event: Webhook event
        """
        alert_type = event.data.get("type", "Unknown")
        alert_message = event.data.get("message", "")
        severity = event.data.get("severity", "info")

        self.logger.warning(
            f"Alert raised in site {event.site_id}: [{severity}] "
            f"{alert_type} - {alert_message}"
        )

        # Example: Could trigger notifications, update monitoring systems, etc.

    async def handle_event_occurred(self, event: WebhookEvent) -> None:
        """Handle generic event.

        Args:
            event: Webhook event
        """
        event_key = event.data.get("key", "unknown")
        event_msg = event.data.get("msg", "")

        self.logger.info(
            f"Event occurred in site {event.site_id}: {event_key} - {event_msg}"
        )

    async def handle_wildcard(self, event: WebhookEvent) -> None:
        """Handle any event (wildcard handler).

        Args:
            event: Webhook event
        """
        self.logger.debug(
            f"Wildcard handler received event: {event.event_type} from site {event.site_id}"
        )

    def get_default_handlers(self) -> dict[str, Callable]:
        """Get default event handlers mapping.

        Returns:
            Dictionary mapping event types to handler functions
        """
        return {
            "device.online": self.handle_device_online,
            "device.offline": self.handle_device_offline,
            "client.connected": self.handle_client_connected,
            "client.disconnected": self.handle_client_disconnected,
            "alert.raised": self.handle_alert_raised,
            "event.occurred": self.handle_event_occurred,
        }

    def register_default_handlers(self, receiver) -> None:
        """Register all default handlers with a webhook receiver.

        Args:
            receiver: WebhookReceiver instance
        """
        handlers = self.get_default_handlers()

        for event_type, handler in handlers.items():
            receiver.register_handler(event_type, handler)

        self.logger.info(f"Registered {len(handlers)} default webhook handlers")


# Example custom handler
async def custom_handler_example(event: WebhookEvent) -> None:
    """Example custom webhook handler.

    Args:
        event: Webhook event

    Example:
        receiver = WebhookReceiver(settings)
        receiver.register_handler("device.adopted", custom_handler_example)
    """
    print(f"Custom handler received event: {event.event_type}")
    print(f"Event data: {event.data}")
