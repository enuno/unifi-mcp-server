"""Agent card construction helpers for the UniFi MCP server."""

from __future__ import annotations

import importlib.metadata
import re
from collections.abc import Iterable
from typing import Any

from fastmcp import FastMCP
from fastmcp.resources.function_resource import FunctionResource
from fastmcp.tools.function_tool import FunctionTool

from ..config import APIType, Settings
from .types import AgentCard, AuthenticationMode, ResourceURI, SafetyRequirement, Skill

_DESTRUCTIVE_NAME_RE = re.compile(
    r"(?:^|_)(?:create|delete|remove|reset|restore|reboot|restart|disable|enable|update|patch|set|modify|purge|clear|flush|provision|deprovision|shutdown)(?:_|$)",
    re.IGNORECASE,
)
_SENSITIVE_FIELD_NAMES = {
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "client_secret",
    "confirm",
    "description",
    "key",
    "passphrase",
    "password",
    "secret",
    "ssid",
    "token",
    "username",
}


def _package_version() -> str:
    """Return the installed package version when available."""
    try:
        return importlib.metadata.version("unifi-mcp-server")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _iter_registered_components(mcp: FastMCP) -> Iterable[tuple[str, Any]]:
    """Yield registered tool/resource components from a FastMCP instance."""
    for provider in getattr(mcp, "providers", []):
        components = getattr(provider, "_components", None)
        if not isinstance(components, dict):
            continue
        yield from components.items()


def _tool_description(tool: FunctionTool) -> str:
    """Get a useful description for a tool."""
    if tool.description:
        return tool.description
    fn = getattr(tool, "fn", None)
    doc = getattr(fn, "__doc__", None)
    if doc:
        return doc.strip().splitlines()[0]
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
    """Generate a representative example value from a JSON schema fragment."""
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


def _is_destructive_tool(tool: FunctionTool) -> bool:
    """Heuristically determine whether a tool can change controller state."""
    name = tool.name.lower()
    description = _tool_description(tool).lower()
    if _DESTRUCTIVE_NAME_RE.search(name):
        return True
    if any(
        token in description
        for token in (
            "delete",
            "remove",
            "reset",
            "restore",
            "reboot",
            "restart",
            "disable",
            "clear",
            "flush",
            "provision",
            "deprovision",
        )
    ):
        return True
    properties = _schema_for_tool(tool).get("properties", {})
    if isinstance(properties, dict) and "confirm" in properties:
        return True
    return False


def _sensitive_fields(tool: FunctionTool) -> list[str]:
    """Identify parameter names that should be treated as sensitive."""
    properties = _schema_for_tool(tool).get("properties", {})
    if not isinstance(properties, dict):
        return []
    sensitive: list[str] = []
    for name in properties:
        normalized = name.lower()
        if normalized in _SENSITIVE_FIELD_NAMES or any(
            token in normalized for token in _SENSITIVE_FIELD_NAMES
        ):
            sensitive.append(name)
    return sorted(dict.fromkeys(sensitive))


def _safety_requirement_for_tool(tool: FunctionTool) -> SafetyRequirement | None:
    """Build a safety requirement record for a tool when needed."""
    destructive = _is_destructive_tool(tool)
    sensitive_fields = _sensitive_fields(tool)
    if not destructive and not sensitive_fields:
        return None
    confirmation_level = "required" if destructive else "recommended"
    reason = (
        "Mutating controller state requires explicit confirmation."
        if destructive
        else "Sensitive parameters detected."
    )
    return SafetyRequirement(
        confirmationLevel=confirmation_level,
        destructive=destructive,
        sensitiveFields=sensitive_fields,
        toolName=tool.name,
        reason=reason,
    )


def _authentication_mode(settings: Settings) -> AuthenticationMode:
    """Map the current settings to the broadest supported auth mode."""
    if settings.api_type == APIType.LOCAL:
        return AuthenticationMode.BOTH
    if settings.api_type in (APIType.CLOUD_V1, APIType.CLOUD_EA):
        return AuthenticationMode.BOTH
    return AuthenticationMode.BOTH


def _tool_skill(tool: FunctionTool) -> Skill:
    """Convert a FastMCP tool into an A2A skill."""
    return Skill(
        name=tool.name,
        description=_tool_description(tool),
        inputSchema=_schema_for_tool(tool),
        outputSchema=_output_schema_for_tool(tool),
        examples=[_example_call_payload(tool)],
    )


def _resource_uri(resource: FunctionResource) -> ResourceURI:
    """Convert a FastMCP resource into an A2A resource URI."""
    description = resource.description or f"MCP resource: {resource.name}"
    mime_type = getattr(resource, "mime_type", None) or "text/plain"
    return ResourceURI(
        uri=str(resource.uri),
        name=resource.name,
        description=description,
        mimeType=mime_type,
    )


def build_agent_card(mcp: FastMCP, settings: Settings) -> AgentCard:
    """Build an A2A agent card from a FastMCP server instance.

    The resulting card mirrors the live MCP registration state so it can be
    safely exposed to other agents for discovery and delegation.
    """
    skills: list[Skill] = []
    resources: list[ResourceURI] = []
    safety_requirements: list[SafetyRequirement] = []

    for _, component in _iter_registered_components(mcp):
        if isinstance(component, FunctionTool):
            skill = _tool_skill(component)
            skills.append(skill)
            requirement = _safety_requirement_for_tool(component)
            if requirement is not None:
                safety_requirements.append(requirement)
        elif isinstance(component, FunctionResource):
            resources.append(_resource_uri(component))

    name = getattr(getattr(mcp, "_mcp_server", None), "name", "UniFi MCP Server")
    description = (
        "A UniFi Network control surface exposed through MCP and A2A for local and cloud "
        "controller operations."
    )
    metadata = {
        "apiType": settings.api_type.value,
        "baseUrl": settings.base_url,
        "resourceCount": len(resources),
        "skillCount": len(skills),
        "toolModules": len(getattr(mcp, "providers", [])),
    }
    if settings.api_type == APIType.LOCAL:
        metadata["localHost"] = settings.local_host
    else:
        metadata["cloudApiUrl"] = settings.cloud_api_url

    integration_examples = [
        "Use health_check to verify server availability before delegating a task.",
        "Call a read-only skill such as list_sites or list_devices to discover available scope.",
        "For destructive skills, supply confirm=true and optional dry_run=true for preview.",
    ]

    return AgentCard(
        name=name,
        version=_package_version(),
        description=description,
        authenticationMode=_authentication_mode(settings),
        skills=skills,
        resources=resources,
        safetyRequirements=safety_requirements,
        integrationExamples=integration_examples,
        metadata=metadata,
    )


__all__ = ["build_agent_card"]
