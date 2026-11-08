# UniFi MCP Server — Active TODO

**Last Reconciled:** 2026-11-08 at `311fce7714bbda5d77b581a381c4e19feacdeb8a` (`pyproject.toml` version 0.8.0)
**Prior Receipts:** 343 tools / 60 modules / 3,152 tests passing / 93% coverage are historical, not a current count or test result.
**Current Posture:** Phases 0–7 have shipped deliverables; Phase 8 Network 11 live verification N1–N4 and other discovery items remain open. See `DEVELOPMENT_PLAN.md` §4.9 for the eight-category addendum.

This TODO mirrors `DEVELOPMENT_PLAN.md` and tracks the work that is still open in the repo.

## Using this backlog

### Objective

Keep the live backlog actionable and phase-aligned so operators and contributors know what is genuinely next.

### Prerequisites

- You know the current development phase.
- You have the supporting roadmap or runbook for the item you are updating.

### Procedure

1. Move items between phase buckets only when the phase boundary changes.
2. Keep completed items short and factual.
3. When a phase item becomes operator-facing, add or refresh the matching runbook.
4. Reconcile the TODO with the development plan after every meaningful update.

### Verification

- Active work matches the phase plan.
- Completed work is not re-labeled as active.
- The backlog can be read without guessing the current release posture.

### Rollback

- If the TODO drifts, restore the phase bucket and status markers before making further edits.

### Common failure modes

- Letting the backlog become a duplicate roadmap.
- Marking phase work complete before the implementation is actually shipped.
- Leaving stale maintenance items active after they are already folded into another doc.

---

## Active work

### Phase 3 — Protect API integration (complete)

- [x] Implement `src/api/protect_client.py` (scaffolded; wired for local/Cloud path prefixes)
- [x] Add Protect models under `src/models/protect_*.py` (ProtectCamera, ProtectNVR)
- [x] Add camera tools (`src/tools/protect_cameras.py`) (list, get)
- [x] Add Protect device tools (`src/tools/protect_devices.py`)
- [x] Add NVR / asset tools (`src/tools/protect_nvr.py`) (list, get)
- [x] Add live view / viewer tools (`src/tools/protect_views.py`)
- [x] Add Protect events / webhook tools (`src/tools/protect_events.py`)
- [x] Add Protect MCP resources (`src/resources/protect.py`) (nvrs, cameras resource URIs)
- [x] Build mocked integration tests for Protect (completed 2026-08-12)
- [x] Update `API.md` and `UNIFI_API.md` with Protect coverage (completed 2026-08-12)
- [x] Wire exports, runtime profile, and config helper for Protect (completed 2026-07-19)

### Phase 4 — Testing, polish, minor gaps, developer experience

- [x] Add tests for all new Phase 1–3 modules (2026-10-10: every module at 80%+)
- [x] Close remaining minor gaps: Dynamic DNS full CRUD
- [x] Close remaining minor gaps: Tagged MAC management (`src/tools/mac_tags.py`)
- [x] Close remaining minor gaps: Device migration tools (`src/tools/device_migration.py`)
- [x] Fix "Received request before initialization was complete" (issue #96: closed; raised inside the `mcp` SDK's SSE transport, workaround is `MCP_SERVER_TRANSPORT=streamable_http`)
- [x] Add `NETWORK_PLAYBOOK.md` runbook library
- [x] Add `skills/` domain knowledge packs (channel planning, devices, network, security, system)
- [x] Add `docker-compose.yml` and `HARBOR_SETUP.md`
- [x] Add `Makefile` (`make help` lists targets; `make ci` mirrors the blocking CI jobs)
- [x] Synchronize README, API.md, UNIFI_API.md, and CHANGELOG.md (2026-09-27; tool and test counts refreshed 2026-10-10)
- [x] Prepare release prep notes and version bump (v0.5.0 tagged 2026-09-28; v0.6.0 released 2026-10-12, v0.6.1 2026-10-14, v0.7.0 2026-10-29, see `DEVELOPMENT_PLAN.md` §5)
- [x] Fix the webhook receiver (2026-10-10: Starlette endpoint instead of the undeclared `fastapi`, `WEBHOOK_SECRET` read into `Settings`, fails closed without it, real 401/429 responses)
- [x] Mount `POST /webhooks/unifi` on network transports when `WEBHOOK_SECRET` is set (`register_webhook_route` in `src/main.py`)

### Phase 5 — Enterprise scale & operational excellence

- [x] Add multi-controller / multi-site orchestration (fleet Phases 0–5: per-call `controller` routing, the Postgres controller registry, a shared connection pool and Redis read cache, several replicas with shared rate limits and registry pub/sub, the worker tier with `fleet_*` read tools and health-driven circuit recovery, drills, SIEM export and retention; cloud-account discovery deferred, `docs/FLEET_SCALING_PLAN.md` §4)
- [x] Add dry-run / change-safe mode (every mutating tool declares `dry_run`, enforced by `test_every_mutating_tool_declares_dry_run`; `UNIFI_DRY_RUN` forces previews server-wide)
- [x] Add tool-level RBAC: roles over risk tiers, server-issued API tokens (fleet Phase 2b: `viewer`/`operator`/`admin`/`fleet-admin` roles, module and controller-label scopes, `umcp_` tokens with `DATABASE_URL`)
- [x] Add append-only audit logging (wrapper-level coverage, HMAC hash chain with `python -m src.utils.audit_verify`, the append-only Postgres store, SIEM export with chain-head anchors (`UNIFI_AUDIT_SIEM_TARGETS`, fleet Phase 5b), and retention: `python -m src.fleet.cli audit-retention` for Postgres, `UNIFI_AUDIT_LOG_ROTATE_MB` plus `python -m src.utils.audit_retention` for the JSONL file (fleet Phase 5c); `docs/FLEET_SCALING_PLAN.md` §3.7)
- [x] Add Prometheus metrics endpoint (`UNIFI_METRICS_ENABLED`: `GET /metrics` on network transports, behind the same bearer token as `/mcp`)
- [x] Add A2A agent card and manifest (`src/a2a/`, `agent-card.json`, served behind bearer auth)
- [x] Add webhook event bus with Redis pub/sub (`src/fleet/bus.py`, `src/webhooks/receiver.py`; see `DEVELOPMENT_PLAN.md:121,318`).
- [ ] Add tool exposure modes for network, protect, access, talk, drive, and read-only sessions (partial: `UNIFI_PROFILE` supports network, devices, security, system, minimal, protect; `UNIFI_READ_ONLY` done; access, talk, drive pending)
- [ ] Research and map the Access API
- [ ] Implement Access API tools once the endpoint map is confirmed

### Phase 7 — Deployment automation (historically shipped; `DEVELOPMENT_PLAN.md` Phase 7)

- [x] Ansible playbook (`deploy/ansible/`) installing the server, Redis and Postgres with Docker, for a single server or a multi-server / clustered inventory with nginx in front; each component optional, secrets from Ansible Vault, migrations run once, least-privilege runtime role, retention cron; syntax-checked in CI
- [x] Unauthenticated `GET /healthz` liveness endpoint for load balancers and container health checks
- [x] Molecule converge-and-idempotence test for the playbook (`deploy/ansible/molecule/default/`; historical CI evidence in `DEVELOPMENT_PLAN.md` Phase 7; fresh run not claimed).
- [x] Helm chart (`deploy/helm/unifi-mcp/`) for Kubernetes: server and worker Deployments, `/healthz` probes, a ServiceMonitor with the bearer token, Redis/Postgres as external endpoints, secrets from an existing Secret, migration Job, retention CronJob
- [x] `-fleet` image variant (the fleet extras) published by the release workflow
- [x] `helm lint` / `helm template`, kubeconform and a kind smoke test (fleet mode against a throwaway Postgres) in CI
- [x] Agent setup prompt: MCP server only (`docs/deploy-prompts/`)
- [x] Agent setup prompt: MCP server with a single Redis and Postgres
- [x] Agent setup prompt: full clustered environment (replicas, workers, Redis and Postgres on a data host, load balancer, SIEM export); HA Redis and Postgres are left to managed services
- [x] Test that the playbook, chart and compose files set the same environment variables (`tests/unit/test_deploy.py`)

---

## Phase 8 eight-category backlog (SPEC.md §8; DEVELOPMENT_PLAN.md §4.9)

Revision basis 311fce7, reconciled 2026-11-08. `[x]` means source exists or historical work is reconciled, not that a controller was tested. The external dashboard's eight gaps remain eight categories; compound items have subtasks without changing the denominator. `docs/COMPETITOR_GAP_RECONCILIATION.md` holds the evidence table and discovery requests.

- [x] CG-8a Source implemented: existing `list_sdwan_configs`, `get_sdwan_config`, `get_sdwan_config_status` (#292); initial PDF's absence claim corrected. Local request/response repair has red regression witnesses and 115 focused passing tests. The final full-suite attempt was not green (an unrelated Redis rate-limit wall-clock bound failed under suite load; its module passed alone); independent review and live verification are separate below.
- [ ] CG-8b Independent reviewer made two read-only passes: first found top-level malformed success, stale examples and synthetic tests; second found nested malformed success and invalid `applyStatus` casing. Both sets have local repairs and focused tests; final independent post-repair review remains pending. Check mode/profile exposure and fleet isolation separately; do not treat self-review as independent (#292).
- [ ] CG-8c Live-verify list/detail/status with a feature-enabled Site Manager read-only account; record exact URL/status, null/empty/error envelopes and sanitized hub/spoke tunnel semantics. Blocked on credentials; mocks passing do not close this task (#292).
- [ ] CG-8d Discover policy fields for destination routing, performance steering, hub priority, WAN priority and thresholds; typed read support only after versioned schema/observations. Authoring blocked on upstream mutation surface and separate approval (#292).
- [ ] CG-6a / CG-1a Discover AP radio and console capture lifecycle/limits on approved hardware with sanitized metadata; blocked on endpoint evidence and explicit capture authorization (#293). No PCAP in repo.
- [ ] CG-1b Separately discover NetFlow/sFlow/IPFIX exporter, supported devices and collector contract; blocked on upstream/device evidence; export activation not approved (#293).
- [ ] CG-7a Discover UPS inventory/battery/health surface and self-test/schedule separately; blocked on model/firmware evidence (#293).
- [ ] CG-7b Discover UPS unit cycle/off, destructive-tier dry-run/audit/recovery requirements; no live power test or action without target approval (#293).
- [x] CG-2a Documentation-only: classic standalone target compatibility distinguished from Network 11 migration and X-API-KEY/path-family endpoint coverage (`docs/NETWORK_11_COMPATIBILITY.md`, `docs/COMPETITOR_GAP_RECONCILIATION.md`). Explicit operator metadata is not autodetection; no runtime compatibility claim (#293 adjacent).
- [ ] CG-2b Verify standalone X-API-KEY and legacy/v2/Integration paths on approved classic instance; blocked on credentials/hardware; retain unknown where detection is inconclusive. Network 11 N1–N4 live follow-up remains open independently.
- [ ] CG-3 Matter: review next official Network/version-local spec and approved UI evidence; blocked on upstream surface (#293).
- [ ] CG-4 Thread: separately review border-router/node surface, sharing IoT discovery where safe; blocked on upstream surface (#293).
- [ ] CG-5 Time Machine: discover historical topology endpoint and retention semantics; local snapshots are not feature parity; blocked on upstream surface (#293).
- [ ] Preserve #290 bulk client/alarm filtering and #291 URL-sourced Network Lists as separate open work; neither is closed by this matrix.

---

## Ongoing maintenance

- [ ] Keep `README.md` aligned with the current codebase
- [ ] Keep `ROADMAP.md` aligned with `DEVELOPMENT_PLAN.md`
- [ ] Keep `docs/RELEASE_PROCESS.md` aligned with the current release flow
- [ ] Keep `docs/SKILLS.md` aligned with current tool counts and profiles
- [ ] Keep `API.md` and `UNIFI_API.md` synchronized with implementation changes
- [ ] Run `git diff --check` on doc-only syncs before merge

---

## Completed phases

- [x] Phase 0 — Documentation accuracy and housekeeping
- [x] Phase 1 — Network API completion
- [x] Phase 2 — Site Manager API completion
- [x] Phase 3 — Protect API integration
