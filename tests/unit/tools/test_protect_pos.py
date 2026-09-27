"""Unit tests for UniFi Protect POS transaction tool (Protect v7 surface)."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_pos
from src.tools.protect_pos import ingest_pos_transaction
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.get_protect_integration_path = MagicMock(
        side_effect=lambda endpoint: f"/integration/v1/{endpoint.lstrip('/')}"
    )
    return settings


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


VALID_KWARGS = {
    "type": "sale",
    "external_id": "tx-123",
    "amount": 12.5,
    "location_id": "reg-1",
}


# --- Write gates ------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_refused_without_confirm(mock_settings, mock_client):
    with patch("src.tools.protect_pos.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await ingest_pos_transaction("cam-1", mock_settings, **VALID_KWARGS)
        client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_write_refused_with_string_false_confirm(mock_settings, mock_client):
    with patch("src.tools.protect_pos.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await ingest_pos_transaction(
                "cam-1", mock_settings, confirm="false", **VALID_KWARGS
            )
        client_cls.assert_not_called()


# --- Dry run ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_pos_transaction_dry_run(mock_settings, mock_client):
    before_ms = int(time.time() * 1000)
    with patch("src.tools.protect_pos.ProtectClient", return_value=mock_client):
        result = await ingest_pos_transaction(
            "cam-1",
            mock_settings,
            location_name="Register 1",
            currency="USD",
            line_items=[{"name": "Coffee", "price": 12.5}],
            payment_types=["card"],
            timestamp=before_ms,
            confirm=True,
            dry_run=True,
            **VALID_KWARGS,
        )
    assert result["dry_run"] is True
    assert result["operation"] == "ingest_pos_transaction"
    assert result["camera_id"] == "cam-1"
    payload = result["payload"]
    assert payload["type"] == "sale"
    assert payload["externalId"] == "tx-123"
    assert payload["amount"] == 12.5
    assert payload["currency"] == "USD"
    assert payload["lineItems"] == [{"name": "Coffee", "price": 12.5}]
    assert payload["location"] == {"id": "reg-1", "name": "Register 1"}
    assert payload["paymentTypes"] == ["card"]
    assert payload["timestamp"] == before_ms
    mock_client.post.assert_not_called()


# --- Execute ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_pos_transaction_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"accepted": True, "externalId": "tx-123"})
    timestamp = int(time.time() * 1000)
    with patch("src.tools.protect_pos.ProtectClient", return_value=mock_client):
        result = await ingest_pos_transaction(
            "cam-1",
            mock_settings,
            location_name="Register 1",
            currency="USD",
            payment_types=["cash"],
            timestamp=timestamp,
            confirm=True,
            **VALID_KWARGS,
        )
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/pos/cameras/cam-1/transactions",
        json_data={
            "type": "sale",
            "externalId": "tx-123",
            "amount": 12.5,
            "location": {"id": "reg-1", "name": "Register 1"},
            "currency": "USD",
            "paymentTypes": ["cash"],
            "timestamp": timestamp,
        },
    )
    assert result["accepted"] is True
    assert result["externalId"] == "tx-123"


# --- Input validation -------------------------------------------------------


@pytest.mark.asyncio
async def test_rejects_invalid_type(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await ingest_pos_transaction(
            "cam-1", mock_settings, confirm=True, type="exchange", **{
                k: v for k, v in VALID_KWARGS.items() if k != "type"
            }
        )


@pytest.mark.asyncio
async def test_rejects_non_positive_amount(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await ingest_pos_transaction(
            "cam-1", mock_settings, confirm=True, amount=0, **{
                k: v for k, v in VALID_KWARGS.items() if k != "amount"
            }
        )


@pytest.mark.asyncio
async def test_rejects_negative_amount(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await ingest_pos_transaction(
            "cam-1", mock_settings, confirm=True, amount=-1.5, **{
                k: v for k, v in VALID_KWARGS.items() if k != "amount"
            }
        )


@pytest.mark.asyncio
async def test_rejects_missing_location_id(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await ingest_pos_transaction(
            "cam-1", mock_settings, confirm=True, location_id="   ", **{
                k: v for k, v in VALID_KWARGS.items() if k != "location_id"
            }
        )


@pytest.mark.asyncio
async def test_rejects_bad_currency(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await ingest_pos_transaction(
            "cam-1", mock_settings, confirm=True, currency="usd", **VALID_KWARGS
        )
    with pytest.raises(ValidationError):
        await ingest_pos_transaction(
            "cam-1", mock_settings, confirm=True, currency="US", **VALID_KWARGS
        )


@pytest.mark.asyncio
async def test_rejects_stale_timestamp(mock_settings, mock_client):
    stale = int(time.time() * 1000) - 25 * 60 * 60 * 1000
    with pytest.raises(ValidationError):
        await ingest_pos_transaction(
            "cam-1", mock_settings, confirm=True, timestamp=stale, **VALID_KWARGS
        )


@pytest.mark.asyncio
async def test_rejects_far_future_timestamp(mock_settings, mock_client):
    future = int(time.time() * 1000) + 10 * 60 * 1000
    with pytest.raises(ValidationError):
        await ingest_pos_transaction(
            "cam-1", mock_settings, confirm=True, timestamp=future, **VALID_KWARGS
        )


@pytest.mark.asyncio
async def test_validation_happens_before_dry_run_return(mock_settings, mock_client):
    with patch("src.tools.protect_pos.ProtectClient", return_value=mock_client):
        with pytest.raises(ValidationError):
            await ingest_pos_transaction(
                "cam-1", mock_settings, confirm=True, dry_run=True,
                type="bogus", external_id="tx-1", amount=1, location_id="reg-1",
            )
        mock_client.post.assert_not_called()


# --- Module attribute access (parity with siren tests) ----------------------


def test_module_exposes_ingest_pos_transaction():
    assert protect_pos.ingest_pos_transaction is ingest_pos_transaction
