"""Data models for UniFi MCP Server."""

from .acl import ACLRule
from .client import Client
from .device import Device
from .dpi import Country, DPIApplication, DPICategory
from .firewall_zone import FirewallZone
from .network import Network
from .site import Site
from .site_manager import (
    CrossSiteStatistics,
    InternetHealthMetrics,
    SiteHealthSummary,
    VantagePoint,
)
from .traffic_flow import FlowRisk, FlowStatistics, FlowView, TrafficFlow
from .traffic_matching_list import (
    TrafficMatchingList,
    TrafficMatchingListCreate,
    TrafficMatchingListType,
    TrafficMatchingListUpdate,
)
from .voucher import Voucher
from .wan import WANConnection
from .zbf_matrix import ApplicationBlockRule, ZoneNetworkAssignment, ZonePolicy, ZonePolicyMatrix

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
    "ZonePolicyMatrix",
    "ZonePolicy",
    "ApplicationBlockRule",
    "ZoneNetworkAssignment",
    "TrafficFlow",
    "FlowStatistics",
    "FlowRisk",
    "FlowView",
    "TrafficMatchingList",
    "TrafficMatchingListCreate",
    "TrafficMatchingListUpdate",
    "TrafficMatchingListType",
    "SiteHealthSummary",
    "InternetHealthMetrics",
    "CrossSiteStatistics",
    "VantagePoint",
]
