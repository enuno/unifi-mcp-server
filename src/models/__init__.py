"""Data models for UniFi MCP Server."""

from .acl import ACLRule
from .client import Client
from .device import Device
from .dpi import Country, DPIApplication, DPICategory
from .firewall_zone import FirewallZone
from .network import Network
from .site import Site
from .voucher import Voucher
from .wan import WANConnection

__all__ = [
    "Site",
    "Device",
    "Client",
    "Network",
    "ACLRule",
    "Voucher",
    "FirewallZone",
    "WANConnection",
    "DPICategory",
    "DPIApplication",
    "Country",
]
