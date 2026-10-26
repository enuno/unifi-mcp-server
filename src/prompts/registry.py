"""Registration of the native UniFi MCP prompt catalog.

The registry decides which workflows a running server may advertise. It does
that from the server's own state, not from a second copy of the profile and
API-mode logic: the tool names registered on this FastMCP instance, and the
settings that shape them.

A workflow is advertised only when every capability it requires is satisfied
by a tool that is actually registered. That keeps the catalog honest in every
configuration:

- local-only workflows disappear in cloud mode, because their tools are not
  registered there,
- the Protect workflow disappears where no Protect tool is registered,
- read-only and dry-run modes keep every read-only workflow, and
- the change-planning workflow stays, because it only ever produces a plan.

Registering a prompt never calls a controller, never reads a secret and never
starts work in the background. Listing and retrieving prompts are pure.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from fastmcp import FastMCP
from fastmcp.prompts.base import Prompt, PromptArgument

from .catalog import WORKFLOWS
from .templates import RenderContext, WorkflowSpec, render_workflow, validate_arguments

#: Prefix FastMCP puts in front of a prompt's key. Used to recognise a prompt
#: this server already registered, so registration is idempotent.
_PROMPT_KEY_PREFIX = "prompt:"


class _WorkflowPrompt(Prompt):
    """A FastMCP prompt that renders one workflow from the catalog.

    The prompt carries its workflow spec and the server capability context, so
    rendering is a pure function of the caller's arguments.
    """

    def __init__(
        self,
        spec: WorkflowSpec,
        context: RenderContext,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        """Build the prompt for *spec*.

        Args:
            spec: The workflow this prompt renders.
            context: The server capability metadata the prompt may refer to.
            name: Override for the prompt name. Defaults to the workflow name.
            description: Override for the description. Defaults to the
                workflow description.
        """
        super().__init__(
            name=name or spec.name,
            description=description or spec.description,
            arguments=[
                PromptArgument(
                    name=argument.name,
                    description=argument.description,
                    required=argument.required,
                )
                for argument in spec.arguments
            ],
        )
        # FastMCPComponent is a pydantic model, so the extra state has to live
        # outside the validated fields.
        self._spec = spec
        self._context = context

    async def render(self, arguments: dict[str, Any] | None = None) -> str:
        """Render the workflow prompt.

        Args:
            arguments: The arguments supplied in the ``prompts/get`` call.

        Returns:
            The rendered prompt text.

        Raises:
            PromptArgumentError: If an argument is missing, unknown or invalid.
        """
        values = validate_arguments(self._spec, arguments)
        return render_workflow(self._spec, values, self._context)


def _registered_tool_names(mcp: FastMCP) -> set[str]:
    """Return the public names of the tools registered on *mcp*.

    Reads FastMCP's own component store, so the answer is what the server will
    actually expose over the protocol.

    Args:
        mcp: The FastMCP server instance.

    Returns:
        The registered tool names.
    """
    provider = getattr(mcp, "_local_provider", None)
    components = getattr(provider, "_components", None)
    if not isinstance(components, dict):
        return set()
    names: set[str] = set()
    for key in components:
        if not isinstance(key, str) or not key.startswith("tool:"):
            continue
        # A component key looks like "tool:<name>@<version>".
        name = key[len("tool:") :].split("@", 1)[0]
        if name:
            names.add(name)
    return names


def _registered_prompt_names(mcp: FastMCP) -> set[str]:
    """Return the public names of the prompts registered on *mcp*.

    Args:
        mcp: The FastMCP server instance.

    Returns:
        The registered prompt names.
    """
    provider = getattr(mcp, "_local_provider", None)
    components = getattr(provider, "_components", None)
    if not isinstance(components, dict):
        return set()
    names: set[str] = set()
    for key in components:
        if not isinstance(key, str) or not key.startswith(_PROMPT_KEY_PREFIX):
            continue
        name = key[len(_PROMPT_KEY_PREFIX) :].split("@", 1)[0]
        if name:
            names.add(name)
    return names


def _site_manager_enabled(settings: Any) -> bool:
    """Return whether the Site Manager API is enabled in *settings*.

    Args:
        settings: The server settings.

    Returns:
        True when Site Manager tools can run.
    """
    return getattr(settings, "site_manager_enabled", False) is True


def available_workflows(
    registered_tools: Iterable[str],
    *,
    settings: Any = None,
    workflows: Sequence[WorkflowSpec] = WORKFLOWS,
) -> list[WorkflowSpec]:
    """Return the workflows this server can actually run.

    A workflow qualifies when every capability it requires can be satisfied by
    a registered tool. A tool that needs the Site Manager API only counts when
    that API is enabled, because it is registered either way but refuses to
    run without it.

    Args:
        registered_tools: The tool names registered on the server.
        settings: The server settings, used for the Site Manager gate.
        workflows: The catalog to filter.

    Returns:
        The workflows that may be advertised, in catalog order.
    """
    tools = set(registered_tools)
    site_manager = _site_manager_enabled(settings)
    available: list[WorkflowSpec] = []
    for workflow in workflows:
        satisfied = True
        for requirement in workflow.requirements:
            if not any(
                option.name in tools and (site_manager or not option.requires_site_manager)
                for option in requirement.options
            ):
                satisfied = False
                break
        if satisfied:
            available.append(workflow)
    return available


def _context_for(
    workflow: WorkflowSpec,
    registered_tools: set[str],
    *,
    settings: Any = None,
) -> RenderContext:
    """Return the render context for *workflow*.

    Args:
        workflow: The workflow being rendered.
        registered_tools: The tool names registered on the server.
        settings: The server settings.

    Returns:
        The context describing what this workflow may use.
    """
    site_manager = _site_manager_enabled(settings)
    available = {
        tool.name
        for tool in workflow.evidence
        if tool.name in registered_tools and (site_manager or not tool.requires_site_manager)
    }
    return RenderContext(
        available_tools=frozenset(available),
        registered_tools=frozenset(registered_tools),
        read_only=getattr(settings, "read_only", False) is True,
        dry_run=getattr(settings, "dry_run", False) is True,
    )


def register_prompts(
    mcp: FastMCP,
    settings: Any = None,
    *,
    workflows: Sequence[WorkflowSpec] = WORKFLOWS,
) -> list[str]:
    """Register the workflow prompts this server can run.

    Registration is idempotent: a prompt name that is already registered on
    *mcp* is skipped, so calling this twice does not duplicate a prompt.

    Args:
        mcp: The FastMCP server to register the prompts on.
        settings: The server settings, used for the Site Manager, read-only and
            dry-run gates.
        workflows: The catalog to register from.

    Returns:
        The names of the prompts that were registered.
    """
    registered_tools = _registered_tool_names(mcp)
    already_registered = _registered_prompt_names(mcp)
    registered: list[str] = []

    for workflow in available_workflows(registered_tools, settings=settings, workflows=workflows):
        if workflow.name in already_registered:
            continue
        context = _context_for(workflow, registered_tools, settings=settings)
        mcp.add_prompt(_WorkflowPrompt(workflow, context))
        registered.append(workflow.name)

    return registered


__all__ = [
    "available_workflows",
    "register_prompts",
]
