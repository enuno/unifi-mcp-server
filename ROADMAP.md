# UniFi MCP Server — Roadmap

This roadmap is synchronized with `DEVELOPMENT_PLAN.md` and reflects the current architectural evolution plan.

## Posture

- Phase 3: Protect API integration
- Phase 4: testing, polish, minor gaps, and developer experience
- Phase 5: enterprise scale and operational excellence
- Phase 5+ follow-on: Access expansion and later domains

## How to use this roadmap

### Objective

Keep planning, implementation, and documentation synchronized so phase claims stay tied to the actual repository state.

### Prerequisites

- You have read `SPEC.md` and `DEVELOPMENT_PLAN.md`.
- You know whether you are planning new work, verifying progress, or reconciling drift.

### Procedure

1. Start with the current phase and read its exit criteria.
2. Check the corresponding runbook or support doc before making a change.
3. Use the deliverables list to determine whether a change belongs in code, docs, tests, or release workflow.
4. If a phase is complete, update the version roadmap and any adjacent references together.
5. If a phase is not complete, keep the language explicitly aspirational.

### Verification

- Phase labels match the live repo state.
- Deliverables and exit criteria are consistent with the detailed plan.
- No doc describes future work as shipped work.

### Rollback

- If roadmap text drifts from reality, revert the text first, then re-baseline against the code.

### Common failure modes

- Updating the roadmap in isolation while the development plan still disagrees.
- Promoting a deliverable to complete before the implementation and tests exist.
- Leaving phase labels ambiguous enough that operators cannot tell what is actually ready.

## Phase 3: Protect API integration

Goal: deliver native Protect coverage on top of the existing Network and Site Manager foundations.

### Deliverables

- `src/api/protect_client.py`
- Protect models under `src/models/protect_*.py`
- Tool modules for cameras, devices, NVR, views, and events
- Protect MCP resources for cameras and events
- Integration tests with mocked NVR responses
- Protect documentation updates in `API.md` and `docs/UNIFI_API.md`

### Exit criteria

- Protect tools match the documented endpoint surface
- Tests cover the new models and response shapes
- Docs distinguish implemented Protect support from future Access work

---

## Phase 4: Testing, polish, minor gaps, and developer experience

Goal: harden the server, close the remaining small gaps, and add AI-friendly operational assets.

### Deliverables

- Dynamic DNS full CRUD
- Tagged MAC management
- Device migration tools
- `NETWORK_PLAYBOOK.md`
- `skills/` domain knowledge packs
- `Makefile`, `docker-compose.yml`, and `HARBOR_SETUP.md`
- release and documentation synchronization

### Exit criteria

- Coverage target reached and stable
- Developer workflow is standardized
- Docs reflect the implemented feature set

---

## Phase 5: Enterprise scale and operational excellence

Goal: turn the server into a multi-site, multi-team operating platform with strong safety and observability controls.

### Deliverables

- Multi-controller / multi-site orchestration
- Dry-run / change-safe mode
- Tool-level RBAC via API key scopes
- Append-only audit log
- Prometheus metrics endpoint
- A2A agent card and manifest
- Webhook event bus with Redis pub/sub
- Tool exposure profiles for network, protect, access, talk, drive, and read-only sessions
- Access API implementation

### Exit criteria

- Multi-controller routing is isolated and testable
- Write operations are previewable, auditable, and scoped
- Server observability is first-class
- Named tool exposure modes keep per-session tool lists small and task-relevant
- Access domain is mapped and scheduled into implementation

---

## Version roadmap

| Version | Scope | Notes |
|---|---|---|
| v0.2.5 | Current stable release | Baseline release artifact |
| v0.3.0 | Phases 0–2 completion | Docs sync, Network refs, connector foundation |
| v0.4.0 | Phase 3 | Protect API integration |
| v0.5.0 | Phase 4 | Testing, polish, minor gaps, developer experience |
| v1.0.0 | Phase 5 | Enterprise scale and operational excellence |
| v1.1.0+ | Post-Phase 5 | Access expansion and later product domains |
