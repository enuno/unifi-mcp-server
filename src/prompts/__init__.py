"""Native MCP prompts for UniFi operational workflows.

The catalog in :mod:`src.prompts.catalog` describes the workflows, the
templates in :mod:`src.prompts.templates` render them, and the registry in
:mod:`src.prompts.registry` decides which of them this server may advertise
based on the tools it actually registered.

Example:
    >>> from src.prompts import register_prompts
    >>> from src.config import Settings
    >>> register_prompts(mcp, Settings())  # doctest: +SKIP
    ['network_health_check', 'troubleshoot_client_connectivity']
"""

from .catalog import PROMPT_NAMES, WORKFLOWS
from .registry import available_workflows, register_prompts
from .templates import (
    ArgumentSpec,
    EvidenceTool,
    PromptArgumentError,
    RenderContext,
    Requirement,
    WorkflowSpec,
    render_workflow,
    validate_arguments,
)

__all__ = [
    "ArgumentSpec",
    "EvidenceTool",
    "PROMPT_NAMES",
    "PromptArgumentError",
    "RenderContext",
    "Requirement",
    "WORKFLOWS",
    "WorkflowSpec",
    "available_workflows",
    "register_prompts",
    "render_workflow",
    "validate_arguments",
]
