# Fleet Scaling Plan: Postgres Registry + Redis Caching

**Status:** Draft for review · **Date:** 2026-10-09 · **Roadmap item:** DEVELOPMENT_PLAN.md G3 (multi-controller orchestration), Phase 5 Redis event bus
**Implements the runbook:** [`MULTI_CONTROLLER.md`](../MULTI_CONTROLLER.md)

## 1. Goal and decisions

Let one deployment of the MCP server manage **hundreds to thousands of UniFi gateways and cloud accounts**, scaling horizontally across replicas.

| Decision | Choice |
|---|---|
| Tenancy | **Single organization, fleet model.** One trust domain; no tenant isolation layer. Access narrowing is by token scope / controller labels, not tenant. |
| Routing | **Explicit `controller` parameter + session default.** Every tool gains an optional `controller` argument; when omitted, the session-selected controller is used, then the configured default. **Mutating calls must resolve to exactly one controller** (never an implicit fan-out). |
| Scale target | **Hundreds to thousands of controllers, multiple replicas**, with a worker tier for background sync. |
| Credentials | **Fernet-encrypted columns in Postgres**, reusing `src/utils/audit_encryption.py` key handling (MultiFernet, newest-first rotation). The key stays in the environment, never in the database. |

**Hard constraint:** with no `DATABASE_URL` and no `REDIS_URL` set, behavior is **byte-for-byte what it is today**: one controller from `UNIFI_*` env vars, no new dependencies imported, and all 275 tools keep their current schemas apart from the new optional `controller` argument.

## 2. Where the code stands today (survey, 2026-10-09)

| Area | Current state | Consequence for scaling |
|---|---|---|
| Configuration | One `Settings()` built at import time (`src/main.py:92`) and pre-bound into every tool by `_make_tool_wrapper` (`src/tool_registry.py`). | The process is hard-wired to one controller. |
| API clients | Tools construct `UniFiClient(settings)` / `ProtectClient(settings)` / `SiteManagerClient(settings)` **per call**, about 312 call sites. Each builds a new `httpx.AsyncClient` and the `authenticate()` `/ea/sites` probe re-runs per call. | No connection reuse; with N controllers × M calls this is TLS handshakes and probes on every request. |
| Site map | `_site_uuid_to_name` / `_site_id_cache` live on the client instance and are rebuilt per call. | Wasted round-trips; nothing shared across replicas. |
| Rate limiting | Token bucket in process memory (`RateLimiter`, `asyncio.Lock`). | With multiple replicas, each replica gets the full budget, so the true controller-side rate is multiplied by the replica count. |
| Redis cache | `src/cache.py` exists but **no tool uses it** (only webhook handler examples). `redis` is not a runtime dependency. `connect()` reads `redis_host` etc. via `getattr` defaults because `Settings` has no such fields, so the documented `REDIS_HOST` / `REDIS_PORT` are ignored (always `localhost:6379`). `@cached` opens and closes a connection per call. Keys (`devices:{site_id}`) carry no controller identity. | Must be fixed before any use. Un-namespaced keys would mix data between two controllers that both have a `default` site. |
| Identity | Every bearer token maps to `client_id: "mcp-client"`, `scopes: []` (`build_auth_provider`). | Callers can't be told apart, so per-token controller scoping isn't possible. |
| Database | None. | Everything below is new. |
| MCP sessions | FastMCP 3.2.0 provides `session_state_store=` (pluggable key-value store), `ctx.get_state/set_state` (session-scoped), and `http_app(stateless_http=..., event_store=...)`. | Session defaults can live in Redis, so replicas don't need sticky sessions for state (see Phase 4). |

## 3. Target architecture

```
                 ┌──────────── MCP clients (Claude, agents, A2A) ────────────┐
                 │  Bearer token → TokenPrincipal(scopes, controller labels) │
                 └──────────────────────────────┬────────────────────────────┘
                                                │ (load balancer; sticky on mcp-session-id OR stateless_http)
                      ┌─────────────────────────┼─────────────────────────┐
                      ▼                         ▼                         ▼
              ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
              │  API replica │   ...    │  API replica │          │ Worker (n)   │
              │ tool wrapper │          │              │          │ sync / health│
              │  → resolver  │          │              │          │ leased shards│
              │  → ClientPool│          │              │          └──────┬───────┘
              └──────┬───────┘          └──────┬───────┘                 │
                     │                         │                         │
        ┌────────────┴───────┬─────────────────┴────────┬────────────────┘
        ▼                    ▼                          ▼
 ┌─────────────┐     ┌──────────────────────────┐   ┌───────────────────────────────┐
 │  Postgres   │     │          Redis           │   │ UniFi gateways / api.ui.com   │
 │ registry,   │     │ read cache, session      │   │ (hundreds–thousands)          │
 │ creds(enc), │     │ state, rate-limit        │   └───────────────────────────────┘
 │ sites,      │     │ buckets, leases, pub/sub │
 │ inventory,  │     │ (webhooks, invalidation) │
 │ tokens      │     └──────────────────────────┘
 └─────────────┘
```

### 3.1 The central idea: route in the wrapper, not in 275 tools

`_make_tool_wrapper` already removes `settings` from each tool's public signature and injects it. We extend it to:

1. Add an optional `controller: str | None = None` parameter to the public signature (skipped for tools that are controller-agnostic, e.g. registry management tools).
2. On each call, **resolve** the target: explicit argument → `ctx.get_state("active_controller")` → registry default → error.
3. Build (or fetch from an LRU) a **per-controller `Settings`** via `base_settings.model_copy(update=profile.settings_overrides())`, and inject that as `settings`.
4. Bind `controller_id` into a `ContextVar` for the duration of the call, so the client pool, cache keys, audit records, and logs all pick it up without signature changes.

Tool bodies keep calling `UniFiClient(settings)`, and because `settings` is now per-controller, every existing tool becomes multi-controller **without editing it**. This is the low-churn path that makes the plan feasible.

Mutation safety: if a tool declares `confirm` (the existing mutating-tool convention), the resolver requires the target to come from an explicit argument **or** a session selection made in this session. A registry default alone is not enough when more than one controller is registered. That keeps the "accidental cross-controller write" failure mode in `MULTI_CONTROLLER.md` closed.

### 3.2 Postgres (system of record)

Stack: **SQLAlchemy 2.0 async + asyncpg + Alembic**, shipped as an optional `[fleet]` extra so the base install is unchanged.

| Table | Key columns | Notes |
|---|---|---|
| `cloud_accounts` | `id`, `name` (unique), `api_type` (`cloud-v1`/`cloud-ea`), `credential_id`, `labels jsonb`, `enabled`, `last_sync_at` | One Site Manager API key; hosts behind it are discovered, not hand-entered. |
| `controllers` | `id`, `name` (unique, the routing handle), `kind` (`local`/`cloud-ea`/`cloud-v1`), `host`, `port`, `verify_ssl`, `cloud_account_id` (nullable FK), `console_id` (cloud host id), `credential_id`, `labels jsonb`, `enabled`, `is_default`, `capabilities jsonb` (Network/Protect versions, feature gates), `health` (`ok`/`degraded`/`down`), `last_seen_at`, timestamps | Partial unique index enforces at most one `is_default`. |
| `credentials` | `id`, `ciphertext` (`fernet:v1:` token), `key_fingerprint`, `rotated_at` | Only the ciphertext is stored. Encrypt/decrypt goes through `audit_encryption` primitives under a separate env var (`UNIFI_FLEET_CREDENTIAL_KEY`) so audit and credential keys rotate independently. |
| `sites` | `controller_id`, `site_uuid`, `short_name`, `display_name`, `synced_at` | Replaces the per-client `_site_uuid_to_name` rebuild; filled by the worker. |
| `device_inventory` | `controller_id`, `site_uuid`, `mac`, `model`, `version`, `state`, `payload jsonb`, `synced_at` | Snapshot for fleet-wide reads ("which gateways run firmware < X") without fanning out live. |
| `api_tokens` | `id`, `token_hash` (sha256), `name`, `scopes text[]`, `controller_selector jsonb` (label match), `expires_at`, `last_used_at` | Replaces comma-separated `MCP_AUTH_TOKEN` when the DB is configured; env tokens keep working. |
| `audit_log` *(optional, Phase 5)* | Mirrors today's JSONL records + `controller_id` | Keeps the encrypted-payload format from PR #193. JSONL stays the default sink. |

The registry is read through a `ControllerRegistry` protocol with two implementations:

- `EnvRegistry`: a single controller named `default`, built from today's `UNIFI_*` env vars. Always available, so this is the zero-config path.
- `PostgresRegistry`: backed by the tables above, with an **in-process snapshot** refreshed on a short interval and on `registry:changed` pub/sub events, so the hot path never queries Postgres per tool call.

### 3.3 Redis (shared, ephemeral state)

All keys are namespaced `unifi:v1:{controller_id}:...` (the version segment lets a deploy invalidate everything by bumping it).

| Use | Design |
|---|---|
| **Read-through cache** | Rewrite `src/cache.py` around one shared `redis.asyncio` connection pool created at startup (no connect/ping per call). Settings fields: `REDIS_URL` (plus the documented `REDIS_HOST`/`PORT`/`DB`/`PASSWORD` as aliases, fixing the current bug). Key = `unifi:v1:{controller}:{resource}:{site}:{args-hash}`. Single-flight lock (`SET NX PX`) to prevent stampedes on the same key. Keep `CacheConfig` TTLs. Apply caching **in the wrapper** for tools on an explicit read-only allowlist, never by default. |
| **Invalidation** | After a mutating tool succeeds (`confirm=True`, not dry-run), the wrapper deletes `unifi:v1:{controller}:{resource}:*` for that tool's resource family, then publishes `cache:invalidate`. Webhook events map to their controller and do the same. TTLs remain the backstop. |
| **Session state** | Pass a Redis-backed store to `FastMCP(session_state_store=...)`, so `select_controller` survives replica hops. |
| **Distributed rate limiting** | Per-controller token bucket in Redis (a Lua script, atomic), replacing the per-process bucket when Redis is configured. Cloud accounts get a **shared** bucket per API key, because api.ui.com limits per key and not per console. |
| **Auth/site-map cache** | `unifi:v1:{controller}:auth_ok` (short TTL) and site map, so `authenticate()` doesn't re-probe `/ea/sites` on every call. |
| **Leases** | `SET NX PX` leases for worker shard ownership and singleton jobs (cloud-account discovery). |
| **Pub/sub** | `registry:changed`, `cache:invalidate`, and the existing roadmap item "webhook event bus with Redis pub/sub". |

### 3.4 Connection management at thousands of controllers

- **ClientPool** keyed by `controller_id`, holding one long-lived `httpx.AsyncClient` per controller. **LRU-bounded** (`FLEET_MAX_OPEN_CLIENTS`, default 256) with idle eviction, since keeping a thousand TLS pools open per replica isn't viable. `UniFiClient.__aenter__` takes the pooled transport when a `ContextVar` pool is active, and `__aexit__` does not close it. Without a pool, behavior is unchanged.
- **Per-controller circuit breaker**: after consecutive failures, mark `health=down` and fail fast with a clear error for a cool-off period instead of burning timeouts. The worker's health checks close it again.
- **Fan-out reads** (new `fleet_*` tools, read-only): bounded concurrency (`asyncio.Semaphore`, configurable), a per-controller timeout, and **partial results**: each controller returns `{ok, data}` or `{error}`, never all-or-nothing. They prefer `device_inventory` snapshots when fresh enough, and go live only on request.

### 3.5 Worker tier

A new entry point `python -m src.worker` (same image, different command):

- Controllers are sharded across workers by consistent hashing over Redis-registered worker IDs. Shard ownership is held by leases, so a dead worker's shard is picked up after lease expiry.
- Jobs: health check (cheap probe, updates `health` / `capabilities`), site sync → `sites`, inventory sync → `device_inventory` (staggered with jitter so a thousand controllers aren't all polled at :00), and cloud-account discovery (Site Manager `/v1/hosts` → upsert `controllers` with `cloud_account_id`).
- API replicas never poll. They read snapshots and do targeted live calls.

### 3.6 Identity and scoping (single org)

There is no tenant layer, but the fleet still needs least privilege. `api_tokens.controller_selector` (for example `{"labels": {"site_group": "retail"}}`) restricts which controllers a token can resolve, and `scopes` (`read`, `write`, `fleet:admin`) gate mutating and registry-management tools. `build_auth_provider` returns these as the token's claims, and the resolver enforces them. Env-configured tokens map to `scopes=["read","write"]` over all controllers, which matches today's behavior.

## 4. Phased delivery

Each phase is independently shippable, keeps the zero-config path identical, and has explicit verification.

### Phase 0: Foundations and fixes (no behavior change)
- Add `redis_url`/`redis_*` fields to `Settings` and fix `CacheClient` to honor them (fixes the documented-but-ignored `REDIS_HOST`). Move to a shared connection pool.
- Add `database_url`, `fleet_*` settings. Add `[fleet]` extra (`sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `redis`).
- Add `ControllerProfile` (Pydantic) and the `ControllerRegistry` protocol with `EnvRegistry`.
- `docker-compose.fleet.yml` with Postgres 16 + Redis 7 for development and integration tests.
- **Verify:** full unit suite unchanged; a new test proves `REDIS_HOST` is honored; an import test proves the base install imports no `sqlalchemy`/`asyncpg`/`redis`.

### Phase 1: Routing core
- Extend `_make_tool_wrapper` per §3.1: `controller` parameter, resolver, per-controller `Settings` LRU, and a `controller_id` `ContextVar`.
- New tools: `list_controllers`, `select_controller`, `get_active_controller`.
- Record `controller` in every audit record and log line. Expose a per-controller **call-count gauge only**, with no controller label on the per-tool histogram (275 tools × 1,000 controllers would be a cardinality blow-up; see DEVELOPMENT_PLAN risk register).
- **Verify:** concurrency tests where two sessions with different selected controllers interleave 1,000 calls and every request hits its own controller (respx-mocked hosts). A mutating tool with only a registry default and ≥2 controllers fails with a clear error. Tool JSON schemas are snapshot-tested: only the added optional `controller` field changes.

### Phase 2: Postgres registry and encrypted credentials
- Alembic baseline migration for the §3.2 tables (except `audit_log`).
- `PostgresRegistry` with snapshot + `registry:changed` refresh. Credential encryption reusing `audit_encryption` primitives under `UNIFI_FLEET_CREDENTIAL_KEY`.
- Management tools (`fleet:admin` scope, `confirm=True`, dry-run aware): `register_controller`, `update_controller`, `disable_controller`, `register_cloud_account`, `rotate_fleet_credentials` (re-encrypt under the newest key).
- `unifi-mcp fleet import` CLI that seeds the registry from the current env config, for migration.
- **Verify:** migration up/down tests against a real Postgres (testcontainers, in CI when Actions is unblocked). No API key or plaintext credential ever appears in logs, audit, errors, or tool output (property test modeled on the PR #193 key-never-leaks tests). Registry outage → the last snapshot keeps serving reads, and registry writes fail loudly.

### Phase 3: Connection pool and caching on the hot path
- `ClientPool` with LRU/idle eviction and circuit breakers (§3.4). Auth/site-map caching (§3.3).
- Wrapper-level read-through cache for an allowlist of high-traffic read tools (devices, clients, sites, networks, WLANs), plus mutation-driven invalidation.
- **Verify:** benchmark harness with 500 simulated controllers on a mock server: p50/p95 tool latency and controller-side request count before vs. after (target: ≥80% fewer controller requests for repeated reads; no `/ea/sites` probe per call). A stale-read test confirms a mutation is visible on the next read.

### Phase 4: Horizontal scale
- Redis `session_state_store`, distributed rate limiting, pub/sub invalidation.
- **Session affinity decision** (needs a spike): FastMCP's Streamable HTTP keeps transport sessions in replica memory. Option A: sticky load balancing on `mcp-session-id` (simplest; state in Redis covers failover re-selection). Option B: `stateless_http=True` plus Redis session state (any replica serves any request; loses server-initiated streams). Recommendation: **A by default, B as a documented mode**, chosen after the spike.
- Worker tier (§3.5) with lease-based sharding and staggered sync. `fleet_*` fan-out read tools over snapshots.
- **Verify:** a 3-replica + 2-worker compose test. Killing a worker leads to its shard being reassigned within lease TTL + 1 interval. Rate-limit test: 3 replicas combined never exceed one controller's budget. Fan-out over 1,000 mocked controllers with 5% failing returns partial results within the configured deadline.

### Phase 5: Hardening and documentation
- Token scopes and `controller_selector` enforcement (§3.6). Optional Postgres audit sink.
- Degradation drills: Redis down → cache bypass, local rate limiter at `budget / expected_replicas`, explicit `controller` required (no session default). Postgres down → snapshot reads only.
- Update `MULTI_CONTROLLER.md` (registry now real), README configuration, `.env.example`, API.md (new tools), DEVELOPMENT_PLAN G3 status.
- **Verify:** chaos tests in the compose environment; docs reviewed against the implemented env vars.

## 5. Risks and open questions

| Risk / question | Mitigation / next step |
|---|---|
| Cross-controller write via a stale session default | Mutations require an explicit or same-session selection (§3.1); the audit records the resolved controller. |
| Per-controller `Settings` copies diverge from base settings (e.g. `read_only`, `dry_run` must be global) | Profiles may only override connection fields (`api_type`, `local_host`, `local_port`, `local_verify_ssl`, `api_key`, `default_site`, rate limits). Safety flags are not overridable, enforced by a test. |
| Metric cardinality at fleet scale | No controller label on per-tool series; per-controller gauges only, capped. |
| Mixed Network/Protect versions across the fleet | `controllers.capabilities` from health checks; tools can gate on capability instead of failing remotely. |
| FastMCP `session_state_store` backend options | Confirm which key-value backends 3.2 ships (Redis via `py-key-value`?) in the Phase 4 spike; fall back to a thin custom store if needed. |
| Cloud API rate limits are per key across all its consoles | Shared bucket per `cloud_account` (§3.3). |
| CI is currently blocked (account billing lock) | Postgres/Redis integration tests need Actions. Until then, `make ci` runs locally against `docker-compose.fleet.yml`. |
| Credential-key loss | Same blast-radius model as the audit key: documented rotation, and `rotate_fleet_credentials` re-encrypts under the newest key while old keys are still listed. |

## 6. Out of scope (for this plan)

- Multi-tenant isolation (row-level security, per-tenant quotas). The schema doesn't preclude adding `tenant_id` later, but nothing here builds it.
- External secret stores (Vault, AWS Secrets Manager). Credentials live encrypted in Postgres, per the decision above.
- A web UI for the registry. Management is via MCP tools and the CLI.
