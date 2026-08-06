"""Pydantic models for UniFi Network Integration API v1 endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PaginatedResponse(BaseModel):
    """Common pagination wrapper for integration API list endpoints."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    offset: int = Field(0, description="Pagination offset")
    limit: int = Field(0, description="Pagination limit")
    count: int = Field(0, description="Number of items in this response")
    total_count: int = Field(0, alias="totalCount", description="Total number of items available")


class IntegrationSite(BaseModel):
    """Site as returned by the integration API /v1/sites."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(..., description="Site UUID")
    internal_reference: str | None = Field(
        None, alias="internalReference", description="Internal site reference (short name)"
    )
    name: str = Field(..., description="Site display name")


class IntegrationDevice(BaseModel):
    """Device as returned by the integration API /v1/sites/{siteId}/devices."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(..., description="Device UUID")
    mac_address: str | None = Field(None, alias="macAddress", description="Device MAC address")
    ip_address: str | None = Field(None, alias="ipAddress", description="Device IP address")
    name: str | None = Field(None, description="Device name")
    model: str | None = Field(None, description="Device model string")
    state: str | None = Field(None, description="Device state (e.g., ONLINE, OFFLINE)")
    supported: bool | None = Field(None, description="Whether the device is supported")
    firmware_version: str | None = Field(
        None, alias="firmwareVersion", description="Current firmware version"
    )
    firmware_updatable: bool | None = Field(
        None, alias="firmwareUpdatable", description="Whether firmware can be updated"
    )
    features: list[str] | None = Field(None, description="Supported feature tags")
    interfaces: list[str] | None = Field(None, description="Available interface types")


class IntegrationClient(BaseModel):
    """Client as returned by the integration API /v1/sites/{siteId}/clients."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str | None = Field(None, description="Client type")
    id: str = Field(..., description="Client UUID")
    name: str | None = Field(None, description="Client name or hostname")
    connected_at: str | None = Field(
        None, alias="connectedAt", description="ISO 8601 connection timestamp"
    )
    ip_address: str | None = Field(None, alias="ipAddress", description="Client IP address")
    access: dict[str, Any] | None = Field(None, description="Access point association details")


class NetworkMetadata(BaseModel):
    """Metadata object nested inside integration API network responses."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    origin: str | None = Field(None, description="Origin identifier")


class IntegrationNetwork(BaseModel):
    """Network as returned by the integration API /v1/sites/{siteId}/networks."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    management: str | None = Field(None, description="Management type")
    id: str = Field(..., description="Network UUID")
    name: str = Field(..., description="Network name")
    enabled: bool | None = Field(None, description="Whether the network is enabled")
    vlan_id: int | None = Field(None, alias="vlanId", description="VLAN ID")
    metadata: NetworkMetadata | None = Field(None, description="Network metadata")
    default: bool | None = Field(None, description="Whether this is the default network")


class WifiSecurityConfiguration(BaseModel):
    """Security configuration nested in WiFi broadcast responses."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str | None = Field(None, description="Security type (e.g., WPA2, WPA3)")


class WifiNetworkRef(BaseModel):
    """Network reference nested in WiFi broadcast responses."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str | None = Field(None, description="Network reference type")


class WifiBroadcastingDeviceFilter(BaseModel):
    """Device filter nested in WiFi broadcast responses."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str | None = Field(None, description="Filter type")


class IntegrationWifiBroadcast(BaseModel):
    """WiFi broadcast (SSID) as returned by /v1/sites/{siteId}/wifi/broadcasts."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str | None = Field(None, description="Broadcast type")
    id: str = Field(..., description="Broadcast UUID")
    name: str = Field(..., description="SSID name")
    enabled: bool | None = Field(None, description="Whether the broadcast is enabled")
    metadata: NetworkMetadata | None = Field(None, description="Broadcast metadata")
    network: WifiNetworkRef | None = Field(None, description="Associated network reference")
    security_configuration: WifiSecurityConfiguration | None = Field(
        None, alias="securityConfiguration", description="Security settings"
    )
    broadcasting_device_filter: WifiBroadcastingDeviceFilter | None = Field(
        None, alias="broadcastingDeviceFilter", description="Device filter rules"
    )


class IntegrationDNSPolicy(BaseModel):
    """DNS policy as returned by /v1/sites/{siteId}/dns/policies."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str | None = Field(None, description="Policy type")
    id: str = Field(..., description="Policy UUID")
    enabled: bool | None = Field(None, description="Whether the policy is enabled")
    metadata: NetworkMetadata | None = Field(None, description="Policy metadata")
    domain: str | None = Field(None, description="Domain matched by this policy")


class IntegrationWAN(BaseModel):
    """WAN as returned by /v1/sites/{siteId}/wans."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(..., description="WAN UUID")
    name: str | None = Field(None, description="WAN name")


class IntegrationVPNServer(BaseModel):
    """VPN server as returned by /v1/sites/{siteId}/vpn/servers."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str | None = Field(None, description="VPN server type")
    id: str = Field(..., description="VPN server UUID")
    name: str = Field(..., description="VPN server name")
    enabled: bool | None = Field(None, description="Whether the VPN server is enabled")
    metadata: NetworkMetadata | None = Field(None, description="Server metadata")


class IntegrationDeviceTag(BaseModel):
    """Device tag as returned by /v1/sites/{siteId}/device-tags."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(..., description="Tag UUID")
    name: str = Field(..., description="Tag name")
    device_ids: list[str] | None = Field(
        None, alias="deviceIds", description="Associated device UUIDs"
    )
    metadata: NetworkMetadata | None = Field(None, description="Tag metadata")


class DPICategory(BaseModel):
    """DPI application category as returned by /v1/dpi/categories."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: int = Field(..., description="Category numeric ID")
    name: str = Field(..., description="Category display name")
