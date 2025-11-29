"""QoS (Quality of Service) Profile data models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QoSPriority(str, Enum):
    """QoS priority levels (0-7, where 7 is highest)."""

    BACKGROUND = "0"  # Best Effort, low priority
    BEST_EFFORT = "1"  # Standard traffic
    EXCELLENT_EFFORT = "2"  # Better than best effort
    CRITICAL_APPLICATIONS = "3"  # Business-critical apps
    VIDEO = "4"  # Streaming video (<100ms latency)
    VOICE = "5"  # VoIP (<10ms latency)
    INTERNETWORK_CONTROL = "6"  # Network control traffic
    NETWORK_CONTROL = "7"  # Routing protocols, highest priority


class DSCPValue(str, Enum):
    """Common DSCP (Differentiated Services Code Point) values."""

    # Default
    DEFAULT = "0"  # Best Effort (BE)
    CS0 = "0"  # Class Selector 0

    # Class Selectors
    CS1 = "8"  # Class Selector 1
    CS2 = "16"  # Class Selector 2
    CS3 = "24"  # Class Selector 3
    CS4 = "32"  # Class Selector 4
    CS5 = "40"  # Class Selector 5
    CS6 = "48"  # Class Selector 6
    CS7 = "56"  # Class Selector 7

    # Assured Forwarding (AFxy)
    AF11 = "10"  # AF Class 1, Low Drop
    AF12 = "12"  # AF Class 1, Medium Drop
    AF13 = "14"  # AF Class 1, High Drop
    AF21 = "18"  # AF Class 2, Low Drop
    AF22 = "20"  # AF Class 2, Medium Drop
    AF23 = "22"  # AF Class 2, High Drop
    AF31 = "26"  # AF Class 3, Low Drop
    AF32 = "28"  # AF Class 3, Medium Drop
    AF33 = "30"  # AF Class 3, High Drop
    AF41 = "34"  # AF Class 4, Low Drop
    AF42 = "36"  # AF Class 4, Medium Drop
    AF43 = "38"  # AF Class 4, High Drop

    # Expedited Forwarding
    EF = "46"  # Expedited Forwarding (Voice)

    # Voice Admit
    VOICE_ADMIT = "44"  # Voice-Admit


class QoSAction(str, Enum):
    """QoS action types."""

    PRIORITIZE = "prioritize"  # Set priority/DSCP
    LIMIT = "limit"  # Apply bandwidth limit
    BLOCK = "block"  # Block traffic
    MARK = "mark"  # Mark with DSCP value
    SHAPE = "shape"  # Shape traffic to rate


class ProAVProtocol(str, Enum):
    """Professional Audio/Video protocols."""

    DANTE = "dante"  # Audinate Dante
    Q_SYS = "q-sys"  # QSC Q-SYS
    SDVOE = "sdvoe"  # SDVoE (Software Defined Video over Ethernet)
    AVB = "avb"  # Audio Video Bridging
    RAVENNA = "ravenna"  # AES67/RAVENNA
    NDI = "ndi"  # NewTek NDI
    SMPTE_2110 = "smpte-2110"  # SMPTE ST 2110


class QoSProfile(BaseModel):
    """QoS Profile for traffic prioritization and shaping."""

    id: str = Field(alias="_id", description="Profile ID")
    name: str = Field(..., description="Profile name")
    priority_level: int = Field(..., ge=0, le=7, description="Priority level (0-7, 7=highest)")
    description: str | None = Field(None, description="Profile description")

    # Traffic matching
    applications: list[str] = Field(default_factory=list, description="Application IDs to match")
    categories: list[str] = Field(default_factory=list, description="Category IDs to match")
    ports: list[int] = Field(default_factory=list, description="Port numbers to match")
    protocols: list[str] = Field(default_factory=list, description="Protocols (tcp, udp, icmp)")

    # DSCP marking
    dscp_marking: int | None = Field(None, ge=0, le=63, description="DSCP value to mark packets")
    preserve_dscp: bool = Field(False, description="Preserve existing DSCP markings")

    # Bandwidth control
    bandwidth_limit_down_kbps: int | None = Field(
        None, ge=0, description="Download bandwidth limit in kbps"
    )
    bandwidth_limit_up_kbps: int | None = Field(
        None, ge=0, description="Upload bandwidth limit in kbps"
    )
    bandwidth_guaranteed_down_kbps: int | None = Field(
        None, ge=0, description="Guaranteed download bandwidth in kbps"
    )
    bandwidth_guaranteed_up_kbps: int | None = Field(
        None, ge=0, description="Guaranteed upload bandwidth in kbps"
    )

    # Scheduling
    schedule_enabled: bool = Field(False, description="Enable time-based schedule")
    schedule_days: list[str] = Field(
        default_factory=list, description="Days active (mon, tue, wed, thu, fri, sat, sun)"
    )
    schedule_time_start: str | None = Field(None, description="Start time (HH:MM format)")
    schedule_time_end: str | None = Field(None, description="End time (HH:MM format)")

    # ProAV specific
    proav_protocol: str | None = Field(None, description="ProAV protocol type")
    proav_multicast_enabled: bool = Field(False, description="Enable multicast support")
    proav_ptp_enabled: bool = Field(False, description="Enable PTP (Precision Time Protocol)")

    # State
    enabled: bool = Field(True, description="Profile enabled")
    site_id: str | None = Field(None, description="Site ID")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
        use_enum_values = True


class ProAVTemplate(BaseModel):
    """Pre-configured template for ProAV protocols."""

    name: str = Field(..., description="Template name")
    protocol: ProAVProtocol = Field(..., description="ProAV protocol")
    description: str = Field(..., description="Template description")

    # Recommended QoS settings
    priority_level: int = Field(..., ge=0, le=7)
    dscp_marking: int = Field(..., ge=0, le=63)

    # Protocol-specific ports
    udp_ports: list[int] = Field(default_factory=list)
    tcp_ports: list[int] = Field(default_factory=list)

    # Multicast configuration
    multicast_enabled: bool = Field(False)
    multicast_range: str | None = Field(None, description="Multicast IP range")

    # PTP configuration
    ptp_enabled: bool = Field(False)
    ptp_domain: int | None = Field(None, ge=0, le=255)

    # Bandwidth requirements
    min_bandwidth_mbps: int | None = Field(None, description="Minimum bandwidth in Mbps")
    max_latency_ms: int | None = Field(None, description="Maximum latency in milliseconds")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


# Pre-defined ProAV templates
PROAV_TEMPLATES: dict[str, dict[str, Any]] = {
    "dante": {
        "name": "Audinate Dante",
        "protocol": "dante",
        "description": "Professional audio networking over IP with low latency",
        "priority_level": 5,  # Voice priority
        "dscp_marking": 46,  # EF (Expedited Forwarding)
        "udp_ports": [319, 320, 4440, 4444, 4455, 8700, 8800, 14336, 14337],
        "tcp_ports": [8019, 8700],
        "multicast_enabled": True,
        "multicast_range": "239.255.0.0/16",
        "ptp_enabled": True,
        "ptp_domain": 0,
        "min_bandwidth_mbps": 10,
        "max_latency_ms": 1,
    },
    "q-sys": {
        "name": "QSC Q-SYS",
        "protocol": "q-sys",
        "description": "QSC ecosystem for audio, video, and control",
        "priority_level": 5,
        "dscp_marking": 46,
        "udp_ports": [1700, 1701, 1702, 1703, 1704, 1705],
        "tcp_ports": [1700, 1701, 1710],
        "multicast_enabled": True,
        "multicast_range": "239.255.254.0/24",
        "ptp_enabled": False,
        "min_bandwidth_mbps": 100,
        "max_latency_ms": 2,
    },
    "sdvoe": {
        "name": "SDVoE Alliance",
        "protocol": "sdvoe",
        "description": "Software Defined Video over Ethernet for AV distribution",
        "priority_level": 4,  # Video priority
        "dscp_marking": 34,  # AF41
        "udp_ports": [5353],  # mDNS
        "tcp_ports": [],
        "multicast_enabled": True,
        "multicast_range": "239.0.0.0/8",
        "ptp_enabled": True,
        "ptp_domain": 127,
        "min_bandwidth_mbps": 1000,  # 1 Gbps minimum for 4K
        "max_latency_ms": 100,
    },
    "avb": {
        "name": "Audio Video Bridging (IEEE 802.1)",
        "protocol": "avb",
        "description": "IEEE 802.1 standard for time-sensitive networking",
        "priority_level": 5,
        "dscp_marking": 46,
        "udp_ports": [],
        "tcp_ports": [],
        "multicast_enabled": True,
        "multicast_range": "224.0.1.129/32",
        "ptp_enabled": True,
        "ptp_domain": 0,
        "min_bandwidth_mbps": 75,
        "max_latency_ms": 2,
    },
    "ravenna": {
        "name": "AES67/RAVENNA",
        "protocol": "ravenna",
        "description": "AES67 and RAVENNA for professional IP audio",
        "priority_level": 5,
        "dscp_marking": 46,
        "udp_ports": [5353, 5004, 5005],  # mDNS, RTP, RTCP
        "tcp_ports": [554, 8080],  # RTSP, HTTP
        "multicast_enabled": True,
        "multicast_range": "239.69.0.0/16",
        "ptp_enabled": True,
        "ptp_domain": 0,
        "min_bandwidth_mbps": 48,
        "max_latency_ms": 1,
    },
    "ndi": {
        "name": "NewTek NDI",
        "protocol": "ndi",
        "description": "Network Device Interface for video production",
        "priority_level": 4,
        "dscp_marking": 34,
        "udp_ports": [5353, 5960, 5961],  # mDNS, NDI
        "tcp_ports": [5353, 5960, 5961, 5962, 5963],
        "multicast_enabled": True,
        "multicast_range": "239.255.42.0/24",
        "ptp_enabled": False,
        "min_bandwidth_mbps": 125,  # 1080p60
        "max_latency_ms": 33,  # One frame at 30fps
    },
    "smpte-2110": {
        "name": "SMPTE ST 2110",
        "protocol": "smpte-2110",
        "description": "Professional media over managed IP networks",
        "priority_level": 4,
        "dscp_marking": 34,
        "udp_ports": [],  # Dynamic RTP ports
        "tcp_ports": [],
        "multicast_enabled": True,
        "multicast_range": "239.0.0.0/8",
        "ptp_enabled": True,
        "ptp_domain": 127,
        "min_bandwidth_mbps": 3000,  # 4K uncompressed
        "max_latency_ms": 1,
    },
}
