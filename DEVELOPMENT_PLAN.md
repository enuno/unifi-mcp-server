# UniFi MCP Server Development Plan

**Document Version:** 2026-09-24
**Source Plan:** `~/INTEGRATION/Unifi-Evolution.md`
**Repository Baseline:** 275 MCP tools registered in local mode across 47 tool modules; 2,240 unit tests passing
**Current Phase:** Phase 4 (Phases 0–3 complete; Phase 5 partially started)

---

## 1. Executive Summary

This plan defines the path from the current UniFi Network-centric server to a production-grade, multi-domain MCP platform with Protect, Access, and enterprise-scale operational controls.

The roadmap preserves the current Network and Site Manager baseline while adding the following strategic capabilities:

- native Protect API coverage
- Access API expansion
- multi-controller / multi-site orchestration
- dry-run / change-safe execution
- tool-level RBAC
- append-only audit logging
- Prometheus metrics
- A2A agent discovery
- webhook-driven event bus
- task-specific tool exposure profiles
- AI-readable runbooks and domain skills
- standardized developer workflow and registry support

## 1.1 Operator guidance

### Objective

Describe how to execute the plan without losing sight of the current production baseline.

### Prerequisites

- You know the current stable release and the current development phase.
- You can distinguish implemented baseline, planned gap, and post-phase aspiration.
- You have the companion runbooks for the phase you are touching.

### Procedure

1. Verify the current state in the implementation tables before updating any phase language.
2. Update the narrowest phase that covers the requested work.
3. Keep deliverables, scope, and exit criteria aligned across this plan, the roadmap, and the gap report.
4. If a phase introduces operator-facing behavior, add or update the supporting runbook at the same time.
5. Re-read the affected section after editing to ensure the phase story still reads linearly.

### Verification

- The current state table still matches the repo.
- Each phase has a clear goal, deliverables, and exit criteria.
- New operator behavior is documented in a supporting runbook.

### Rollback

- If a change broadens or narrows scope incorrectly, revert the affected phase paragraph/table and restate the boundary cleanly.

### Common failure modes

- Mixing aspirational work into the implemented baseline table.
- Moving one phase forward without updating the roadmap or gap report.
- Describing supporting docs as optional when the operator workflow depends on them.

---

## 2. Current State

### 2.1 Implemented baseline

| Area | Status | Notes |
|---|---:|---|
| Devices | Complete | CRUD, adoption, port actions, statistics, pending devices |
| Clients | Complete | List, details, search, block/unblock, reconnect, DPI |
| Networks | Complete | VLANs, WAN, corporate, VPN networks; full CRUD |
| WiFi / WLANs | Complete | SSID CRUD, statistics, radio config |
| Firewall Zones | Complete | Zone CRUD, assignment, network references |
| Firewall Policies | Complete | Policy CRUD via v2 API |
| ACL Rules | Complete | CRUD and ordering |
| Firewall Groups | Complete | Address and port group CRUD |
| Traffic Flows | Complete | Real-time flows with documented 50-flow cap |
| DPI | Complete | Statistics, top applications, client DPI |
| QoS / Traffic Routes | Partial | Smart Queue read/configure; Traffic Routes read-only from the v2 endpoint (write tools removed in #178 until verified on hardware) |
| Traffic Matching Lists | Complete | CRUD |
| Port Forwarding | Complete | CRUD |
| Port Profiles | Complete | Profile CRUD and device port overrides |
| Switching | Complete | Stacks, MC-LAG, LAGs |
| RADIUS | Complete | Profile CRUD, account CRUD |
| Guest Portal / Hotspot | Complete | Portal config, packages, vouchers |
| Backups | Complete | Trigger, list, download, delete, restore, schedule, status |
| Topology | Complete | Graph data, connections, exports |
| Site VPN | Complete | Site-to-site tunnels, server list |
| WAN / DNS | Complete | Connections, DNS, content filtering |
| DHCP Reservations | Complete | CRUD |
| Site Manager | Partial | Aggregated sites, health, inventory, ISP metrics, SD-WAN read, hosts, version control |
| Device Control | Complete | Upgrade, restart, locate, LED |
| Cloud Connector | Complete | Network and Protect proxy tools |
| Diagnostics | Complete | Speed test, spectrum scan, historical stats |
| Events / Alarms | Complete | Controller events, alarms, neighboring APs |
| Dynamic DNS | Complete | Full CRUD |
| Tagged MACs | Complete | Device tag CRUD on legacy `rest/tag` (local only) |
| Device Migration | Complete | Move between sites (`move-device`), migrate to another controller (`migrate` / `cancel-migrate`); local only |
| Protect | Complete | Cameras, devices, NVR, views, events; MCP resources; mocked integration tests |
| A2A | Complete | Agent card, discovery, delegation, playbooks; `/a2a/*` served behind bearer auth |
| Access controls | Partial | Bearer auth on network transports, `UNIFI_READ_ONLY`, `UNIFI_PROFILE` (network, devices, security, system, minimal, protect), `confirm=True` on all write tools |
| Audit logging | Partial | JSONL append-mode log with credential redaction and 0600 permissions; encryption / tamper evidence open (issue #22) |

### 2.2 Known limitations

- Traffic flow historical trends and streaming are not feasible under the current v2 cap and remain documented as unsupported.
- Traffic Route writes are not available until the v2 write path is verified on real hardware.
- Access API is not yet implemented.
- Multi-controller orchestration is not yet implemented (runbook only).
- Prometheus metrics and the Redis webhook event bus are not yet implemented (runbooks only).
- Dry-run covers 32 of 47 tool modules and is not enforced in CI; per-tool RBAC scopes do not exist yet.
- Tool profiles exist for network, devices, security, system, minimal, and protect; access, talk, and drive profiles are pending.

---

## 3. Gap taxonomy

### 3.1 Critical functional gaps

| ID | Gap | Priority | Outcome |
|---|---|---:|---|
| G1 | Protect API | Highest | Native camera, NVR, viewer, event, and device support |
| G2 | Access API | Highest | Doors, credentials, visitors, and policy support |
| G3 | Multi-controller orchestration | Highest | Single-server fleet operations across controllers |

### 3.2 Platform gaps

| ID | Gap | Priority | Outcome |
|---|---|---:|---|
| P1 | Dry-run / change-safe mode | High | Preview write actions before execution |
| P2 | Tool-level RBAC | High | Scope tool access by API key |
| P3 | Append-only audit log | High | Trace every write/destructive operation |
| P4 | Prometheus metrics | High | Observe server and tool health |
| P5 | A2A agent card | Medium | Enable machine-readable discovery |
| P6 | Webhook event bus | Medium | Convert webhooks into normalized events |
| P7 | Tool exposure profiles | Medium | Reduce context-window bloat |
| P8 | AI skills / runbooks | Medium | Give agents reusable operational knowledge |
| P9 | Developer workflow standardization | Medium | Make local dev, build, and release consistent |

---

## 4. Phased implementation plan

### Phase 3: Protect API integration (complete)

**Goal:** deliver native Protect coverage on top of the existing Network and Site Manager foundation.

#### Deliverables

- `src/api/protect_client.py`
- Protect models under `src/models/protect_*.py`
- Tool modules for cameras, devices, NVR, views, and events
- Protect MCP resources for cameras and events
- Integration tests with mocked Protect responses and client/tool/resource coverage (completed 2026-08-12)
- API and UniFi endpoint docs updated for Protect (completed 2026-08-12)

#### Scope

- cameras: list, get, update, snapshot, stream, talkback, PTZ
- lights, sensors, chimes
- NVR details and device asset files
- live views and viewer settings
- Protect events and alarm webhooks
- device update messages

#### Exit criteria

- Protect tool coverage matches the documented endpoint set
- Tests cover new models and response shapes
- Documentation clearly separates implemented vs planned surfaces

---

### Phase 4: Testing, polish, minor gaps, and developer experience (active)

**Goal:** harden the server, close remaining small gaps, and ship AI-friendly operational assets.

#### Deliverables

- Full test coverage for new Phase 1–3 modules — in progress
- Dynamic DNS full CRUD — done
- Tagged MAC management — done
- Device migration tools — done
- `NETWORK_PLAYBOOK.md` runbook library — done
- `skills/` domain knowledge packs — done
- `docker-compose.yml` and `HARBOR_SETUP.md` — done; `Makefile` — open
- Documentation synchronization across README, API, UNIFI_API, and changelog — open

#### Exit criteria

- Coverage target reached and stable
- Developer workflow is standardized
- Docs reflect the implemented feature set

---

### Phase 5: Enterprise scale and operational excellence (partially started)

**Goal:** turn the server into a multi-site, multi-team operating platform with strong safety and observability controls.

#### Deliverables

- Multi-controller / multi-site orchestration — open (runbook only)
- Dry-run / change-safe mode — partial
- Tool-level RBAC via API key scopes — partial (transport-level bearer auth only)
- Append-only audit log — partial (issue #22 open)
- Prometheus metrics endpoint — open (runbook only)
- A2A agent card and manifest — done
- Webhook event bus with Redis pub/sub — partial (receiver only)
- Tool exposure profiles for network, protect, access, talk, drive, and read-only sessions — partial (read-only and protect done)
- Access API implementation — open

#### Exit criteria

- Multi-controller routing is isolated and testable
- Write operations are previewable, auditable, and scoped
- Metrics and logs are first-class operational outputs
- Named tool profiles keep per-session context bounded
- Access domain coverage is documented and implemented

---

## 5. Version roadmap

| Version | Scope | Notes |
|---|---|---|
| v0.2.5 | Current package version | `pyproject.toml` version on `main` |
| v0.3.0 | Phases 0–2 completion | Shipped on `main`; never tagged or version-bumped |
| v0.4.0 | Phase 3 | Protect API integration; `CHANGELOG.md` has a `[0.4.0]` section, but no tag or version bump exists |
| v0.5.0 | Phase 4 | Testing, polish, minor gaps, developer experience |
| v1.0.0 | Phase 5 | Enterprise scale & operational excellence |
| v1.1.0+ | Post-Phase 5 | Access expansion and follow-on domains |

---

> **Release versioning needs reconciling before the next release.** `main` still declares 0.2.5, a `v0.2.6` tag exists on a commit that is not on `main`, and `CHANGELOG.md` has a `[0.4.0]` heading with no matching tag. Phase 4 release prep has to pick the next version number and fold the `[0.4.0]` and `[Unreleased]` entries into it.

## 6. Required downstream docs

After each phase, keep these synchronized:

- `README.md`
- `API.md`
- `docs/UNIFI_API.md`
- `CHANGELOG.md`
- `GAP_REPORT.md`
- `TEST_STRATEGY.md`
- `RELEASE_CHECKLIST.md`
- `MAINTENANCE_POLICY.md`
- `ROADMAP.md`

New documents introduced by the roadmap:

- `SPEC.md`
- `NETWORK_PLAYBOOK.md`
- `HARBOR_SETUP.md`
- `MULTI_CONTROLLER.md`
- `METRICS.md`
- `WEBHOOK_SETUP.md`
- `A2A.md`
- `agent-card.json`

---

## 7. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Protect endpoints differ from docs | Medium | High | Verify against live hardware early |
| Multi-controller context leaks | Medium | High | Enforce async context isolation and tests |
| Dry-run interception is inconsistent | Medium | Medium | Decorator-based enforcement and CI checks |
| Redis unavailable for webhook bus | Low | Medium | Graceful single-instance fallback |
| RBAC misconfiguration grants too much access | Low | High | Default deny and explicit scope mapping |
| Metrics cardinality grows too large | Low | Medium | Cap label cardinality and keep labels stable |
| API/documentation drift returns | Medium | Medium | Phase gates require docs and implementation sync |

---

## 8. Maintenance rule

The development plan is not complete until documentation and implementation tell the same story. When a new capability is added, update the spec, roadmap, endpoint docs, and test strategy in the same change set.
