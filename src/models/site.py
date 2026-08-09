"""Site data model."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class Site(BaseModel):
    """UniFi site information (compatible with Cloud and Local API)."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",  # Allow extra fields from Cloud API
        json_schema_extra={
            "example": {
                "_id": "default",
                "name": "Default Site",
                "desc": "Default site description",
            }
        },
    )

    id: str = Field(
        ...,
        description="Site ID",
        alias="_id",
        validation_alias=AliasChoices("_id", "siteId", "id"),
    )

    name: str | None = Field(
        None,
        description="Site name",
        validation_alias=AliasChoices("name", "siteName"),
    )

    desc: str | None = Field(
        None,
        description="Site description",
        validation_alias=AliasChoices("desc", "description"),
    )

    # Cloud API specific fields
    is_owner: bool | None = Field(
        None, alias="isOwner", description="Whether user owns the site (Cloud API)"
    )

    # Optional metadata fields (Local API)
    attr_hidden_id: str | None = Field(None, description="Hidden ID attribute")
    attr_no_delete: bool | None = Field(None, description="Whether site can be deleted")
    role: str | None = Field(None, description="Site role")

    @model_validator(mode="after")
    def set_name_fallback(self) -> "Site":
        """Set name from ID if not provided (Cloud API compatibility).

        Returns:
            The Site instance with name populated
        """
        if self.name is None or self.name == "":
            self.name = f"Site {self.id}"
        return self


class SiteReference(BaseModel):
    """A site entry from the local ``/ea/sites`` listing.

    Only the two fields needed to translate a site UUID into the short name the
    local API's path segments expect. ``internalReference`` is the short name
    ("default"); it is optional because older controllers omit it, in which case
    the site simply cannot be translated.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(..., description="Site UUID as returned by /ea/sites")
    internal_reference: str | None = Field(
        None,
        description="Site short name used in local API paths",
        validation_alias=AliasChoices("internalReference", "internal_reference"),
    )
