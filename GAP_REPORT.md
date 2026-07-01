# Gap Report — UniFi MCP Server

This report tracks the remaining work implied by the current evolution plan. It should be read alongside `SPEC.md` and `DEVELOPMENT_PLAN.md`.

## Executive summary

The current server is strong on UniFi Network coverage, but the next material gaps are:

- native Protect support
- Access API support
- multi-controller orchestration
- safety and governance controls for write operations
- first-class observability and eventing

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
|---|---|---:|---|
| G1 | Protect API | Highest | 3 |
| G2 | Access API | Highest | 5+ |
| G3 | Multi-controller orchestration | Highest | 5 |

### 2. Safety and governance gaps

| ID | Gap | Priority | Phase |
|---|---|---:|---|
| G4 | Dry-run / change-safe mode | High | 5 |
| G5 | Tool-level RBAC | High | 5 |
| G6 | Append-only audit log | High | 5 |

### 3. Observability and platform gaps

| ID | Gap | Priority | Phase |
|---|---|---:|---|
| G7 | Prometheus metrics endpoint | High | 5 |
| G8 | Webhook event bus | Medium | 5 |
| G9 | A2A agent card / manifest | Medium | 5 |
| G10 | Tool exposure profiles | Medium | 5 |

### 4. Developer-experience gaps

| ID | Gap | Priority | Phase |
|---|---|---:|---|
| G11 | AI runbook library | Medium | 4 |
| G12 | Domain skills packs | Medium | 4 |
| G13 | Harbor / Makefile workflow docs | Medium | 4 |

## Endpoint and domain notes

### Implemented baseline

- Network, switching, firewall, QoS, topology, backup, and Site Manager foundations exist.
- Traffic-flow historical streaming remains constrained by the current API cap and should stay documented as unsupported.

### Planned next work

- Protect native endpoint mapping and model coverage
- Access endpoint mapping and model coverage
- controller-specific routing and fleet query operations
- change-safe wrappers for all writes
- metrics, audit, and webhook event handling

## Success criteria

This report is considered closed when:

- Protect coverage is documented and implemented natively.
- Access work is mapped and queued behind Protect and platform safety work.
- write operations are previewable, auditable, and access-scoped.
- the docs no longer imply a single-controller-only architecture.
