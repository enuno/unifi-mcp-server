# Gap Report — UniFi MCP Server

This report tracks the remaining work implied by the current evolution plan. It should be read alongside `SPEC.md` and `DEVELOPMENT_PLAN.md`.

## Executive summary

The current server has native Network, Protect (v6 and v7.3.68), Mobility, InnerSpace and Carrier Fabric coverage, RBAC, audit logging, Prometheus metrics, a webhook event bus and A2A discovery. The remaining material gap is:

- Access API support — **blocked**: no official spec published as of 2026-09-26
- API-spec alignment: keep docs and pins current against Network v10.6.106 / Protect v7.3.68 with the repeatable audit workflow, and track the Network 11 / UniFi OS 6 compatibility work (DEVELOPMENT_PLAN.md Phase 8)

## Operator handling

### Objective

Turn the gap list into a working queue that can be triaged, verified, and closed without losing track of phase dependencies.

### Prerequisites

- You know which phase owns the gap.
- You have the current implementation baseline in `DEVELOPMENT_PLAN.md`.
- You can tell product gaps from platform and developer-experience gaps.

### Procedure

1. Identify the gap category and phase owner.
2. Confirm whether the gap is a documentation mismatch, a test gap, or a missing implementation.
3. Update the appropriate source of truth first: code, then tests, then docs.
4. Reconfirm the success criteria after the fix lands.
5. Keep any unresolved gap explicitly labeled as open and in the right phase bucket.

### Verification

- The gap still exists, or the gap report has been updated to show closure.
- Phase ownership is unambiguous.
- The report no longer overstates implemented coverage.

### Rollback

- If a gap was misclassified, move it back to the correct bucket before the next implementation pass.

### Common failure modes

- Treating a docs fix as implementation closure.
- Letting the report drift from the roadmap phase numbering.
- Hiding unresolved work inside generic “platform” language.

## Gap categories

### 1. Product gaps

| ID | Gap | Priority | Phase |
|---|---|---:|
| G1 | Protect API | Done | 3 (v6) / 5a (v7.3.68, 39 ops) |
| G2 | Access API | Highest | 5+ — blocked: no official spec published as of 2026-09-26 |
| G3 | Multi-controller orchestration | Done | 5 (fleet Phases 0–5) |
| G4 | Protect v7 expansion | Done | 5a |
| G5 | Mobility API | Done | 6 |
| G6 | InnerSpace API | Done | 6 |
| G7 | Carrier Fabric API | Done | 6 |

### 2. Safety and governance gaps

| ID | Gap | Priority | Phase |
|---|---|---:|
| G8 | Dry-run / change-safe mode | Partial | 5 |
| G9 | Tool-level RBAC | Done (static and fleet-issued tokens) | 5 |
| G10 | Append-only audit log | Done | 5 |

### 3. Observability and platform gaps

| ID | Gap | Priority | Phase |
|---|---|---:|
| G11 | Prometheus metrics endpoint | Done | 5 |
| G12 | Webhook event bus | Done | 5.5 |
| G13 | A2A agent card / manifest | Done | 5 |
| G14 | Tool exposure profiles | Partial (network, devices, security, system, minimal, protect done; access, talk, drive pending) | 5 |

### 4. Developer-experience gaps

| ID | Gap | Priority | Phase |
|---|---|---:|
| G15 | AI runbook library | Medium | 4 |
| G16 | Domain skills packs | Medium | 4 |
| G17 | Harbor / Makefile workflow docs | Medium | 4 |

## Endpoint and domain notes

### Implemented baseline

- Network, switching, firewall, QoS, topology, backup, and Site Manager foundations exist.
- Network Integration API docs are verified against the v10.6.106 spec (73/73 operations covered; endpoint-stable since v10.3.55).
- Protect surface is native through v7.3.68 (cameras, devices, NVR, views, events, arm profiles/alarm control, sirens, speakers, fobs, relays, bridges, link stations, alarm hubs, users, POS ingestion); write paths await hardware verification.
- Mobility, InnerSpace and Carrier Fabric (Phase 6) are implemented and mock-tested over the Site Manager client and Cloud Connector proxy.
- Fleet (multi-controller orchestration), RBAC (static and fleet-issued token roles), append-only audit logging, Prometheus metrics, the Redis webhook event bus, and A2A discovery/delegation are implemented — see DEVELOPMENT_PLAN.md §2.1.
- Traffic-flow historical streaming remains constrained by the current API cap and should stay documented as unsupported.

### Planned next work

- Access endpoint mapping and model coverage — blocked until Ubiquiti publishes a spec
- Dry-run / change-safe mode: extend preview coverage to every write tool (currently partial)
- Remaining tool exposure profiles: access, talk, drive
- UniFi Network 11 / UniFi OS 6 compatibility verification on a live controller (DEVELOPMENT_PLAN.md Phase 8; four items cannot be settled from documentation alone)
- spec-drift guardrail: pinned spec snapshots + quarterly re-audit against developer.ui.com

## Success criteria

This report is considered closed when:

- Access work is mapped and queued — or confirmed still blocked by the absence of an official spec.
- Every write tool is previewable under `dry_run` (not just a subset).
- The four Network 11 "needs live controller test" items (DEVELOPMENT_PLAN.md §2.4) are resolved on a real UniFi OS 6 / Network 11 controller.
