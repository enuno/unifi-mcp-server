"""Site data model."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Site(BaseModel):
    """UniFi site information."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "default",
                "name": "Default Site",
                "desc": "Default site description",
            }
        },
    )

    id: str = Field(..., description="Site ID", alias="_id")
    name: str = Field(..., description="Site name")
    desc: Optional[str] = Field(None, description="Site description")

    # Optional metadata fields
    attr_hidden_id: Optional[str] = Field(None, description="Hidden ID attribute")
    attr_no_delete: Optional[bool] = Field(None, description="Whether site can be deleted")
    role: Optional[str] = Field(None, description="Site role")
