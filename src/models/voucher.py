"""Hotspot voucher models."""

from datetime import datetime

from pydantic import BaseModel, Field


class Voucher(BaseModel):
    """Hotspot voucher model."""

    id: str = Field(..., alias="_id", description="Voucher identifier")
    site_id: str = Field(..., description="Site identifier")
    code: str = Field(..., description="Voucher code")

    # Usage status
    status: str = Field(..., description="Voucher status (unused/used/expired)")
    used: int = Field(0, description="Number of times used")
    quota: int = Field(1, description="Number of times voucher can be used")

    # Time configuration
    duration: int = Field(..., description="Duration in seconds")
    start_time: datetime | None = Field(None, description="When voucher was first used")
    end_time: datetime | None = Field(None, description="When voucher expires")
    create_time: datetime = Field(..., description="When voucher was created")

    # Bandwidth limits
    upload_limit_kbps: int | None = Field(
        None, alias="qos_rate_max_up", description="Upload speed limit in kbps"
    )
    download_limit_kbps: int | None = Field(
        None, alias="qos_rate_max_down", description="Download speed limit in kbps"
    )
    upload_quota_mb: int | None = Field(
        None, alias="qos_usage_quota", description="Upload quota in MB"
    )
    download_quota_mb: int | None = Field(None, description="Download quota in MB")

    # Additional metadata
    note: str | None = Field(None, description="Admin notes")
    admin_name: str | None = Field(None, description="Admin who created voucher")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
        extra = "allow"
