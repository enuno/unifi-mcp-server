"""The single source of truth for what this server can do.

The A2A agent card, the discovery manifest and the repository-level
``agent-card.json`` artifact all describe the same thing: the tools this
deployment registered, the risk tier of each, and the configuration that
decided which tools were registered. Deriving all three from one place is
what keeps them from drifting apart.

The tool inventory comes from the live FastMCP component store, so a card
describes the tools this process actually serves. The risk tier comes from
:data:`src.tool_registry.TOOL_TIERS`, the same registry the tool wrapper
consults when it authorizes a call, so a card never claims a tool is safe
when the server would refuse it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from fastmcp import FastMCP
from fastmcp.resources.function_resource import FunctionResource
from fastmcp.tools.function_tool import FunctionTool

from ..config import APIType, Settings
from ..tool_registry import TOOL_TIERS
from ..tool_registry import tool_tier as registry_tool_tier

#: The A2A protocol version whose AgentCard shape this server publishes.
#: The server does not implement the A2A task protocol; see
#: docs/AUDIT_A2A_SKILLS.md for the gap and the decision behind it.
A2A_PROTOCOL_VERSION = "0.3.0"

#: The A2A transport the card advertises for its preferred endpoint.
PREFERRED_TRANSPORT = "HTTP+JSON"

#: Media types the server produces for every skill.
DEFAULT_OUTPUT_MODES: tuple[str, ...] = ("application/json",)

#: Media types the server accepts for every skill.
DEFAULT_INPUT_MODES: tuple[str, ...] = ("application/json",)

#: The addresses a wildcard bind uses. They are not reachable addresses, so
#: a published URL never names one.
_WILDCARD_HOSTS = ("0.0.0.0", "::")  # nosec B104 - a comparison, not a bind

#: The address a published URL uses when the server binds to a wildcard.
_LOOPBACK_HOST = "127.0.0.1"

#: A tool module belongs to the domain that names it. The mapping is
#: explicit rather than inferred from the module name so that a new module
#: has to be placed deliberately instead of silently landing in a domain.
_MODULE_DOMAINS: dict[str, str] = {
    "acls": "security",
    "application": "applications",
    "backups": "system",
    "carrier": "cloud",
    "channel_planning": "wireless",
    "client_management": "clients",
    "clients": "clients",
    "connector": "cloud",
    "content_filtering": "security",
    "device_control": "devices",
    "device_migration": "devices",
    "devices": "devices",
    "dhcp_reservations": "network",
    "diagnostics": "devices",
    "dns_management": "network",
    "dpi": "system",
    "dpi_tools": "system",
    "events": "system",
    "firewall": "security",
    "firewall_groups": "security",
    "firewall_policies": "security",
    "firewall_zones": "security",
    "innerspace": "cloud",
    "integration_api": "cloud",
    "mac_tags": "clients",
    "mobility": "cloud",
    "network_config": "network",
    "networks": "network",
    "port_forwarding": "security",
    "port_profiles": "devices",
    "protect_alarm": "protect",
    "protect_alarm_hubs": "protect",
    "protect_bridges": "protect",
    "protect_cameras": "protect",
    "protect_devices": "protect",
    "protect_events": "protect",
    "protect_fobs": "protect",
    "protect_link_stations": "protect",
    "protect_nvr": "protect",
    "protect_pos": "protect",
    "protect_relays": "protect",
    "protect_sirens": "protect",
    "protect_speakers": "protect",
    "protect_users": "protect",
    "protect_views": "protect",
    "qos": "network",
    "radius": "security",
    "reference_data": "system",
    "site_manager": "cloud",
    "site_vpn": "security",
    "sites": "system",
    "switching": "devices",
    "topology": "network",
    "traffic_flows": "system",
    "traffic_matching_lists": "security",
    "vouchers": "clients",
    "vpn": "security",
    "wans": "network",
    "wifi": "wireless",
}

#: The domains a reader looks for, in the order the card lists them.
DOMAIN_ORDER: tuple[str, ...] = (
    "network",
    "wireless",
    "clients",
    "devices",
    "security",
    "protect",
    "system",
    "cloud",
    "applications",
    "fleet",
)


def domain_for_tool(tool: FunctionTool) -> str:
    """Return the capability domain a tool belongs to.

    Args:
        tool: The registered tool.

    Returns:
        The domain name. A tool from an unknown module lands in ``fleet``,
        because that is where the server's own fleet tools live.
    """
    module = getattr(tool.fn, "__module__", "") or ""
    if module.startswith("src.fleet"):
        return "fleet"
    if module == "src.main":
        return "system"
    short = module.rsplit(".", 1)[-1]
    return _MODULE_DOMAINS.get(short, "fleet")


def tool_tier(tool: FunctionTool | str) -> str:
    """Return the risk tier the server enforces for a tool.

    The tier is the one the registry derives from the tool's own
    function, so the tier a card advertises is the tier that is actually
    enforced. A name the registry does not know is treated as
    ``destructive``, so an unknown name is never advertised as safe.

    Args:
        tool: The registered tool, or its public name.

    Returns:
        The risk tier of the tool.
    """
    if isinstance(tool, str):
        return TOOL_TIERS.get(tool, "destructive")
    name = tool.name
    tier = TOOL_TIERS.get(name)
    if tier is not None:
        return tier
    # A tool the registry table does not cover is still a registered tool:
    # the fleet tools and the health check register by another path. Its
    # tier comes from its own function, classified the same way the
    # registry classifies one.
    function = getattr(tool, "fn", None)
    if function is None:
        return "destructive"
    try:
        return registry_tool_tier(function)
    except Exception:  # pragma: no cover - a tool with an odd signature
        return "destructive"


def iter_registered_tools(mcp: FastMCP) -> Iterable[FunctionTool]:
    """Yield the tools registered on *mcp*, in registration order.

    Args:
        mcp: The FastMCP server.

    Yields:
        Each registered tool.
    """
    for provider in getattr(mcp, "providers", []):
        components = getattr(provider, "_components", None)
        if not isinstance(components, dict):
            continue
        for component in components.values():
            if isinstance(component, FunctionTool):
                yield component


def iter_registered_resources(mcp: FastMCP) -> Iterable[FunctionResource]:
    """Yield the resources registered on *mcp*.

    Args:
        mcp: The FastMCP server.

    Yields:
        Each registered resource.
    """
    for provider in getattr(mcp, "providers", []):
        components = getattr(provider, "_components", None)
        if not isinstance(components, dict):
            continue
        for component in components.values():
            if isinstance(component, FunctionResource):
                yield component


@dataclass(frozen=True, slots=True)
class CapabilitySummary:
    """What this deployment exposes, derived from the live registry.

    Attributes:
        tool_count: Number of registered tools.
        read_count: Tools the server authorizes at the ``read`` tier.
        write_count: Tools the server authorizes at the ``write`` tier.
        destructive_count: Tools the server authorizes at the ``destructive``
            or ``fleet-admin`` tier.
        domains: Capability domains present, in :data:`DOMAIN_ORDER`.
        domain_tools: Tool names per domain.
        resource_count: Number of registered resources.
        api_type: The configured API mode.
        read_only: Whether the server registered only read-tier tools.
        dry_run: Whether the server forces every write into a preview.
        fleet: Whether the fleet stack is configured.
    """

    tool_count: int = 0
    read_count: int = 0
    write_count: int = 0
    destructive_count: int = 0
    domains: tuple[str, ...] = ()
    domain_tools: dict[str, tuple[str, ...]] = field(default_factory=dict)
    resource_count: int = 0
    api_type: str = APIType.LOCAL.value
    read_only: bool = False
    dry_run: bool = False
    fleet: bool = False

    def tools_in(self, domain: str) -> tuple[str, ...]:
        """Return the tool names in a domain.

        Args:
            domain: The domain name.

        Returns:
            The tool names, or an empty tuple for an unknown domain.
        """
        return self.domain_tools.get(domain, ())

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the summary.

        Returns:
            The summary as plain data.
        """
        return {
            "toolCount": self.tool_count,
            "readToolCount": self.read_count,
            "writeToolCount": self.write_count,
            "destructiveToolCount": self.destructive_count,
            "domains": list(self.domains),
            "domainTools": {domain: list(names) for domain, names in self.domain_tools.items()},
            "resourceCount": self.resource_count,
            "apiType": self.api_type,
            "readOnly": self.read_only,
            "dryRun": self.dry_run,
            "fleet": self.fleet,
        }


def summarize_capabilities(mcp: FastMCP, settings: Settings) -> CapabilitySummary:
    """Derive the capability summary of a running server.

    Args:
        mcp: The FastMCP server whose registered tools describe the
            deployment.
        settings: The server settings.

    Returns:
        The summary.
    """
    domain_tools: dict[str, list[str]] = {}
    read_count = 0
    write_count = 0
    destructive_count = 0
    total = 0

    for tool in iter_registered_tools(mcp):
        total += 1
        tier = tool_tier(tool)
        if tier == "read":
            read_count += 1
        elif tier == "write":
            write_count += 1
        else:
            destructive_count += 1
        domain_tools.setdefault(domain_for_tool(tool), []).append(tool.name)

    ordered_domains = tuple(domain for domain in DOMAIN_ORDER if domain in domain_tools) + tuple(
        sorted(d for d in domain_tools if d not in DOMAIN_ORDER)
    )

    return CapabilitySummary(
        tool_count=total,
        read_count=read_count,
        write_count=write_count,
        destructive_count=destructive_count,
        domains=ordered_domains,
        domain_tools={domain: tuple(sorted(names)) for domain, names in domain_tools.items()},
        resource_count=sum(1 for _ in iter_registered_resources(mcp)),
        api_type=settings.api_type.value,
        read_only=settings.read_only is True,
        dry_run=settings.dry_run is True,
        fleet=bool(getattr(settings, "database_url", None)),
    )


def advertised_capabilities(summary: CapabilitySummary) -> list[str]:
    """Return the capability names the card advertises.

    The list is derived from the deployment, so a read-only server or a
    minimal profile does not advertise capabilities it does not have.

    Args:
        summary: The capability summary.

    Returns:
        The capability names, in a stable order.
    """
    capabilities = ["tool-delegation", "safety-controls", "audit-log"]
    for domain in summary.domains:
        capabilities.append(f"{domain}-management")
    if summary.read_only:
        capabilities.append("read-only")
    if summary.dry_run:
        capabilities.append("dry-run")
    if summary.fleet:
        capabilities.append("multi-controller")
    return capabilities


def advertised_api_modes(summary: CapabilitySummary) -> list[str]:
    """Return the API modes this deployment can serve.

    A local server cannot serve the cloud API and a cloud server cannot
    serve a local console, so the card lists only the mode in use.

    Args:
        summary: The capability summary.

    Returns:
        The API mode names.
    """
    return [summary.api_type]


def advertised_authentication(summary: CapabilitySummary) -> dict[str, Any]:
    """Return the authentication block of the card.

    Args:
        summary: The capability summary.

    Returns:
        The authentication description.
    """
    return {
        "schemes": ["bearer"],
        "modes": advertised_api_modes(summary),
        "scopes": ["read", "write", "destructive", "admin"],
    }


def security_schemes() -> dict[str, Any]:
    """Return the A2A security schemes the server implements.

    The server accepts a bearer token on every route. It does not implement
    OAuth2, API keys or mTLS, so the card declares only what exists.

    Returns:
        The security scheme map.
    """
    return {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "MCP_AUTH_TOKEN, or a fleet-issued token. Sent as "
                "'Authorization: Bearer <token>'."
            ),
        }
    }


def agent_card_url(settings: Settings) -> str:
    """Return the URL a client should use to reach this server.

    Args:
        settings: The server settings.

    Returns:
        The base URL of the running server.
    """
    host = settings.server_host
    if host in _WILDCARD_HOSTS:
        # A wildcard bind is not a reachable address. The card has to name an
        # address a client can actually use.
        host = _LOOPBACK_HOST
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{settings.server_port}"


__all__ = [
    "A2A_PROTOCOL_VERSION",
    "DEFAULT_INPUT_MODES",
    "DEFAULT_OUTPUT_MODES",
    "DOMAIN_ORDER",
    "PREFERRED_TRANSPORT",
    "CapabilitySummary",
    "advertised_api_modes",
    "advertised_authentication",
    "advertised_capabilities",
    "agent_card_url",
    "domain_for_tool",
    "iter_registered_resources",
    "iter_registered_tools",
    "security_schemes",
    "summarize_capabilities",
    "tool_tier",
]
