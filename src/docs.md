# Noridoc: src

Path: @/src

### Overview

- The `src/` package is the complete server implementation, with `main.py` as the FastMCP entry point and subdirectories for the API client, tools, models, resources, config, and utilities.
- `main.py` instantiates the `FastMCP` server, registers every MCP tool and resource via `@mcp.tool()` / `@mcp.resource()` decorators, and starts the server through `mcp.run()`.
- All tool and resource logic lives in subdirectories (`@/src/tools/`, `@/src/resources/`); `main.py` acts as the registration layer, forwarding calls to the implementations.

### How it fits into the larger codebase

- `main.py` is the sole consumer of `@/src/tools/` and `@/src/resources/` — it imports every module at startup and wraps each exported function in an MCP decorator.
- A single `Settings` instance (from `@/src/config/`) is created at module load and captured in all `@mcp.tool()` closures, making the tool layer effectively stateless.
- `@/src/api/` (`UniFiClient`) is not imported directly by `main.py`; individual tool modules open their own `async with UniFiClient(settings)` contexts per request.
- The `agnost.ai` integration is the only **optional external dependency** initialized at module load; all other dependencies are mandatory and imported unconditionally.

### Core Implementation

- **Agnost integration pattern**: The agnost monitoring integration is gated by the `AGNOST_ENABLED` env var and `AGNOST_ORG_ID`. When both are set, `main.py` performs **lazy imports** of `agnost.config` and `agnost.track` inside a `try/except Exception` block. Any import failure or runtime error is caught and logged as a warning, allowing the server to continue starting normally. This means agnost is never a hard dependency — the package can be absent, incompatible, or have a changed API without affecting server startup.

```
AGNOST_ENABLED=true + AGNOST_ORG_ID set
    └─► try:
            from agnost import config as agnost_config  ← lazy, inside conditional
            from agnost import track
            track(mcp, org_id, agnost_config(...))
        except Exception:
            logger.warning(...)   ← server continues

AGNOST_ENABLED=false (default) or AGNOST_ORG_ID missing
    └─► agnost code never runs, no imports attempted
```

- **Tool registration**: Each tool module is imported as an alias (e.g., `from .tools import radius as radius_tools`) and each exported async function is wrapped in a thin `@mcp.tool()` closure that binds the singleton `settings` and forwards all other arguments.
- **DEBUG tool**: A `debug_api_request` tool is conditionally registered only when `DEBUG=true`, and its `UniFiClient` import is deferred to the function body via a local `from .api import UniFiClient`.
- **MCP Resources**: Resources are registered via `@mcp.resource("protocol://path")` and delegate to `@/src/resources/` handler classes instantiated at module load.

### Things to Know

- The agnost `track()` signature changed in v0.1.13 — it expects `track(mcp, org_id, config_object)` where `config_object` is created by calling `agnost.config(...)`. The lazy import pattern in `main.py` ensures that any future agnost API change will produce only a `logger.warning`, not a startup crash.
- Module-level statements in `main.py` (imports, `settings = Settings()`, `mcp = FastMCP(...)`, tool registrations) execute at import time. Tests that reload `src.main` via `importlib.import_module` trigger the full startup sequence including the agnost conditional block, which is the basis for regression tests in `@/tests/unit/test_main_agnost_import.py`.
- Several tool and resource endpoints have been removed because the underlying UniFi API endpoints do not exist in API v10.0.156. These removals are documented inline in `main.py` with `# ⚠️ REMOVED:` comments.

Created and maintained by Nori.
