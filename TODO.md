# UniFi MCP Server — Active TODO

**Last Updated:** 2026-09-24
**Current Codebase:** 267 MCP tools registered in local mode across 45 tool modules; 2,158 unit tests passing
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

- [ ] Add tests for all new Phase 1–3 modules (suite is at 2,158 tests; per-module coverage gaps still need measuring against the 80% target)
- [x] Close remaining minor gaps: Dynamic DNS full CRUD
- [ ] Close remaining minor gaps: Tagged MAC management
- [ ] Close remaining minor gaps: Device migration tools
- [ ] Fix "Received request before initialization was complete" (issue #96)
- [x] Add `NETWORK_PLAYBOOK.md` runbook library
- [x] Add `skills/` domain knowledge packs (channel planning, devices, network, security, system)
- [x] Add `docker-compose.yml` and `HARBOR_SETUP.md`
- [ ] Add `Makefile`
- [ ] Synchronize README, API.md, UNIFI_API.md, and CHANGELOG.md
- [ ] Prepare release prep notes and version bump

### Phase 5 — Enterprise scale & operational excellence

- [ ] Add multi-controller / multi-site orchestration (runbook only: `MULTI_CONTROLLER.md`)
- [ ] Add dry-run / change-safe mode (partial: `dry_run` exists in 31 of 48 tool modules; not yet universal or enforced in CI)
- [ ] Add tool-level RBAC via API key scopes (partial: bearer auth required on network transports and `/a2a/*`; no per-tool scopes)
- [ ] Add append-only audit logging (partial: `src/utils/audit.py` appends JSONL with credential redaction and 0600 permissions; encryption / tamper evidence tracked in issue #22)
- [ ] Add Prometheus metrics endpoint (runbook only: `METRICS.md`)
- [x] Add A2A agent card and manifest (`src/a2a/`, `agent-card.json`, served behind bearer auth)
- [ ] Add webhook event bus with Redis pub/sub (partial: `src/webhooks/` receiver with signature verification; no Redis fan-out)
- [ ] Add tool exposure modes for network, protect, access, talk, drive, and read-only sessions (partial: `UNIFI_PROFILE` supports network, devices, security, system, minimal, protect; `UNIFI_READ_ONLY` done; access, talk, drive pending)
- [ ] Research and map the Access API
- [ ] Implement Access API tools once the endpoint map is confirmed

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
