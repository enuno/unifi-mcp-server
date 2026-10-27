---
name: unifi-cloud-fleet-tools
description: Use when adding, changing or testing a cloud or multi-controller MCP tool (Site Manager, the connector proxy, the integration API tools, sites, Mobility, InnerSpace, Carrier Fabric) or the fleet stack (router, registry, pool, read cache, workers, fleet_* and admin tools) - covers API modes, gating, per-call routing, tokens and roles, test fixtures and known gaps.
---

# UniFi Cloud and Fleet Tools

Cloud tools call `https://api.ui.com` (Site Manager and the connector proxy). Fleet code lets one server serve many controllers. Read this before you change either. For the general add-a-tool workflow, see `unifi-mcp-tool-builder`.

## Module map

| Module | Tools | Examples |
|--------|-------|----------|
| `src/tools/site_manager.py` | 16 | `list_all_sites_aggregated`, `get_isp_metrics`, `list_hosts` |
| `src/tools/connector.py` | 10 | `connector_network_get`, `connector_protect_post` |
| `src/tools/integration_api.py` | 14 | `list_integration_sites`, `list_integration_wans` |
| `src/tools/sites.py` | 3 | `list_sites`, `get_site_details`, `get_site_statistics` |
| `src/tools/mobility.py` | 8 | `list_mobility_workspaces`, `update_mobility_device` |
| `src/tools/innerspace.py` | 6 | `list_innerspace_floor_plans` (reads only) |
| `src/tools/carrier.py` | 11 | `create_carrier_subscriber`, `suspend_carrier_subscriber` |

Fleet tools are built inside functions, not defined at module level, so the "every public async function is a tool" rule does not apply to them:

| Source | Tools | Registered when |
|--------|-------|-----------------|
| `register_fleet_tools()` in `src/fleet/tools.py` | `list_controllers`, `select_controller`, `get_active_controller` | always |
| `register_admin_tools()` in `src/fleet/admin_tools.py` | 11, such as `register_controller`, `create_api_token`, `verify_audit_chain` | `DATABASE_URL` is set, and not read-only |
| `register_fleet_read_tools()` in `src/fleet/fleet_tools.py` | `fleet_health`, `fleet_sites`, `fleet_inventory`, `fleet_compare_versions`, `fleet_compare_sites`, `fleet_fanout` | `DATABASE_URL` is set |

## API modes and gating

- `APIType` (`src/config/config.py`) is `local`, `cloud-v1` or `cloud-ea`. The code default is `cloud-ea`.
- Cloud modes register only `_CLOUD_TOOL_MODULES` (`src/main.py`): `sites`, `site_manager`, `connector`, `integration_api`, `carrier`, `innerspace` and `mobility`. Local mode registers these too. In cloud mode `get_site_statistics` is left out, because its endpoints return 404 on the cloud API. That gives 71 tools, including the 4 fleet tools.
- Local mode registers both lists, so the cloud tools are available there too.
- Site Manager tools need `UNIFI_SITE_MANAGER_ENABLED=true`:
  - `site_manager` tools use the `require_site_manager` decorator;
  - `mobility`, `innerspace` and `carrier` call their own `_require_cloud_api()`, which checks `site_manager_enabled`;
  - the connector tools repeat the check inline.
- Paths:
  - `SiteManagerClient` (`src/api/site_manager_client.py`) uses the base URL `https://api.ui.com/v1/` and the `X-API-KEY` header.
  - Connector calls go to `connector/consoles/{console_id}/proxy/{network|protect}/{path}`.
  - `_validate_connector_params` (`src/tools/connector.py`) checks both inputs before a client is built, and every connector tool uses the normalized values it returns. `console_id` goes through `validate_path_segment` (`src/utils/validators.py`): surrounding whitespace is stripped, then only `[A-Za-z0-9._~:-]` is allowed, up to 256 characters, and an all-dots value is refused. `path` goes through `validate_proxy_path`: leading slashes are stripped, every segment must match the same character set and must not be empty, `.` or `..`, a single trailing slash is allowed, and the whole path is capped at 2048 characters. `?`, `#`, `%` and `\` are refused, so query strings belong in `params`. This keeps a caller, including a `viewer` on the read-tier GET tools, inside the proxy prefix.
  - InnerSpace goes through the connector proxy.
  - `settings.get_integration_path()` gives `/v1/...` for cloud-v1 and `/integration/v1/...` for cloud-ea.
- Profiles: `UNIFI_PROFILE` has `mobility`, `innerspace` and `carrier` sets.

## Per-call routing

Routing happens in the registry wrapper (`_make_tool_wrapper()` in `src/tool_registry.py`), not in tool bodies.

- Every routed tool gets a keyword-only `controller` argument.
- `FleetRouter.resolve()` (`src/fleet/router.py`) picks the controller in this order:
  1. the explicit `controller` argument;
  2. the session choice from `select_controller` (state key `SESSION_KEY`);
  3. the registry default.
- **A write must name its target.** With two or more controllers registered, a write that would fall back to the default raises `ValidationError`. Never weaken this.
- The tool receives per-controller `Settings` from `ControllerProfile.apply_to()` (`src/fleet/registry.py`). Only connection fields can differ; safety switches such as read-only stay process-wide.
- `select_controller` is refused in stateless HTTP mode (`MCP_STATELESS_HTTP`).

## Fleet stack

- **Registry.** Without `DATABASE_URL`, `EnvRegistry` holds one controller named `default`. With it, `PostgresRegistry` (`src/fleet/postgres_registry.py`) serves lookups from memory and refreshes:
  - every `UNIFI_FLEET_REGISTRY_REFRESH_SECONDS`;
  - on a Redis change event.

  Stored credentials are encrypted with `UNIFI_FLEET_CREDENTIAL_KEY` (`src/fleet/credentials.py`).
- **Pool.** `ClientPool` (`src/api/pool.py`) keeps one HTTP client, one rate limiter and one circuit breaker per controller, up to `UNIFI_FLEET_MAX_OPEN_CLIENTS`.
- **Rate limit.** `UNIFI_RATE_LIMIT_REQUESTS` per `UNIFI_RATE_LIMIT_PERIOD` (`src/api/rate_limit.py`).
  - With Redis, the window is shared across replicas, and cloud calls share one window per API key.
  - Without Redis, each process gets the limit divided by `UNIFI_FLEET_EXPECTED_REPLICAS`.
- **Read cache.** `ReadCache` (`src/cache.py`) needs `UNIFI_CACHE_ENABLED` and an explicit Redis setting.
  - It caches only the modules in `CACHED_MODULES`, which hold no cloud module.
  - Cached tools gain a `fresh` argument.
  - Any write that is not a dry run clears the controller's cached reads.
- **Workers.** `python -m src.worker` runs health and sync jobs (`src/worker/jobs.py`). Controllers are split between workers by rendezvous hashing and Redis leases (`src/worker/shards.py`).
- **Fan-out.** `fleet_fanout` runs only read-tier tools that take a `controller` argument, and returns one `{ok, data|error}` entry per controller. Writes are never fanned out. The limits are `UNIFI_FLEET_FANOUT_CONCURRENCY`, `UNIFI_FLEET_FANOUT_TIMEOUT_SECONDS` and `UNIFI_FLEET_FANOUT_DEADLINE_SECONDS`.
- **Webhook event bus.** When Redis is configured, verified webhook deliveries on `POST /webhooks/unifi` are published to `unifi:webhooks:v1:events` after local handlers run. Other replicas and workers can subscribe to react to events without each receiving the HTTP callback. Messages carry an `origin` instance id; listeners ignore their own messages. Redis outages are logged and do not block the HTTP response (`src/fleet/bus.py`, `src/webhooks/receiver.py`, `WEBHOOK_SETUP.md`).
- **Install.** The `fleet` extra in `pyproject.toml` adds redis, SQLAlchemy, asyncpg and alembic.

## Auth, roles and audit

- **Network transports refuse to start without auth** (`ensure_network_transport_authenticated()` in `src/main.py`).
  - `MCP_AUTH_TOKEN` holds static bearer tokens.
  - With a database, `FleetTokenVerifier` checks server-issued tokens (`src/fleet/tokens.py`). They start with `umcp_`, are stored only as SHA-256 hashes, and can be limited by role, module and controller label.
- **Roles** (`ROLE_TIERS` in `src/access.py`):
  - viewer: read
  - operator: read and write
  - admin: adds destructive
  - fleet-admin: everything

  stdio callers and `MCP_AUTH_TOKEN` callers are fleet-admin, unless `UNIFI_STDIO_ROLE` lowers the stdio role.
- **Audit.** Every mutating call writes a hash-chained attempt record and outcome record (`src/utils/audit.py`). The call is refused if the write fails while `UNIFI_AUDIT_FAIL_CLOSED` is on. Verify a log with `python -m src.utils.audit_verify`.

## Write tools

- Signature: `confirm: bool | str = False, dry_run: bool | str = False`. Call `validate_confirmation(confirm, "<operation>", dry_run)` first, and return `{"dry_run": True, "operation": ..., "payload": ...}` before you open a client (see `src/tools/mobility.py`).
- `DESTRUCTIVE_TOOLS` (`src/tool_registry.py`) already holds all 8 mutating connector tools and `suspend_carrier_subscriber`. Carrier writes have the largest blast radius; keep them confirm-gated.
- A risky word in a tool name needs an entry in `DESTRUCTIVE_TOOLS` or in `RISKY_NAME_EXEMPTIONS` (`tests/unit/fleet/test_tiers.py`). Regenerate the snapshot with `UPDATE_TOOL_TIERS=1 pytest tests/unit/fleet/test_tiers.py`.

## Models and responses

- Models: `src/models/site_manager.py`, `src/models/mobility.py`, `src/models/innerspace.py`, `src/models/carrier.py`, `src/models/integration_api.py`. They use `populate_by_name=True`, `extra="allow"` and camelCase aliases.
- List tools return `{"count", "data"}`. Integration API lists also return `offset`, `limit` and `totalCount`.
- Many `site_manager` tools return raw dicts or lists.

## Tests

- **Tool tests** patch the client: `patch("src.tools.carrier.SiteManagerClient", return_value=cm)`. Here `cm` is an `AsyncMock` context manager, and the settings `MagicMock` has `site_manager_enabled=True`. Representative: `tests/unit/tools/test_carrier.py`. Assert the endpoint string and the gate error.
- **Client tests** use a real httpx client with `httpx.MockTransport` (`tests/unit/api/test_site_manager_client.py`).
- **Redis tests** use `fakeredis` (`tests/unit/fleet/test_read_cache.py`).
- **Postgres tests** start a real server with `pgserver`, with no Docker. The fixtures are in `tests/unit/fleet/conftest.py`.
- `make verify-fleet-scale` runs 3 replicas and 2 workers locally.

## Gotchas

- A docs test requires every setting to be listed in `API.md` and `.env.example`. Add both when you add a setting.
- Spec snapshots for Mobility, InnerSpace and Carrier Fabric are in `scripts/`. Upstream hosts only the current version, so keep old snapshots when you need a diff.
- MCP resources still read the default controller, not the routed one.
- Stateful HTTP behind a load balancer needs sticky routing on `mcp-session-id`.
- Tool modules are chosen once, from the base `UNIFI_API_TYPE`. A registered controller with a different API type still gets that tool set, so on a cloud-typed base a registered local gateway is routable while the local-only modules were never registered. Set `UNIFI_MIXED_MODE=true` to register the cloud and local modules together for a mixed fleet; `UNIFI_PROFILE` still narrows the union, and no base `UNIFI_LOCAL_HOST` is needed. See API.md, "Connecting to the cloud API and local gateways together".

## Known defects (not fixed)

- `SiteManagerClient` hardcodes its base URL. It ignores `UNIFI_CLOUD_API_URL`, and it does not use the pool or the rate limiter.
