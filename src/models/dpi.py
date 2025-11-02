"""Deep Packet Inspection (DPI) models."""

from pydantic import BaseModel, Field


class DPICategory(BaseModel):
    """DPI category model."""

    id: str = Field(..., alias="_id", description="Category identifier")
    name: str = Field(..., description="Category name")
    description: str | None = Field(None, description="Category description")

    # Application count
    app_count: int | None = Field(None, description="Number of applications in this category")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
        extra = "allow"


class DPIApplication(BaseModel):
    """DPI application model."""

    id: str = Field(..., alias="_id", description="Application identifier")
    name: str = Field(..., description="Application name")
    category_id: str = Field(..., description="Category identifier")
    category_name: str | None = Field(None, description="Category name")

    # Application metadata
    enabled: bool = Field(True, description="Whether application detection is enabled")

    # Traffic classification
    protocols: list[str] = Field(
        default_factory=list, description="Protocols used by this application"
    )
    ports: list[int] = Field(default_factory=list, description="Common ports used")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
        extra = "allow"


class Country(BaseModel):
    """Country information model."""

    code: str = Field(..., description="ISO country code")
    name: str = Field(..., description="Country name")
    iso_code: str | None = Field(None, description="ISO 3166-1 alpha-2 code")
    iso3_code: str | None = Field(None, description="ISO 3166-1 alpha-3 code")

    # Regulatory information
    regulatory_domain: str | None = Field(None, description="Regulatory domain for wireless")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
        extra = "allow"
