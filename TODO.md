# UniFi MCP Server — Active TODO

**Last Updated:** 2026-10-10
**Current Codebase:** 343 MCP tools registered in local mode across 60 tool modules; 3,152 unit tests passing; 93% line coverage
**Current Posture:** Phase 3 complete; Phase 4 active; Phase 5 partially started (A2A, profiles, read-only mode, audit hardening)

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
- [x] Prepare release prep notes and version bump (v0.5.0 tagged 2026-09-28; v0.6.0 released 2026-10-12, v0.6.1 2026-10-14, see `DEVELOPMENT_PLAN.md` §5)
- [x] Fix the webhook receiver (2026-10-10: Starlette endpoint instead of the undeclared `fastapi`, `WEBHOOK_SECRET` read into `Settings`, fails closed without it, real 401/429 responses)
- [x] Mount `POST /webhooks/unifi` on network transports when `WEBHOOK_SECRET` is set (`register_webhook_route` in `src/main.py`)

### Phase 5 — Enterprise scale & operational excellence

- [x] Add multi-controller / multi-site orchestration (fleet Phases 0–5: per-call `controller` routing, the Postgres controller registry, a shared connection pool and Redis read cache, several replicas with shared rate limits and registry pub/sub, the worker tier with `fleet_*` read tools and health-driven circuit recovery, drills, SIEM export and retention; cloud-account discovery deferred, `docs/FLEET_SCALING_PLAN.md` §4)
- [x] Add dry-run / change-safe mode (every mutating tool declares `dry_run`, enforced by `test_every_mutating_tool_declares_dry_run`; `UNIFI_DRY_RUN` forces previews server-wide)
- [x] Add tool-level RBAC: roles over risk tiers, server-issued API tokens (fleet Phase 2b: `viewer`/`operator`/`admin`/`fleet-admin` roles, module and controller-label scopes, `umcp_` tokens with `DATABASE_URL`)
- [x] Add append-only audit logging (wrapper-level coverage, HMAC hash chain with `python -m src.utils.audit_verify`, the append-only Postgres store, SIEM export with chain-head anchors (`UNIFI_AUDIT_SIEM_TARGETS`, fleet Phase 5b), and retention: `python -m src.fleet.cli audit-retention` for Postgres, `UNIFI_AUDIT_LOG_ROTATE_MB` plus `python -m src.utils.audit_retention` for the JSONL file (fleet Phase 5c); `docs/FLEET_SCALING_PLAN.md` §3.7)
- [x] Add Prometheus metrics endpoint (`UNIFI_METRICS_ENABLED`: `GET /metrics` on network transports, behind the same bearer token as `/mcp`)
- [x] Add A2A agent card and manifest (`src/a2a/`, `agent-card.json`, served behind bearer auth)
- [ ] Add webhook event bus with Redis pub/sub (partial: `src/webhooks/` receiver with signature verification; no Redis fan-out)
- [ ] Add tool exposure modes for network, protect, access, talk, drive, and read-only sessions (partial: `UNIFI_PROFILE` supports network, devices, security, system, minimal, protect; `UNIFI_READ_ONLY` done; access, talk, drive pending)
- [ ] Research and map the Access API
- [ ] Implement Access API tools once the endpoint map is confirmed

### Phase 7 — Deployment automation (done except a molecule test, `DEVELOPMENT_PLAN.md` Phase 7)

- [x] Ansible playbook (`deploy/ansible/`) installing the server, Redis and Postgres with Docker, for a single server or a multi-server / clustered inventory with nginx in front; each component optional, secrets from Ansible Vault, migrations run once, least-privilege runtime role, retention cron; syntax-checked in CI
- [x] Unauthenticated `GET /healthz` liveness endpoint for load balancers and container health checks
- [ ] Molecule (or equivalent) test for the playbook in CI (a converge-and-idempotence run on a Docker-in-Docker host; today CI runs `--syntax-check` and `tests/unit/test_deploy.py`)
- [x] Helm chart (`deploy/helm/unifi-mcp/`) for Kubernetes: server and worker Deployments, `/healthz` probes, a ServiceMonitor with the bearer token, Redis/Postgres as external endpoints, secrets from an existing Secret, migration Job, retention CronJob
- [x] `-fleet` image variant (the fleet extras) published by the release workflow
- [x] `helm lint` / `helm template`, kubeconform and a kind smoke test (fleet mode against a throwaway Postgres) in CI
- [x] Agent setup prompt: MCP server only (`docs/deploy-prompts/`)
- [x] Agent setup prompt: MCP server with a single Redis and Postgres
- [x] Agent setup prompt: full clustered environment (replicas, workers, Redis and Postgres on a data host, load balancer, SIEM export); HA Redis and Postgres are left to managed services
- [x] Test that the playbook, chart and compose files set the same environment variables (`tests/unit/test_deploy.py`)

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
