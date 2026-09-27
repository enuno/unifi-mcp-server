# Gap Report — UniFi MCP Server

This report tracks the remaining work implied by the current evolution plan. It should be read alongside `SPEC.md` and `DEVELOPMENT_PLAN.md`.

## Executive summary

The current server is strong on UniFi Network coverage, but the next material gaps are:

- Protect v7 expansion — v6 surface is native; v7.3.68 added 39 unmapped operations (arm profiles/alarm control, sirens, speakers, fobs, relays, bridges, link stations, alarm hubs, users, POS ingestion)
- Access API support — **blocked**: no official spec published as of 2026-09-26
- multi-controller orchestration
- safety and governance controls for write operations
- first-class observability and eventing
- new API domains: Mobility v1.0.0, InnerSpace v1.3.23, Carrier Fabric v1.0.0 (Phase 6)
- API-spec alignment: docs and pins refreshed to Network v10.6.106 / Protect v7.3.68 with a repeatable audit workflow

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
| G1 | Protect API | Highest | 3 (v6 done) / 5a (v7 expansion) |
| G2 | Access API | Highest | 5+ — blocked: no official spec published as of 2026-09-26 |
| G3 | Multi-controller orchestration | Highest | 5 |
| G4 | Protect v7 expansion | High | 5a |
| G5 | Mobility API | Medium | 6 |
| G6 | InnerSpace API | Medium | 6 |
| G7 | Carrier Fabric API | Medium | 6 |

### 2. Safety and governance gaps

| ID | Gap | Priority | Phase |
|---|---|---:|
| G8 | Dry-run / change-safe mode | High | 5 |
| G9 | Tool-level RBAC | High | 5 |
| G10 | Append-only audit log | High | 5 |

### 3. Observability and platform gaps

| ID | Gap | Priority | Phase |
|---|---|---:|
| G11 | Prometheus metrics endpoint | High | 5 |
| G12 | Webhook event bus | Medium | 5 |
| G13 | A2A agent card / manifest | Medium | 5 |
| G14 | Tool exposure profiles | Medium | 5 |

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
- Protect v6-era surface (cameras, devices, NVR, views, events) exists.
- Traffic-flow historical streaming remains constrained by the current API cap and should stay documented as unsupported.

### Planned next work

- Protect v7 expansion: 39 new operations (arm profiles/alarm control, sirens, speakers, fobs, relays, bridges, link stations, alarm hubs, users, POS ingestion)
- New API domains: Mobility (8 ops), InnerSpace (6 ops, Cloud Connector proxy), Carrier Fabric (11 ops, subscriber management)
- Access endpoint mapping and model coverage — blocked until Ubiquiti publishes a spec
- controller-specific routing and fleet query operations
- change-safe wrappers for all writes
- metrics, audit, and webhook event handling
- spec-drift guardrail: pinned spec snapshots + quarterly re-audit against developer.ui.com

## Success criteria

This report is considered closed when:

- Protect coverage matches spec v7.3.68 (all 74 operations implemented or explicitly out-of-scope).
- Mobility, InnerSpace, and Carrier Fabric domains are implemented or explicitly deferred with specs pinned.
- Access work is mapped and queued — or confirmed still blocked by the absence of an official spec.
- write operations are previewable, auditable, and access-scoped.
- the docs no longer imply a single-controller-only architecture.
