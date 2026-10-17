"""Switching MCP tools for Switch Stacks, MC-LAG Domains, and LAGs."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.switching import Lag, MclagDomain, SwitchStack
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
    get_logger,
    sanitize_log_message,
    validate_limit_offset,
    validate_site_id,
)
from ..utils.tool_kind import read_tool


@read_tool
async def list_switch_stacks(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all switch stacks in a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of switch stacks to return
        offset: Number of switch stacks to skip

    Returns:
        List of switch stack dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        endpoint = settings.get_integration_path(f"sites/{site_id}/switching/switch-stacks")
        response = await client.get(endpoint)
        raw_stacks: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        paginated = raw_stacks[offset : offset + limit]
        stacks = [SwitchStack.model_validate(s).model_dump(exclude_none=True) for s in paginated]

        logger.info(
            sanitize_log_message(f"Retrieved {len(stacks)} switch stacks for site '{site_id}'")
        )
        return stacks


@read_tool
async def get_switch_stack(
    site_id: str,
    switch_stack_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get details for a specific switch stack.

    Args:
        site_id: Site identifier
        switch_stack_id: Switch stack ID
        settings: Application settings

    Returns:
        Switch stack dictionary

    Raises:
        ResourceNotFoundError: If switch stack not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    if not switch_stack_id:
        raise ValidationError("Switch stack ID cannot be empty")

    async with UniFiClient(settings) as client:
        await client.authenticate()

        endpoint = settings.get_integration_path(
            f"sites/{site_id}/switching/switch-stacks/{switch_stack_id}"
        )
        response = await client.get(endpoint)
        raw_stacks: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        if not raw_stacks:
            raise ResourceNotFoundError("switch_stack", switch_stack_id)

        stack = SwitchStack.model_validate(raw_stacks[0])
        logger.info(
            sanitize_log_message(f"Retrieved switch stack '{switch_stack_id}' for site '{site_id}'")
        )
        return stack.model_dump(exclude_none=True)


@read_tool
async def list_mclag_domains(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all MC-LAG domains in a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of MC-LAG domains to return
        offset: Number of MC-LAG domains to skip

    Returns:
        List of MC-LAG domain dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        endpoint = settings.get_integration_path(f"sites/{site_id}/switching/mc-lag-domains")
        response = await client.get(endpoint)
        raw_domains: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        paginated = raw_domains[offset : offset + limit]
        domains = [MclagDomain.model_validate(d).model_dump(exclude_none=True) for d in paginated]

        logger.info(
            sanitize_log_message(f"Retrieved {len(domains)} MC-LAG domains for site '{site_id}'")
        )
        return domains


@read_tool
async def get_mclag_domain(
    site_id: str,
    mclag_domain_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get details for a specific MC-LAG domain.

    Args:
        site_id: Site identifier
        mclag_domain_id: MC-LAG domain ID
        settings: Application settings

    Returns:
        MC-LAG domain dictionary

    Raises:
        ResourceNotFoundError: If MC-LAG domain not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    if not mclag_domain_id:
        raise ValidationError("MC-LAG domain ID cannot be empty")

    async with UniFiClient(settings) as client:
        await client.authenticate()

        endpoint = settings.get_integration_path(
            f"sites/{site_id}/switching/mc-lag-domains/{mclag_domain_id}"
        )
        response = await client.get(endpoint)
        raw_domains: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        if not raw_domains:
            raise ResourceNotFoundError("mclag_domain", mclag_domain_id)

        domain = MclagDomain.model_validate(raw_domains[0])
        logger.info(
            sanitize_log_message(
                f"Retrieved MC-LAG domain '{mclag_domain_id}' for site '{site_id}'"
            )
        )
        return domain.model_dump(exclude_none=True)


@read_tool
async def list_lags(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all LAGs in a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of LAGs to return
        offset: Number of LAGs to skip

    Returns:
        List of LAG dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        endpoint = settings.get_integration_path(f"sites/{site_id}/switching/lags")
        response = await client.get(endpoint)
        raw_lags: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        paginated = raw_lags[offset : offset + limit]
        lags = [
            Lag.model_validate(lag_item).model_dump(exclude_none=True) for lag_item in paginated
        ]

        logger.info(sanitize_log_message(f"Retrieved {len(lags)} LAGs for site '{site_id}'"))
        return lags


@read_tool
async def get_lag_details(
    site_id: str,
    lag_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get details for a specific LAG.

    Args:
        site_id: Site identifier
        lag_id: LAG ID
        settings: Application settings

    Returns:
        LAG dictionary

    Raises:
        ResourceNotFoundError: If LAG not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    if not lag_id:
        raise ValidationError("LAG ID cannot be empty")

    async with UniFiClient(settings) as client:
        await client.authenticate()

        endpoint = settings.get_integration_path(f"sites/{site_id}/switching/lags/{lag_id}")
        response = await client.get(endpoint)
        raw_lags: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        if not raw_lags:
            raise ResourceNotFoundError("lag", lag_id)

        lag = Lag.model_validate(raw_lags[0])
        logger.info(sanitize_log_message(f"Retrieved LAG '{lag_id}' for site '{site_id}'"))
        return lag.model_dump(exclude_none=True)
