"""Agent card construction for the UniFi MCP server.

The card describes the server to another agent: what it is, how to reach it,
how to authenticate, and what it can do. Every field that describes
capability is derived from the live tool registry through
:mod:`src.a2a.capabilities`, so the card cannot advertise a tool this
deployment did not register or call a tool safe that the server would refuse.

The document follows the A2A ``AgentCard`` object shape (specification
0.3.0, section 5.5). The server does not implement the A2A task protocol, so
``capabilities.streaming`` and ``capabilities.pushNotifications`` are
``false``: the card says what the server can actually do. The gap and the
decision behind it are recorded in ``docs/AUDIT_A2A_SKILLS.md``.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

from fastmcp import FastMCP
from fastmcp.resources.function_resource import FunctionResource
from fastmcp.tools.function_tool import FunctionTool

from ..config import APIType, Settings
from .capabilities import (
    A2A_PROTOCOL_VERSION,
    DEFAULT_INPUT_MODES,
    DEFAULT_OUTPUT_MODES,
    PREFERRED_TRANSPORT,
    CapabilitySummary,
    advertised_api_modes,
    advertised_capabilities,
    agent_card_url,
    iter_registered_resources,
    iter_registered_tools,
    security_schemes,
    summarize_capabilities,
    tool_tier,
)
from .types import AuthenticationMode, ResourceURI, SafetyRequirement, Skill

#: Fields of a tool's input schema that name a credential. A card lists
#: them so a reader knows the tool handles a secret, but the card never
#: carries their values.
_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "acct_secret",
        "api_key",
        "apikey",
        "auth_secret",
        "authorization",
        "client_secret",
        "passphrase",
        "password",
        "secret",
        "token",
    }
)


def _package_version() -> str:
    """Return the installed package version when available."""
    try:
        return importlib.metadata.version("unifi-mcp-server")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _tool_description(tool: FunctionTool) -> str:
    """Get a useful description for a tool."""
    if tool.description:
        return tool.description
    fn = getattr(tool, "fn", None)
    doc = getattr(fn, "__doc__", None)
    if doc:
        return str(doc.strip().splitlines()[0])
    return f"MCP tool: {tool.name}"


def _schema_for_tool(tool: FunctionTool) -> dict[str, Any]:
    """Return the input schema for a tool."""
    schema = getattr(tool, "parameters", None)
    return schema if isinstance(schema, dict) else {"type": "object", "properties": {}}


def _output_schema_for_tool(tool: FunctionTool) -> dict[str, Any]:
    """Return the output schema for a tool."""
    schema = getattr(tool, "output_schema", None)
    return schema if isinstance(schema, dict) else {"type": "object"}


def _example_value_for_schema(schema: dict[str, Any], field_name: str) -> Any:
    """Generate a representative example value from a JSON schema fragment.

    A credential parameter gets a redaction placeholder rather than a
    plausible-looking value, so the published card cannot be mistaken for
    a credential and cannot trip a secret scanner.
    """
    if field_name.lower() in _SENSITIVE_FIELD_NAMES:
        return "<redacted>"
    if "default" in schema:
        return schema["default"]
    schema_type = schema.get("type")
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        item_schema = schema.get("items", {}) if isinstance(schema.get("items"), dict) else {}
        return [_example_value_for_schema(item_schema, field_name)]
    if schema_type == "object":
        return {}
    if field_name.endswith("_id") or field_name.endswith("id"):
        return "example-id"
    if "site" in field_name.lower():
        return "default"
    if any(token in field_name.lower() for token in ("name", "label", "title")):
        return f"example-{field_name}"
    return f"example-{field_name}"


def _example_call_payload(tool: FunctionTool) -> dict[str, Any]:
    """Create a practical example payload for a tool."""
    schema = _schema_for_tool(tool)
    properties = schema.get("properties", {}) if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required", []) if isinstance(schema.get("required"), list) else []
    sample: dict[str, Any] = {}
    for field_name in required[:4]:
        field_schema = properties.get(field_name, {})
        if isinstance(field_schema, dict):
            sample[field_name] = _example_value_for_schema(field_schema, field_name)
    if not sample and properties:
        first_name = next(iter(properties))
        first_schema = properties.get(first_name, {})
        if isinstance(first_schema, dict):
            sample[first_name] = _example_value_for_schema(first_schema, first_name)
    if "confirm" in properties:
        sample.setdefault("confirm", True)
    if "dry_run" in properties:
        sample.setdefault("dry_run", True)
    return {"tool": tool.name, "arguments": sample}


def _sensitive_fields(tool: FunctionTool) -> list[str]:
    """Identify parameter names that carry a credential.

    A parameter is matched on its own name, not on a substring: ``ssid`` and
    ``description`` are not secrets, and a field named ``tokenizer`` is not
    a token.

    Args:
        tool: The registered tool.

    Returns:
        The sorted parameter names that name a credential.
    """
    properties = _schema_for_tool(tool).get("properties", {})
    if not isinstance(properties, dict):
        return []
    return sorted(name for name in properties if str(name).lower() in _SENSITIVE_FIELD_NAMES)


def _safety_requirement_for_tool(tool: FunctionTool) -> SafetyRequirement | None:
    """Build a safety requirement record for a tool when needed.

    The destructive flag and the confirmation level come from the tool
    registry's tier, the same tier the server authorizes against, so the
    card never disagrees with the enforcement. A write-tier tool mutates
    controller state and the server requires ``confirm=True`` for it, so it
    is reported as requiring confirmation even though it is not
    destructive.

    Args:
        tool: The registered tool.

    Returns:
        The requirement, or None when the tool is a plain read with no
        credential parameters.
    """
    tier = tool_tier(tool)
    destructive = tier in ("destructive", "fleet-admin")
    mutating = tier in ("write", "destructive", "fleet-admin")
    sensitive_fields = _sensitive_fields(tool)
    if not mutating and not sensitive_fields:
        return None
    if destructive:
        confirmation_level = "required"
        reason = "Destructive action: removing or resetting controller state."
    elif mutating:
        confirmation_level = "required"
        reason = "Mutating controller state requires explicit confirmation."
    else:
        confirmation_level = "recommended"
        reason = "Sensitive parameters detected."
    return SafetyRequirement(
        confirmationLevel=confirmation_level,
        destructive=destructive,
        sensitiveFields=sensitive_fields,
        toolName=tool.name,
        reason=reason,
    )


def _authentication_mode(settings: Settings) -> AuthenticationMode:
    """Map the current settings to the auth mode the server supports.

    Args:
        settings: The server settings.

    Returns:
        The auth mode.
    """
    if settings.api_type == APIType.LOCAL:
        return AuthenticationMode.LOCAL
    if settings.api_type in (APIType.CLOUD_V1, APIType.CLOUD_EA):
        return AuthenticationMode.CLOUD
    return AuthenticationMode.BOTH


def _tool_skill(tool: FunctionTool) -> Skill:
    """Convert a FastMCP tool into an A2A skill.

    Args:
        tool: The registered tool.

    Returns:
        The skill describing the tool.
    """
    return Skill(
        name=tool.name,
        description=_tool_description(tool),
        inputSchema=_schema_for_tool(tool),
        outputSchema=_output_schema_for_tool(tool),
        examples=[_example_call_payload(tool)],
    )


def _resource_uri(resource: FunctionResource) -> ResourceURI:
    """Convert a FastMCP resource into an A2A resource URI.

    Args:
        resource: The registered resource.

    Returns:
        The resource description.
    """
    description = resource.description or f"MCP resource: {resource.name}"
    mime_type = getattr(resource, "mime_type", None) or "text/plain"
    return ResourceURI(
        uri=str(resource.uri),
        name=resource.name,
        description=description,
        mimeType=mime_type,
    )


def _integration_examples(summary: CapabilitySummary) -> list[str]:
    """Return examples that describe the real tool surface.

    Args:
        summary: The capability summary.

    Returns:
        The example strings.
    """
    examples = [
        "Use health_check to verify server availability before delegating a task.",
        "Call a read-only skill such as list_sites or list_devices to discover available scope.",
    ]
    if summary.write_count:
        examples.append(
            "For destructive skills, supply confirm=true and optional dry_run=true for preview."
        )
    if summary.read_only:
        examples.append("This deployment is read-only, so only read-tier skills can run.")
    if summary.dry_run:
        examples.append("This deployment forces dry-run, so every write is returned as a preview.")
    return examples


def build_agent_card(mcp: FastMCP, settings: Settings) -> dict[str, Any]:
    """Build the A2A agent card for a running server.

    Every capability field is derived from the tools this deployment
    registered and the settings that decided it, so the card matches the
    server it describes.

    Args:
        mcp: The FastMCP server whose registered tools describe the
            deployment.
        settings: The server settings.

    Returns:
        The card document.
    """
    summary = summarize_capabilities(mcp, settings)
    base_url = agent_card_url(settings)

    skills = [_tool_skill(tool) for tool in iter_registered_tools(mcp)]
    resources = [_resource_uri(resource) for resource in iter_registered_resources(mcp)]
    safety_requirements = [
        requirement
        for tool in iter_registered_tools(mcp)
        if (requirement := _safety_requirement_for_tool(tool)) is not None
    ]

    return {
        "protocolVersion": A2A_PROTOCOL_VERSION,
        "name": "unifi-mcp-server",
        "description": (
            "UniFi Network and Protect control surface. Exposes read and write "
            "MCP tools for local and cloud controllers, with confirmation and "
            "audit controls on every state change."
        ),
        "url": f"{base_url}/a2a",
        "preferredTransport": PREFERRED_TRANSPORT,
        "provider": {
            "organization": "UniFi MCP Server",
            "url": "https://github.com/enuno/unifi-mcp-server",
        },
        "version": _package_version(),
        "documentationUrl": "https://github.com/enuno/unifi-mcp-server/blob/main/API.md",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "securitySchemes": security_schemes(),
        "security": [{"bearerAuth": []}],
        "defaultInputModes": list(DEFAULT_INPUT_MODES),
        "defaultOutputModes": list(DEFAULT_OUTPUT_MODES),
        "skills": [skill.to_dict() for skill in skills],
        "supportsAuthenticatedExtendedCard": False,
        "metadata": {
            "apiType": summary.api_type,
            "authenticationMode": _authentication_mode(settings).value,
            "apiModes": advertised_api_modes(summary),
            "capabilities": advertised_capabilities(summary),
            "toolCount": summary.tool_count,
            "readToolCount": summary.read_count,
            "writeToolCount": summary.write_count,
            "destructiveToolCount": summary.destructive_count,
            "resourceCount": summary.resource_count,
            "domains": list(summary.domains),
            "readOnly": summary.read_only,
            "dryRun": summary.dry_run,
            "fleet": summary.fleet,
            "resources": [resource.to_dict() for resource in resources],
            "safetyRequirements": [requirement.to_dict() for requirement in safety_requirements],
            "integrationExamples": _integration_examples(summary),
            "toolsManifestUrl": "/a2a/discover",
            "delegateUrl": "/a2a/delegate",
            "confirmUrl": "/a2a/confirm",
            "auditUrl": "/a2a/audit",
        },
    }


def build_agent_capabilities(mcp: FastMCP, settings: Settings) -> dict[str, Any]:
    """Return the capability summary of a running server.

    Args:
        mcp: The FastMCP server.
        settings: The server settings.

    Returns:
        The summary.
    """
    return summarize_capabilities(mcp, settings).to_dict()


__all__ = ["build_agent_capabilities", "build_agent_card"]
