# Fleet Scaling Plan: Postgres Registry, Redis Caching, RBAC and Audit

**Status:** Draft for review · **Date:** 2026-10-09 · **Roadmap items:** DEVELOPMENT_PLAN.md G3 (multi-controller orchestration), P2 (tool-level RBAC), P3 (append-only audit log), Phase 5 Redis event bus
**Implements the runbook:** [`MULTI_CONTROLLER.md`](../MULTI_CONTROLLER.md)

## 1. Goal and decisions

Let one deployment of the MCP server manage **hundreds to thousands of UniFi gateways and cloud accounts**, scaling horizontally across replicas.

| Decision | Choice |
|---|---|
| Tenancy | **Single organization, fleet model.** One trust domain; no tenant isolation layer. Access narrowing is by token scope / controller labels, not tenant. |
| Routing | **Explicit `controller` parameter + session default.** Every tool gains an optional `controller` argument; when omitted, the session-selected controller is used, then the configured default. **Mutating calls must resolve to exactly one controller** (never an implicit fan-out). |
| Scale target | **Hundreds to thousands of controllers, multiple replicas**, with a worker tier for background sync. |
| Credentials | **Fernet-encrypted columns in Postgres**, reusing `src/utils/audit_encryption.py` key handling (MultiFernet, newest-first rotation). The key stays in the environment, never in the database. |
| Permissions | **Built-in roles over risk tiers.** Every tool has one tier (`read`, `write`, `destructive`, `fleet-admin`) derived from the tool registry, not from its name. Roles (`viewer`, `operator`, `admin`, `fleet-admin`) grant tiers; a token can be narrowed further by module allow/deny lists and a controller label selector. |
| Identity | **API tokens issued by the server and stored hashed in Postgres**, one per person or agent, each bound to a role. The existing `MCP_AUTH_TOKEN` keeps working as a full-access (`admin`) break-glass token. |
| Audit scope | **Every mutating call (including dry-run), every denied call, and every admin/config event.** Reads are not audited. |
| Audit storage | **Postgres append-only table, with today's JSONL file as the fallback**, an **HMAC hash chain** for tamper evidence, **SIEM export**, and **retention plus admin query tools**. |

**Hard constraint:** with no `DATABASE_URL` and no `REDIS_URL` set, behavior is **byte-for-byte what it is today**: one controller from `UNIFI_*` env vars, no new dependencies imported, and all 275 tools keep their current schemas apart from the new optional `controller` argument. The `MCP_AUTH_TOKEN` and stdio callers keep full access, and audit records keep going to the JSONL file.

## 2. Where the code stands today (survey, 2026-10-09)

| Area | Current state | Consequence for scaling |
|---|---|---|
| Configuration | One `Settings()` built at import time (`src/main.py:92`) and pre-bound into every tool by `_make_tool_wrapper` (`src/tool_registry.py`). | The process is hard-wired to one controller. |
| API clients | Tools construct `UniFiClient(settings)` / `ProtectClient(settings)` / `SiteManagerClient(settings)` **per call**, about 312 call sites. Each builds a new `httpx.AsyncClient` and the `authenticate()` `/ea/sites` probe re-runs per call. | No connection reuse; with N controllers × M calls this is TLS handshakes and probes on every request. |
| Site map | `_site_uuid_to_name` / `_site_id_cache` live on the client instance and are rebuilt per call. | Wasted round-trips; nothing shared across replicas. |
| Rate limiting | Token bucket in process memory (`RateLimiter`, `asyncio.Lock`). | With multiple replicas, each replica gets the full budget, so the true controller-side rate is multiplied by the replica count. |
| Redis cache | `src/cache.py` exists but **no tool uses it** (only webhook handler examples). `redis` is not a locked runtime dependency (a venv may still have it via an optional `pydocket` install). `connect()` reads `redis_host` etc. via `getattr` defaults because `Settings` has no such fields, so the documented `REDIS_HOST` / `REDIS_PORT` are ignored (always `localhost:6379`). `@cached` opens and closes a connection per call. Keys (`devices:{site_id}`) carry no controller identity. | Must be fixed before any use. Un-namespaced keys would mix data between two controllers that both have a `default` site. |
| Identity | Every bearer token maps to `client_id: "mcp-client"`, `scopes: []` (`build_auth_provider`). | Callers can't be told apart, so per-token controller scoping isn't possible. |
| Authorization | MCP bearer tokens are all-or-nothing. The A2A layer has `AuthManager.validate_permissions`, but it guesses a tool's risk from its **name prefix** (`delete_` → destructive, `create_` → write, anything else → read), so `block_client`, `reconnect_client`, `upgrade_device` or `restore_backup` count as reads. The registry already knows better: `is_mutating_tool()` (`src/tool_registry.py`) uses the `confirm`/`dry_run` parameters plus an explicit list, and `UNIFI_READ_ONLY` relies on it. | RBAC must classify tools from the registry, not from names. |
| Audit | `AuditLogger` appends JSONL records with credential redaction, mode 0600 and optional payload encryption (#193). Tools call it **by hand**: 167 call sites in 36 of 60 tool modules. The `user` field is filled at 1 call site. Denied calls and admin events aren't recorded; there is no tamper evidence, central store or export. | Coverage depends on each tool remembering to log, and records can't say who acted. |
| Database | None. | Everything below is new. |
| MCP sessions | FastMCP 3.2.0 provides `session_state_store=` (pluggable key-value store), `ctx.get_state/set_state` (session-scoped), and `http_app(stateless_http=..., event_store=...)`. | Session defaults can live in Redis, so replicas don't need sticky sessions for state (see Phase 4). |

## 3. Target architecture

```
                 ┌──────────── MCP clients (Claude, agents, A2A) ────────────┐
                 │  Bearer token → TokenPrincipal(role, controller selector) │
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
 │ tokens,audit│     └──────────────────────────┘
 └─────────────┘
```

### 3.1 The central idea: route in the wrapper, not in 275 tools

`_make_tool_wrapper` already removes `settings` from each tool's public signature and injects it. We extend it to:

1. Add an optional `controller: str | None = None` parameter to the public signature (skipped for tools that are controller-agnostic, e.g. registry management tools).
2. On each call, **resolve** the target: explicit argument → `ctx.get_state("active_controller")` → registry default → error.
3. Build (or fetch from an LRU) a **per-controller `Settings`** via `base_settings.model_copy(update=profile.settings_overrides())`, and inject that as `settings`.
4. Bind `controller_id` into a `ContextVar` for the duration of the call, so the client pool, cache keys, audit records, and logs all pick it up without signature changes.

Tool bodies keep calling `UniFiClient(settings)`, and because `settings` is now per-controller, every existing tool becomes multi-controller **without editing it**. This is the low-churn path that makes the plan feasible.

The same wrapper is also where access control and auditing happen, so each call runs one fixed pipeline: **identify the principal → resolve the controller → authorize (§3.6) → apply `read_only`/`dry_run` → run the tool → write the audit record (§3.7)**. Doing all of it in one place is what makes coverage automatic instead of per-tool.

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
| `api_tokens` | `id`, `token_hash` (sha256), `name`, `role`, `allow_modules text[]`, `deny_modules text[]`, `controller_selector jsonb` (label match), `created_by`, `created_at`, `expires_at`, `revoked_at`, `last_used_at` | Issued by the server (§3.6). Env `MCP_AUTH_TOKEN` keeps working alongside. |
| `audit_log` | The §3.7 record: `event_id`, `ts`, `event_type`, principal, `controller_id`, tool, tier, result, encrypted payload, `chain_id`, `seq`, `prev_hash`, `hash` | **Append-only**: the application's database role gets `INSERT` and `SELECT` only, never `UPDATE`/`DELETE`. Partitioned by month for retention. Keeps the encrypted-payload format from PR #193. |
| `audit_chain_heads` | `chain_id`, `seq`, `hash`, `anchored_at` | Latest position of each hash chain, used for verification and external anchoring. |

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

### 3.6 Access control (RBAC)

**Risk tiers.** At registration every tool gets exactly one tier, recorded in a tool → tier map:

| Tier | Which tools | Source |
|---|---|---|
| `read` | Everything `is_mutating_tool()` says is not mutating | Registry (exists today) |
| `write` | Mutating tools | `is_mutating_tool()`: `confirm`/`dry_run` parameters or `MUTATING_TOOLS_WITHOUT_GATE` |
| `destructive` | Mutating tools that delete, restore, re-image or lock out: `delete_*`, `remove_*`, `restore_backup`, `upgrade_device`, `block_client` and similar | A new explicit `DESTRUCTIVE_TOOLS` list next to `MUTATING_TOOLS_WITHOUT_GATE` |
| `fleet-admin` | Controller registry, token, and audit management tools | Declared by the fleet/admin modules |

A snapshot test pins the whole tool → tier map, so any change in classification shows up in review. A second test flags any mutating tool whose name suggests deletion or reset but which isn't in `DESTRUCTIVE_TOOLS`, unless it's explicitly exempted. The A2A `_required_permission` name-prefix logic is replaced by a lookup in the same map.

**Roles** are built in, not configurable, so they stay easy to reason about:

| Role | Grants |
|---|---|
| `viewer` | `read` |
| `operator` | `read`, `write` |
| `admin` | `read`, `write`, `destructive` |
| `fleet-admin` | everything, including `fleet-admin` tools (tokens, registry, audit queries) |

A token can be **narrowed, never widened**, beyond its role: `allow_modules` / `deny_modules` (tool modules such as `firewall` or `protect_*`) and `controller_selector` (for example `{"labels": {"site_group": "retail"}}`), which limits the controllers it can resolve.

**Principals.** `build_auth_provider` returns the token's claims (`token_id`, `name`, `role`, filters). The wrapper puts a `Principal` in a `ContextVar` for the call, where the resolver, the authorizer and the audit writer all read it.

- DB tokens are 32 random bytes generated by the server, shown once, and stored as SHA-256 (enough for high-entropy tokens; no password hashing needed). They support `expires_at` and `revoked_at`. Revocation reaches every replica through the `tokens:changed` pub/sub message, and token lookups are cached for at most 30 seconds.
- `MCP_AUTH_TOKEN` tokens map to `admin`, which keeps today's behavior. They serve as break-glass access and are flagged in audit records.
- stdio is a local, single-user channel: its principal is `admin` (configurable with `UNIFI_STDIO_ROLE`).

**Enforcement** happens on every call, in the wrapper, before any controller is contacted. A denied call gets a generic `PermissionDeniedError` that names the required tier but not what the token could have done, and it produces a `denied` audit record. As a usability step, tools a principal can't call can also be hidden from that session's tool list (FastMCP's per-session `disable_components`). Hiding is cosmetic; enforcement does not depend on it.

**Token management** (`fleet-admin` only, `confirm=True`, each one an audited admin event): `create_api_token` (returns the token once), `list_api_tokens` (never returns secrets), `revoke_api_token`, `update_api_token_role`, plus an `unifi-mcp tokens` CLI for bootstrapping the first `fleet-admin` token.

### 3.7 Audit logging

**What gets recorded.** The wrapper writes one record for every:

- mutating call, including dry-run, with result `success`, `error` or `dry_run`
- denied call: RBAC refusals and rejected write targets (§3.1), with result `denied`
- admin/config event: token create/revoke/role change, controller registry changes, credential and key rotation, audit queries and exports, and server start with its effective safety configuration (`read_only`, `dry_run`, profile, registry source)

Reads are not audited.

**Record (schema v2):**

| Field | Contents |
|---|---|
| `event_id`, `ts` | UUIDv7 and UTC timestamp |
| `event_type` | `tool_call`, `denied`, `admin`, `system` |
| `principal` | `token_id`, `name`, `role`, `break_glass` flag |
| `session_id`, `request_id` | From the MCP context, to tie records to one conversation |
| `controller`, `site_id`, `tool`, `tier` | What was targeted |
| `parameters`, `error` | Credential-redacted, then encrypted when an audit key is set (PR #193 format) |
| `result`, `duration_ms`, `instance_id` | Outcome, timing, and which replica handled it |
| `chain_id`, `seq`, `prev_hash`, `hash` | Tamper evidence (below) |

**Write-ahead for mutations.** For a mutating call the wrapper writes an `attempt` record before contacting the controller, and the outcome after. If the primary audit store can't take the `attempt` record, the call is refused (`UNIFI_AUDIT_FAIL_CLOSED=true`, the default for writes), so no write happens without an audit trail. Denied and admin records follow the same rule.

**Migration from manual calls.** The 167 existing `log_audit`/`audit_action` calls keep working during the transition. While the wrapper's record is open, those calls attach their details to it instead of writing a second record. They're then removed module by module, and a test confirms each mutating tool produces exactly one record.

**Sinks.** An `AuditSink` protocol with these implementations:

- `JsonlSink`: today's file, still the default without a database. It gets size/date rotation, and the chain continues across files.
- `PostgresSink`: the append-only `audit_log` table (§3.2). It's primary whenever `DATABASE_URL` is set.
- SIEM exporters: syslog (RFC 5424 over TLS), OTLP logs and an HMAC-signed HTTPS webhook. They're asynchronous and best-effort, with an on-disk retry buffer, so a slow SIEM never blocks a tool call. They receive the stored (encrypted-payload) form of each record.

**Tamper evidence.** Each record's `hash` is an HMAC-SHA256, keyed by `UNIFI_AUDIT_CHAIN_KEY` (separate from the payload encryption key), over the canonical JSON of the stored record plus `prev_hash`. Each replica keeps its own chain (`chain_id` = instance id), so writes don't serialize across replicas. Because hashes cover the stored ciphertext, verification doesn't need the payload key. Chain heads are regularly written to `audit_chain_heads` and sent to the SIEM as anchors, so truncating a chain or rewriting it wholesale is detectable from outside the server. Verification uses `verify_audit_chain` (MCP tool) and `unifi-mcp audit verify` (CLI).

**Retention.** `UNIFI_AUDIT_RETENTION_DAYS` (unset = keep forever). Expired monthly partitions are verified, exported to compressed JSONL with their chain heads, and only then dropped; JSONL files are rotated and archived the same way.

**Querying** (`fleet-admin` only; every query is itself an audited admin event): `search_audit_log` (filters: time range, principal, controller, tool, tier, result, event type; cursor pagination; payloads decrypted only when the payload key is configured), `verify_audit_chain`, and `export_audit_log`. The existing `python -m src.utils.audit_decrypt` CLI keeps working for JSONL.

## 4. Phased delivery

Each phase is independently shippable, keeps the zero-config path identical, and has explicit verification.

### Phase 0: Foundations and fixes (no behavior change)
- Add `redis_url`/`redis_*` fields to `Settings` and fix `CacheClient` to honor them (fixes the documented-but-ignored `REDIS_HOST`). Move to a shared connection pool.
- Add `database_url`, `fleet_*` settings. Add `[fleet]` extra (`sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `redis`).
- Add `ControllerProfile` (Pydantic) and the `ControllerRegistry` protocol with `EnvRegistry`.
- `docker-compose.fleet.yml` with Postgres 16 + Redis 7 for development and integration tests.
- **Verify:** full unit suite unchanged; a new test proves `REDIS_HOST` is honored; an import test proves the base install imports no `sqlalchemy`/`asyncpg`/`redis`.
- **Status (2026-10-09): done**, with three items deferred to Phase 2 so that no setting ships before the code that reads it: `DATABASE_URL`/`fleet_*` settings, the Postgres/SQLAlchemy/Alembic packages in `[fleet]` (which holds only `redis` for now), and `docker-compose.fleet.yml` (the existing `docker-compose.yml` already runs Redis). The import test *blocks* the fleet packages instead of checking `sys.modules`, because a developer venv can carry `redis` transitively: an installed `pydocket` makes FastMCP import it, although the locked FastMCP does not depend on it.

### Phase 1: Routing core
- Extend `_make_tool_wrapper` per §3.1: `controller` parameter, resolver, per-controller `Settings` LRU, and a `controller_id` `ContextVar`.
- New tools: `list_controllers`, `select_controller`, `get_active_controller`.
- **Tier map and principal plumbing** (§3.6): classify every tool, add `DESTRUCTIVE_TOOLS`, the tier snapshot test, and the `Principal` `ContextVar`. Point A2A's permission check at the tier map. Every caller is still `admin`, so behavior doesn't change yet.
- **Wrapper-level audit** (§3.7) with schema v2 and the attempt/outcome pattern, written to `JsonlSink` with the HMAC chain, plus `unifi-mcp audit verify`. Start migrating the manual audit calls.
- Record `controller` in every audit record and log line. Expose a per-controller **call-count gauge only**, with no controller label on the per-tool histogram (275 tools × 1,000 controllers would be a cardinality blow-up; see DEVELOPMENT_PLAN risk register).
- **Verify:** concurrency tests where two sessions with different selected controllers interleave 1,000 calls and every request hits its own controller (respx-mocked hosts). A mutating tool with only a registry default and ≥2 controllers fails with a clear error. Tool JSON schemas are snapshot-tested: only the added optional `controller` field changes. Every mutating tool produces exactly one audit record per call, including dry-run and error paths. Editing, deleting or reordering a JSONL line makes `audit verify` fail.
- **Status (2026-10-09): done.** Notes from implementation:
  - Each call writes an `attempt` and an outcome record sharing a `call_id`, so "one record per call" is one record *pair*; manual `log_audit` calls inside a call fold into the outcome's `details`. The 167 manual calls remain and are harmless; removing them is cleanup, not a correctness need.
  - The verifier is `python -m src.utils.audit_verify` (matching `audit_decrypt`) rather than a `unifi-mcp audit verify` subcommand. Without `UNIFI_AUDIT_CHAIN_KEY` the chain uses plain SHA-256.
  - Tiers implemented: `read`, `write`, `destructive` (45 tools). `fleet-admin` arrives with the first admin tools in Phase 2a/2b.
  - Classifying tiers surfaced that A2A delegation treated `restore_backup`, `upgrade_device` and other mutating tools as reads with no confirmation; A2A now uses the registry tiers.
  - MCP resources still read the default controller.

### Phase 2a: Postgres registry and encrypted credentials
- Alembic baseline migration for the §3.2 tables.
- `PostgresRegistry` with snapshot + `registry:changed` refresh. Credential encryption reusing `audit_encryption` primitives under `UNIFI_FLEET_CREDENTIAL_KEY`.
- Management tools (`fleet-admin` tier, `confirm=True`, dry-run aware): `register_controller`, `update_controller`, `disable_controller`, `register_cloud_account`, `rotate_fleet_credentials` (re-encrypt under the newest key).
- `unifi-mcp fleet import` CLI that seeds the registry from the current env config, for migration.
- **Verify:** migration up/down tests against a real Postgres (testcontainers, in CI when Actions is unblocked). No API key or plaintext credential ever appears in logs, audit, errors, or tool output (property test modeled on the PR #193 key-never-leaks tests). Registry outage → the last snapshot keeps serving reads, and registry writes fail loudly.

### Phase 2b: Access control and the audit store
- `api_tokens`, roles and enforcement (§3.6): `create/list/revoke/update_api_token` tools and the `unifi-mcp tokens` CLI, module filters, `controller_selector`, revocation via `tokens:changed`, `PermissionDeniedError` and `denied` records, optional per-session tool hiding.
- `PostgresSink` as primary audit store with the INSERT/SELECT-only role, `audit_chain_heads`, fail-closed write-ahead, and admin/config events.
- `search_audit_log`, `verify_audit_chain`, `export_audit_log` (`fleet-admin` only).
- **Verify:** a role × tier matrix test that runs every role against a sample tool of every tier, plus module and controller filters, and checks allowed calls succeed and denied ones neither reach the (mocked) controller nor skip the `denied` record. A revoked token stops working on every replica within 30 seconds. With the audit store down, mutating calls are refused and reads still work. The database role can't `UPDATE` or `DELETE` `audit_log` (tested against real Postgres). No token secret appears in any log, audit record or tool output.

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
- **SIEM export** (syslog/OTLP/webhook) with the on-disk retry buffer, and chain-head anchoring to the SIEM. **Retention** (`UNIFI_AUDIT_RETENTION_DAYS`): verify, archive, then drop.
- Security drills: an RBAC deny-path review of every tool tier, a tamper test that edits, deletes and truncates records in both stores and expects `verify_audit_chain` to catch each one, and a SIEM-outage test that confirms tool calls aren't blocked.
- Degradation drills: Redis down → cache bypass, local rate limiter at `budget / expected_replicas`, explicit `controller` required (no session default). Postgres down → snapshot reads only.
- Update `MULTI_CONTROLLER.md` (registry now real), `SECURITY.md` (roles, tokens, audit integrity), README configuration, `.env.example`, API.md (new tools), DEVELOPMENT_PLAN G3 status.
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
| A tool gets the wrong risk tier (e.g. a destructive tool classed as `write`) | The tier map is derived from the registry and snapshot-tested; the deletion/reset name check flags likely misses for review. |
| The audit store being down blocks all writes | Intended (fail-closed), and limited to writes: reads keep working. Break-glass: `UNIFI_AUDIT_FAIL_CLOSED=false` falls back to JSONL with a loud warning, recorded as a `system` event. |
| An attacker with database write access rewrites the audit trail | Chain hashes are keyed with a key the database doesn't hold, and chain heads are anchored outside the server (SIEM). |
| A leaked API token | Server-issued tokens expire, revocation propagates in at most 30 seconds, and `last_used_at` plus audit records show where it was used. |
| Audit volume at fleet scale | Reads aren't audited; writes are a small share of calls. Monthly partitions keep retention cheap. |
| Credential-key loss | Same blast-radius model as the audit key: documented rotation, and `rotate_fleet_credentials` re-encrypts under the newest key while old keys are still listed. |

## 6. Out of scope (for this plan)

- Multi-tenant isolation (row-level security, per-tenant quotas). The schema doesn't preclude adding `tenant_id` later, but nothing here builds it.
- External secret stores (Vault, AWS Secrets Manager). Credentials live encrypted in Postgres, per the decision above.
- A web UI for the registry. Management is via MCP tools and the CLI.
- OIDC/JWT identities from an external IdP. The `Principal` abstraction leaves room for another token verifier later, but this plan only issues its own tokens.
- Auditing read calls, and per-tool (rather than per-tier and per-module) permission lists.
