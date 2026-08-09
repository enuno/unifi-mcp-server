"""Deep Packet Inspection (DPI) models."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class DPICategory(BaseModel):
    """DPI category model."""

    id: int | str = Field(
        ..., validation_alias=AliasChoices("id", "_id"), description="Category identifier"
    )
    name: str = Field(..., description="Category name")
    description: str | None = Field(None, description="Category description")

    # Application count
    app_count: int | None = Field(None, description="Number of applications in this category")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class DPIApplication(BaseModel):
    """DPI application model."""

    # Only ``id`` and ``name`` are guaranteed: ``/integration/v1/dpi/applications``
    # returns just those two, and ``id`` comes back as a number there while the
    # legacy endpoint sends a string ``_id``. Everything below is optional so a
    # sparse response validates instead of raising, and every optional field
    # defaults to ``None`` rather than to a concrete value, so an omitted field
    # is never reported as an empty list or an enabled flag nobody set.
    id: int | str = Field(
        ...,
        validation_alias=AliasChoices("id", "_id"),
        description="Application identifier",
    )
    name: str = Field(..., description="Application name")
    category_id: int | str | None = Field(
        None,
        validation_alias=AliasChoices("category_id", "categoryId"),
        description="Category identifier",
    )
    category_name: str | None = Field(
        None,
        validation_alias=AliasChoices("category_name", "categoryName"),
        description="Category name",
    )

    # Application metadata
    enabled: bool | None = Field(None, description="Whether application detection is enabled")

    # Traffic classification
    protocols: list[str] | None = Field(None, description="Protocols used by this application")
    ports: list[int] | None = Field(None, description="Common ports used")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Country(BaseModel):
    """Country information model."""

    code: str = Field(..., description="ISO country code")
    name: str = Field(..., description="Country name")
    iso_code: str | None = Field(None, description="ISO 3166-1 alpha-2 code")
    iso3_code: str | None = Field(None, description="ISO 3166-1 alpha-3 code")

    # Regulatory information
    regulatory_domain: str | None = Field(None, description="Regulatory domain for wireless")

    model_config = ConfigDict(populate_by_name=True, extra="allow")
