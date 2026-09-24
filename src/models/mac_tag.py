"""MAC tag models.

A tag on UniFi is a named set of device MAC addresses (``member_table``),
stored at the legacy V1 internal endpoint
``/proxy/network/api/s/{site}/rest/tag``. The controller uses tags to target
WiFi broadcasts at a subset of access points. The Integration API only lists
device tags (``list_device_tags``); this legacy endpoint is the writable
surface, so these tools are local-gateway only.
"""

from pydantic import BaseModel, ConfigDict, Field


class MacTag(BaseModel):
    """A tag and the device MAC addresses assigned to it."""

    id: str = Field(..., alias="_id", description="Tag identifier (24-hex ObjectId)")
    name: str = Field(..., description="Tag display name")
    member_table: list[str] = Field(
        default_factory=list,
        description="MAC addresses of the devices carrying this tag",
    )
    site_id: str | None = Field(None, description="Internal site id (not always returned)")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @property
    def member_count(self) -> int:
        """Number of MAC addresses on the tag."""
        return len(self.member_table)
