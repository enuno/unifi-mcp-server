# Noridoc: tools

Path: @/src/tools

### Overview

- Contains all MCP tool implementations for the UniFi MCP Server, covering every area of UniFi network management from RADIUS to firewall to traffic monitoring.
- Each module corresponds to a functional domain (e.g., `radius.py`, `firewall.py`, `wifi.py`) and exports async functions that are registered as `@mcp.tool()` wrappers in `@/src/main.py`.
- Tools follow a consistent CRUD pattern: list/get/create/update/delete, with all mutating operations requiring `confirm=True` and supporting `dry_run` mode.

### How it fits into the larger codebase

- `@/src/main.py` is the sole consumer: it imports each tool module as an alias (e.g., `radius as radius_tools`) and wraps each function with `@mcp.tool()` to expose it to MCP clients.
- Tools call into `@/src/api/client.py` (`UniFiClient`) for all HTTP communication with the UniFi controller. Each function opens an `async with UniFiClient(settings) as client:` context for its request(s).
- Pydantic models from `@/src/models/` validate and serialize API responses before they are returned; raw dicts from the API are never returned directly.
- `@/src/utils/` provides three shared utilities used throughout: `audit_action` (mutation logging), `get_logger`, and `validate_confirmation` (enforces `confirm=True` guard).
- `@/src/config/` (`Settings`) is threaded through every tool function as a parameter so the tool layer is stateless.

### Core Implementation

- **Tool registration flow**: `src/tools/<module>.py` defines async functions → `src/main.py` wraps them in `@mcp.tool()` closures that capture the singleton `settings` object and forward all other arguments.
- **Payload construction pattern**: Update functions build a sparse `payload` dict from only the `Optional` arguments that are not `None`, then validate the payload is non-empty *before* opening the `UniFiClient` context. This prevents wasted network connections and allows `ValueError` to propagate cleanly in tests (see Things to Know).
- **Password/secret redaction**: Functions that handle credentials (`radius.py`) redact sensitive fields (`x_password`, `auth_secret`, `acct_secret`) in API responses and in audit log payloads before any data leaves the function.
- **Response normalization**: All API responses are normalized via `data = response if isinstance(response, list) else response.get("data", response)` followed by list-unwrapping, because the UniFi API inconsistently returns bare lists, wrapped lists, or wrapped dicts.
- **RADIUS module**: Covers RADIUS Profiles (`/ea/sites/{site_id}/rest/radiusprofile`), RADIUS Accounts (`/ea/sites/{site_id}/rest/account`), Guest Portal config (`/integration/v1/sites/{site_id}/guest-portal/config`), and Hotspot Packages (`/integration/v1/sites/{site_id}/hotspot/packages`). All four resources now have full CRUD.

### Things to Know

- **Empty-payload guard placement**: The `if not payload and not dry_run: raise ValueError(...)` check in update functions must occur *before* the `async with UniFiClient(...) as client:` block. Placing it inside the context manager causes it to be silently swallowed in tests because `AsyncMock().__aexit__` returns a truthy value, suppressing exceptions raised within the block.
- **RADIUS Account field mapping**: The MCP parameter `username` maps to the API field `name`; `password` maps to `x_password`; `vlan_id` maps to `vlan`. When `vlan_id` is provided during creation, `tunnel_type` (13) and `tunnel_medium_type` (6) are auto-set unless explicitly overridden.
- **API prefix split**: RADIUS Profiles and Accounts use the `/ea/` (Early Access) path prefix, while Guest Portal and Hotspot Packages use `/integration/v1/`. This split is significant when debugging endpoint availability across UniFi firmware versions.
- **Dry-run handling in update functions**: When `dry_run=True` and the payload happens to be empty, the empty-payload guard is skipped (`not dry_run` short-circuits), and the function returns a dry-run response indicating nothing would be changed.

Created and maintained by Nori.
