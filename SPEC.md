# UniFi MCP Server Specification

Version: reconciled 2026-11-08 against `311fce7714bbda5d77b581a381c4e19feacdeb8a` (`pyproject.toml` version 0.8.0).
Historical input: `~/INTEGRATION/Unifi-Evolution.md` (not present at reconciliation; not the sole practical source of truth). Current requirements are grounded in this repository's code, tests, `DEVELOPMENT_PLAN.md`, `docs/UNIFI_API.md`, the dated matrix at `/home/elvis/inbox/UniFi competitor-to-gap matrix.pdf`, and the official Site Manager v1.0.0 OpenAPI. See `docs/COMPETITOR_GAP_RECONCILIATION.md` for source-scoped evidence.

## 1. Purpose

UniFi MCP Server is a Model Context Protocol server for operating UniFi environments through AI agents and MCP clients. It exposes a disciplined, auditable tool surface for Network today, then expands into Protect, Access, and enterprise-scale orchestration controls.

The specification emphasizes four outcomes:

1. Broad UniFi API coverage.
2. Safe operational change handling.
3. Multi-controller / multi-site scale.
4. Strong documentation and drift control.

## 2. Product principles

- Security first: default-deny, least privilege, auditability, secret hygiene.
- Change safety first: every write path must be previewable, scoped, and traceable.
- Scale without context bloat: expose smaller task-specific tool surfaces where possible.
- Reality over hype: only document or ship features that have a clear operational model.
- Keep docs and implementation synchronized.

## 3. Current baseline

Implemented baseline at the cited revision, subject to live-controller verification:

- Network and Protect tool families are registered (`src/main.py:580-846`); Protect writes still need hardware validation (`DEVELOPMENT_PLAN.md:108`).
- Site Manager has three SD-WAN config/status read tools (`src/tools/site_manager.py:647-726`), not typed Site Manager policy authoring. The 2026-11-08 reconciliation identified wrong client paths and synthetic response models; the local repair is tracked separately from live interoperability.
- Fleet routing, tool tiers, read-only mode, audit and selective cache exist (`src/tool_registry.py:308-459`); endpoint availability still depends on mode, profile, service setting and per-controller credentials.
- Traffic flow history/streaming and Network 11 live compatibility remain open (`DEVELOPMENT_PLAN.md:115-123,478-549`).

## 4. Target capability model

### 4.1 Network

Core network operations remain the primary surface:

- devices, clients, networks, WiFi, firewall, ACLs, groups
- traffic flows and DPI
- WAN, DNS, VPN, DHCP, port forwarding
- switching, topology, backups, diagnostics, device control
- Site Manager aggregation where available

### 4.2 Protect

Protect becomes a native first-class domain with support for:

- cameras, snapshots, RTSP/RTSPS streams, PTZ, talkback
- lights, sensors, chimes
- NVR details and device asset files
- live views and viewer settings
- Protect events and alarm webhooks
- device update messages

### 4.3 Access

Access is planned as the next large domain after Protect and platform hardening:

- doors, door groups, devices, visitors
- users, user groups, credentials, NFC cards, pin codes, QR codes, touch passes
- access policies, schedules, holiday groups
- system logs and webhook endpoints

## 5. Platform features

### 5.1 Multi-controller orchestration

The server must support multiple configured UniFi controllers from one MCP instance.

Requirements:

- named controller registry
- session-local active controller context
- fan-out read operations for fleet queries
- controller comparison / diff operations
- no cross-session controller leakage

### 5.2 Change-safe operation

All write and destructive tools must support a preview path.

Requirements:

- dry-run mode via environment variable and/or request parameter
- structured dry-run result containing method, target, payload, and rollback hint
- read-only tools must never be intercepted
- dry-run must work consistently across all tool modules

### 5.3 Tool-level RBAC

Tool access must be scoped by API key permissions.

Scopes:

- read
- write
- destructive
- admin

Requirements:

- default deny for unrecognized keys
- permissions evaluated per tool category
- denied calls return structured permission errors
- a permitted-tools helper must be exposed for discovery

### 5.4 Auditability

All write and destructive operations must be recorded in an append-only audit trail.

Requirements:

- timestamp, session id, API key id, tool name, controller, site, parameters, result, status, duration
- export and query tools for operators
- configurable log path and optional syslog forwarding
- no secrets in logs

### 5.5 Observability

The server should expose Prometheus metrics.

Requirements:

- tool call count and duration
- UniFi API error counts
- cache hit/miss counts
- active session gauge
- controller reachability gauge

### 5.6 A2A discovery

The server should publish an A2A-compatible agent manifest.

Requirements:

- repository-root `agent-card.json`
- `.well-known/agent-card.json` endpoint when HTTP transport is enabled
- manifest includes capabilities, auth schemes, and tool manifest URL

### 5.7 Event bus and webhooks

Webhook events should become normalized internal events and MCP notifications.

Requirements:

- UniFi controller webhook receiver
- Protect alarm webhook receiver
- optional Redis pub/sub fan-out for multi-instance deployments
- event logging and handler registration

### 5.8 Context reduction modes

The server should support named exposure profiles so agents only load relevant tools.

Planned modes:

- network
- protect
- access
- talk
- drive
- read-only

Requirements:

- profiles are declarative
- hidden tools must not be emitted into the active MCP manifest
- profiles are compatible with multi-controller and RBAC

### 5.9 AI operating assets

The project should include AI-readable operational knowledge assets:

- NETWORK_PLAYBOOK.md runbooks
- domain skills packs under `skills/`
- private registry / Harbor deployment documentation
- developer workflow standards via Makefile and compose files

## 6. Documentation contract

The following documents are part of the spec surface and must remain synchronized:

- `README.md`
- `API.md`
- `docs/UNIFI_API.md`
- `DEVELOPMENT_PLAN.md`
- `ROADMAP.md`
- `GAP_REPORT.md`
- `TEST_STRATEGY.md`
- `RELEASE_CHECKLIST.md`
- `MAINTENANCE_POLICY.md`
- `CHANGELOG.md`
- new phase docs such as `MULTI_CONTROLLER.md`, `METRICS.md`, `WEBHOOK_SETUP.md`, `A2A.md`, and `NETWORK_PLAYBOOK.md`

## 7. Acceptance criteria

The roadmap is considered aligned when:

- Protect is fully documented and implemented natively.
- Access is mapped and scheduled as the next domain.
- Multi-controller operation is isolated and testable.
- Dry-run, RBAC, audit, and metrics are documented and covered.
- README, API, UNIFI_API, and roadmap docs tell the same story.
- A new contributor can understand scope and safety model from the docs alone.

## 8. Eight-category competitor-gap contract (2026-11-08)

The eight category IDs below preserve the PDF/dashboard denominator (the external 2026-11-07 snapshot claimed 6 covered / 13 partial / 8 gaps; the dashboard's generation inputs were not available in this checkout). Subitems are not new categories. These are proposed capabilities until the acceptance evidence exists. The PDF describes competitors' *claimed/documented* support, never a live-controller test. See `docs/COMPETITOR_GAP_RECONCILIATION.md` for the dated evidence and discovery package.

| ID | Required outcome and explicit exclusion | Prerequisites / acceptance evidence |
|---|---|---|
| CG-1 console capture + flow export | Distinct packet-capture job/artifact lifecycle and NetFlow/sFlow/IPFIX exporter/collector management; built-in flow records, `reportFlowEnabled`, DPI and port mirroring are not substitutes. | Verified controller/version/protocol, scoped endpoint and permission evidence; limits, privacy/retention, dry-run/confirmation/audit for start/export; no activation without target/destination approval. |
| CG-2 classic standalone target | Truthfully report deployment-target compatibility separately from legacy/v2/Integration endpoint coverage and Network 11 migration. Unknown remains unknown. | Prove X-API-KEY auth and each path family on a specific standalone version; explicit operator metadata is not auto-detection. No session/password auth, prefix stripping, TLS weakening, automatic migration or upgrade. |
| CG-3 Matter | Read-only typed device identity/visibility if a supported surface is documented or observed. | Network version, model, schema, scope and permission; no speculative pairing or handling of pairing codes. |
| CG-4 Thread | Read-only typed nodes/border-router topology if a surface exists. | Same discovery as Matter plus Thread-specific topology semantics; no raw-field-as-support shortcut. |
| CG-5 Time Machine Topology | Expose Ubiquiti historical topology only with a versioned history endpoint and semantics. | Timestamp/range, retention and access evidence; locally stored snapshots are a separate, non-parity proposal. |
| CG-6 AP radio capture | Approved capture start/status/stop/download/cleanup with radio/interface/filter and bounded duration, bytes, concurrency and storage. | Version/device permissions, async lifecycle, timeout/cancel/recovery and sanitized evidence; RF spectrum scan is not PCAP. No start/PCAP transfer without separate approval. |
| CG-7 UPS | Separate inventory/battery/health reads, self-test execution, scheduling, unit cycle and unit off. | Exact UPS model/firmware/permissions and endpoint evidence; destructive cycle/off require explicit target confirmation, dry-run with zero requests, fail-closed audit and recovery plan. PDU and PoE are not UPS. |
| CG-8 Site Manager SD-WAN | Repair existing config list/detail and deployment-status reads; separately establish typed policy *visibility* for destination routing, performance steering, hub selection, WAN priority and loss/latency/jitter thresholds. Policy authoring is a later independently authorized design. | Official v1.0.0 complete URLs, API-key scope, envelopes, optional/unknown fields, 401/403/404/429/error handling, registration across modes/profiles, fleet isolation and live account validation. `applyStatus` is not tunnel health; untyped settings/routes or local Traffic Routes are not policy parity. No guessed mutation path or removed Traffic Route writes. |

For every category, acceptance distinguishes source implemented, tests passing, independent review, and live verification. Missing API credentials/hardware block live validation but not offline regression tests or documentation. Endpoint absence must not be inferred from auth, transport or certificate failures. Discovery uses the existing quarterly spec-drift process (`DEVELOPMENT_PLAN.md` §2.3 and §8), not a new watcher. Any mutating implementation retains `confirm`, real no-request dry-run, risk tier, RBAC and fail-closed audit; sensitive artifacts and secrets never enter this repository. Local mocks cannot establish device interoperability.
