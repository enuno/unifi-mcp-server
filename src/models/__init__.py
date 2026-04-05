"""Data models for UniFi MCP Server."""

from .acl import ACLRule
from .backup import (
    BackupMetadata,
    BackupOperation,
    BackupSchedule,
    BackupStatus,
    BackupType,
    BackupValidationResult,
    RestoreOperation,
    RestoreStatus,
)
from .client import Client
from .device import Device
from .dpi import Country, DPIApplication, DPICategory
from .firewall_policy import (
    ConnectionStateType,
    FirewallPolicy,
    FirewallPolicyCreate,
    FirewallPolicyUpdate,
    IPVersion,
    MatchingTarget,
    MatchTarget,
    PolicyAction,
    Schedule,
)
from .firewall_zone import FirewallZone
from .network import Network
from .port_profile import PortOverride, PortProfile, PortTableEntry
from .qos_profile import MatchCriteria, RouteAction, RouteSchedule, TrafficRoute
from .radius import RADIUSProfile
from .reference_data import DeviceTag
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
from .vpn import VPNServer, VPNTunnel
from .wan import WANConnection
from .zbf_matrix import ZoneNetworkAssignment

__all__ = [
    "Site",
    "Device",
    "Client",
    "Network",
    "ACLRule",
    "Voucher",
    "FirewallZone",
    "FirewallPolicy",
    "FirewallPolicyCreate",
    "FirewallPolicyUpdate",
    "PolicyAction",
    "MatchingTarget",
    "ConnectionStateType",
    "IPVersion",
    "MatchTarget",
    "Schedule",
    "WANConnection",
    "DPICategory",
    "DPIApplication",
    "Country",
    "ZoneNetworkAssignment",
    "TrafficFlow",
    "FlowStatistics",
    "FlowRisk",
    "FlowView",
    "TrafficMatchingList",
    "TrafficMatchingListCreate",
    "TrafficMatchingListUpdate",
    "TrafficMatchingListType",
    "VPNTunnel",
    "VPNServer",
    "RADIUSProfile",
    "DeviceTag",
    "SiteHealthSummary",
    "InternetHealthMetrics",
    "CrossSiteStatistics",
    "VantagePoint",
    "BackupMetadata",
    "BackupOperation",
    "BackupSchedule",
    "BackupStatus",
    "BackupType",
    "BackupValidationResult",
    "RestoreOperation",
    "RestoreStatus",
    "RouteAction",
    "MatchCriteria",
    "RouteSchedule",
    "TrafficRoute",
    "PortProfile",
    "PortOverride",
    "PortTableEntry",
]
