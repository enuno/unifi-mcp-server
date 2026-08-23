"""Site ID validation across the tool surface.

``site_id`` is interpolated straight into request paths (for example
``/ea/sites/{site_id}/rest/radiusprofile``), and the client's endpoint
translation matches ``^/ea/sites/([^/]+)/(.+)$`` — a value carrying ``/``,
``..``, ``?`` or ``#`` moves the capture boundary and lands the request on a
different path than the tool name implies. ``validate_site_id`` already existed
and was applied in some modules; these tests pin it down for all of them.
"""

from __future__ import annotations

import ast
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import acls, radius, traffic_flows, vouchers, wifi
from src.utils.exceptions import ValidationError

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[3] / "src" / "tools"

# Modules deliberately exempt:
#   site_manager - four tools take ``site_id: str | None``; the validator
#                  rejects None, and their site is optional by design.
#   connector    - addresses consoles by ``console_id``, which contains a
#                  colon and is not a site ID.
EXEMPT_MODULES = {"site_manager.py", "connector.py", "__init__.py"}

HOSTILE_SITE_IDS = [
    "default/../../../v2/api/site/default/firewall-policies",
    "default/../../hosts",
    "default#",
    "default?filter=all",
    "default/rest/firewallrule",
    "",
]


def _tools_with_required_site_id() -> list[tuple[str, str, ast.AsyncFunctionDef, str]]:
    """Return (module, function, node, source) for every public async tool
    that takes a required ``site_id: str``."""
    found = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        if path.name in EXEMPT_MODULES:
            continue
        source = path.read_text()
        tree = ast.parse(source)
        for node in tree.body:
            if not isinstance(node, ast.AsyncFunctionDef) or node.name.startswith("_"):
                continue
            arg = next((a for a in node.args.args if a.arg == "site_id"), None)
            if arg is None or arg.annotation is None:
                continue
            if ast.unparse(arg.annotation) != "str":
                continue
            required = len(node.args.args) - len(node.args.defaults)
            if arg not in node.args.args[:required]:
                continue
            found.append((path.name, node.name, node, source))
    return found


def test_discovery_finds_the_tool_surface() -> None:
    """Guard against the collector silently matching nothing."""
    tools = _tools_with_required_site_id()
    assert len(tools) > 80, f"expected the full tool surface, found {len(tools)}"


def test_every_tool_validates_site_id() -> None:
    """Every tool taking a required site_id must validate it.

    Static rather than behavioural on purpose: it also covers tools whose
    other required arguments make them awkward to call, and it fails for a
    newly added tool that forgets the call.
    """
    offenders = [
        f"{module}::{name}"
        for module, name, node, source in _tools_with_required_site_id()
        if "validate_site_id(site_id)" not in (ast.get_source_segment(source, node) or "")
    ]
    assert not offenders, f"tools not validating site_id: {sorted(offenders)}"


def test_validation_runs_before_any_network_io() -> None:
    """Validation must happen before the request is built, not after it.

    Deliberately not "must be the first statement": several tools legitimately
    set up a logger or check the API mode first. What matters is that no
    request is constructed with an unvalidated site_id.
    """
    late = []
    for module, name, node, _source in _tools_with_required_site_id():
        validate_line = None
        io_line = None
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            rendered = ast.unparse(child)
            if validate_line is None and rendered.startswith("validate_site_id(site_id"):
                validate_line = child.lineno
            if io_line is None and (
                rendered.startswith("UniFiClient(")
                or any(
                    rendered.startswith(f"client.{verb}(")
                    for verb in ("get", "post", "put", "patch", "delete", "request")
                )
            ):
                io_line = child.lineno
        if validate_line is None:
            continue  # covered by test_every_tool_validates_site_id
        if io_line is not None and io_line < validate_line:
            late.append(f"{module}::{name} (I/O at line {io_line}, validation at {validate_line})")
    assert not late, f"site_id reaches a request before validation: {sorted(late)}"


@pytest.mark.asyncio
@pytest.mark.parametrize("hostile", HOSTILE_SITE_IDS)
@pytest.mark.parametrize(
    "tool",
    [acls.list_acl_rules, radius.list_radius_profiles, vouchers.list_vouchers, wifi.list_wlans],
    ids=lambda t: t.__name__,
)
async def test_hostile_site_id_is_rejected(tool, hostile: str) -> None:
    """A path-escaping site_id raises before any client is constructed."""
    settings = MagicMock()
    settings.log_level = "INFO"

    with patch("src.api.client.UniFiClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock()
        with pytest.raises(ValidationError):
            await tool(site_id=hostile, settings=settings)
        client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_legitimate_site_ids_are_accepted() -> None:
    """The real site ID forms must keep working."""
    from src.utils.validators import validate_site_id

    for good in ("default", "88f7af54-98f8-306a-a1c7-c9349722b1f6", "64f3ea9e476c410824968da6"):
        assert validate_site_id(good) == good


@pytest.mark.asyncio
async def test_traffic_flows_rejects_hostile_site_id() -> None:
    """Cover a read-only module too, not just the writers."""
    settings = MagicMock()
    settings.log_level = "INFO"
    with pytest.raises(ValidationError):
        await traffic_flows.get_traffic_flows(site_id="default/../../hosts", settings=settings)
