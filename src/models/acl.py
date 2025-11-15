"""Access Control List (ACL) models."""

from pydantic import BaseModel, ConfigDict, Field


class ACLRule(BaseModel):
    """ACL rule model."""

    id: str = Field(..., alias="_id", description="ACL rule identifier")
    site_id: str = Field(..., description="Site identifier")
    name: str = Field(..., description="Rule name")
    enabled: bool = Field(True, description="Whether the rule is enabled")
    action: str = Field(..., description="Action to take (allow/deny)")

    # Source configuration
    source_type: str | None = Field(None, description="Source type (network/device/ip/any)")
    source_id: str | None = Field(None, description="Source identifier")
    source_network: str | None = Field(None, description="Source network CIDR")

    # Destination configuration
    destination_type: str | None = Field(
        None, description="Destination type (network/ip/port/dpi-category/dpi-app)"
    )
    destination_id: str | None = Field(None, description="Destination identifier")
    destination_network: str | None = Field(None, description="Destination network CIDR")

    # Protocol and ports
    protocol: str | None = Field(None, description="Protocol (tcp/udp/icmp/all)")
    src_port: int | None = Field(None, description="Source port")
    dst_port: int | None = Field(None, description="Destination port")

    # Priority and metadata
    priority: int = Field(100, description="Rule priority (lower = higher priority)")
    description: str | None = Field(None, description="Rule description")
    rule_index: int | None = Field(None, description="Rule index in the list")

    # Statistics
    byte_count: int | None = Field(None, description="Bytes matched by this rule")
    packet_count: int | None = Field(None, description="Packets matched by this rule")

    model_config = ConfigDict(populate_by_name=True, extra="allow")
