# UniFi MCP Server Specification

Version: 0.4 planning baseline
Source of truth: `~/INTEGRATION/Unifi-Evolution.md`

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

Implemented baseline, as reflected in the existing repository and roadmap:

- UniFi Network coverage is broad and production usable.
- Site Manager support exists in partial form.
- Cloud Connector proxy tools bridge some cross-product access.
- Traffic flow tools have known v2 limitations and should remain documented as such.
- Protect native support is the next major domain gap.

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
