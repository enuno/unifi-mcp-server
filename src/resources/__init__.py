"""MCP resources for UniFi MCP Server."""

from .clients import ClientsResource
from .devices import DevicesResource
from .networks import NetworksResource
from .protect import ProtectResource
from .sites import SitesResource

__all__ = ["SitesResource", "DevicesResource", "ClientsResource", "NetworksResource", "ProtectResource"]
