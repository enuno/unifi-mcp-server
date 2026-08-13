"""Hotspot voucher models.

The shape mirrors the documented Integration v1 voucher
(``/v1/sites/{siteId}/hotspot/vouchers``, docs/UNIFI_API.md): camelCase
keys, an integer ``code``, and no ``site_id``/``status``/``duration``/
``create_time`` at all. Only ``id`` is required — ``activatedAt`` is absent
until a voucher is first used, so nothing else can be counted on. Dump with
``exclude_none=True`` so an absent key means "not reported" rather than
"empty" (the convention settled in #103).
"""

from pydantic import BaseModel, ConfigDict, Field


class Voucher(BaseModel):
    """Hotspot voucher as the Integration v1 API reports it."""

    id: str = Field(..., description="Voucher ID (UUID)")

    created_at: str | None = Field(None, alias="createdAt", description="Creation timestamp")
    name: str | None = Field(None, description="Voucher note")
    code: int | str | None = Field(None, description="Voucher access code")

    authorized_guest_limit: int | None = Field(
        None, alias="authorizedGuestLimit", description="Max guests allowed on one voucher"
    )
    authorized_guest_count: int | None = Field(
        None, alias="authorizedGuestCount", description="Guests currently using the voucher"
    )

    activated_at: str | None = Field(
        None, alias="activatedAt", description="First-use timestamp; absent until used"
    )
    expires_at: str | None = Field(None, alias="expiresAt", description="Expiration timestamp")
    expired: bool | None = Field(None, description="Whether the voucher has expired")

    time_limit_minutes: int | None = Field(
        None, alias="timeLimitMinutes", description="Access duration in minutes"
    )
    data_usage_limit_mb: int | None = Field(
        None, alias="dataUsageLimitMBytes", description="Data usage limit in megabytes"
    )
    rx_rate_limit_kbps: int | None = Field(
        None, alias="rxRateLimitKbps", description="Download rate limit in kbps"
    )
    tx_rate_limit_kbps: int | None = Field(
        None, alias="txRateLimitKbps", description="Upload rate limit in kbps"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")
