"""Regression tests for mutation confirmation, preview, and audit controls."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.diagnostics import run_speed_test
from src.tools.protect_devices import (
    update_protect_chime,
    update_protect_device,
    update_protect_light,
    update_protect_sensor,
)
from src.tools.protect_events import send_protect_alarm_webhook
from src.tools.protect_views import (
    create_protect_live_view,
    update_protect_live_view,
    update_protect_viewer,
)
from src.utils.exceptions import ValidationError

Mutation = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


@pytest.fixture
def settings() -> MagicMock:
    """Return settings sufficient for pre-request safety checks."""
    value = MagicMock()
    value.log_level = "INFO"
    value.get_protect_integration_path.side_effect = lambda endpoint: f"/protect/{endpoint}"
    return value


MUTATIONS: list[tuple[Mutation, dict[str, Any]]] = [
    (run_speed_test, {"site_id": "default"}),
    (update_protect_device, {"device_id": "device-1", "name": "Front Door"}),
    (update_protect_light, {"light_id": "light-1", "name": "Porch"}),
    (update_protect_sensor, {"sensor_id": "sensor-1", "name": "Garage"}),
    (update_protect_chime, {"chime_id": "chime-1", "name": "Hall"}),
    (update_protect_viewer, {"viewer_id": "viewer-1", "name": "Lobby"}),
    (create_protect_live_view, {"live_view": {"name": "Operations", "slots": []}}),
    (update_protect_live_view, {"live_view_id": "view-1", "name": "Operations"}),
    (send_protect_alarm_webhook, {"webhook_id": "webhook-1", "payload": {"alarm": True}}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("mutation", "kwargs"), MUTATIONS)
async def test_mutation_requires_confirmation_before_client_creation(
    mutation: Mutation, kwargs: dict[str, Any], settings: MagicMock
) -> None:
    """Every affected mutation must reject an unconfirmed call before I/O."""
    client_name = "UniFiClient" if mutation is run_speed_test else "ProtectClient"

    with patch(f"{mutation.__module__}.{client_name}") as client_class:
        with pytest.raises(ValidationError, match="confirmation"):
            await mutation(settings=settings, confirm=False, **kwargs)

    client_class.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("mutation", "kwargs"), MUTATIONS)
async def test_mutation_dry_run_is_side_effect_free_and_audited(
    mutation: Mutation, kwargs: dict[str, Any], settings: MagicMock
) -> None:
    """Every affected mutation must provide an audited no-I/O preview."""
    client_name = "UniFiClient" if mutation is run_speed_test else "ProtectClient"

    with (
        patch(f"{mutation.__module__}.{client_name}") as client_class,
        patch(f"{mutation.__module__}.log_audit") as audit,
    ):
        result = await mutation(settings=settings, dry_run=True, **kwargs)

    assert result["dry_run"] is True
    client_class.assert_not_called()
    audit.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(("mutation", "kwargs"), MUTATIONS)
async def test_mutation_failure_is_audited(
    mutation: Mutation, kwargs: dict[str, Any], settings: MagicMock
) -> None:
    """Every attempted mutation must leave an audit record when execution fails."""
    client_name = "UniFiClient" if mutation is run_speed_test else "ProtectClient"
    client = MagicMock()
    client.__aenter__ = AsyncMock(side_effect=RuntimeError("simulated API failure"))

    with (
        patch(f"{mutation.__module__}.{client_name}", return_value=client),
        patch(f"{mutation.__module__}.log_audit") as direct_audit,
        patch("src.utils.audit.log_audit") as shared_audit,
    ):
        with pytest.raises(RuntimeError, match="simulated API failure"):
            await mutation(settings=settings, confirm=True, **kwargs)

    audit = direct_audit if mutation is run_speed_test else shared_audit
    audit.assert_called_once()
    assert audit.call_args.kwargs["result"] == "failed"
