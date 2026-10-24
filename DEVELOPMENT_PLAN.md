# UniFi MCP Server Development Plan

**Document Version:** 2026-10-24
**Source Plan:** `~/INTEGRATION/Unifi-Evolution.md`
**Repository Baseline:** 343 MCP tools registered in local mode across 60 tool modules; 3,152 unit tests passing; 93% line coverage
**API Spec Baseline** (audited 2026-09-26): UniFi Network **v10.6.106**, UniFi Protect **v7.3.68**, Site Manager v1.0.0; newly published: Mobility v1.0.0, InnerSpace v1.3.23, Carrier Fabric v1.0.0 (artifacts in `scripts/`)
**Release Target Baseline** (audited 2026-10-22, §2.4): UniFi Network **v11.0.83** (requires UniFi OS **6.0.10+**) and UniFi OS **6** — compatible per released documentation, with two platform-level breaks and four items still pending live-controller verification
**Current Phase:** Phase 4 (Phases 0–3 complete; Phase 5 partially started; API-spec alignment wave in progress) · Phase 8 planned (Network 11 / UniFi OS 6 compatibility, §4 Phase 8)

---

## 1. Executive Summary

This plan defines the path from the current UniFi Network-centric server to a production-grade, multi-domain MCP platform with Protect, Access, and enterprise-scale operational controls.

The roadmap preserves the current Network and Site Manager baseline while adding the following strategic capabilities:

- native Protect API coverage — v6-era surface complete; **v7.3.68 expansion outstanding** (39 new operations, §2.3)
- API-spec alignment: codebase and docs pinned to current official specs (Network v10.6.106, Protect v7.3.68) with a repeatable diff/audit workflow
- UniFi Network 11 / UniFi OS 6 compatibility — **planned, not yet started** (Phase 8, §4): compatible per released documentation, with two platform-level breaks (USG gateways, the standalone Network Application Server) and four items that still need a live-controller test before "full support" can be claimed
- Access API expansion — **blocked** (no official spec published as of 2026-09-26)
- multi-controller / multi-site orchestration
- dry-run / change-safe execution
- tool-level RBAC
- append-only audit logging
- Prometheus metrics
- A2A agent discovery
- webhook-driven event bus
- task-specific tool exposure profiles
- new API domains: Mobility, InnerSpace, Carrier Fabric (Phase 6, §4.6)
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
| Protect | Complete (v7.3.68, mock-tested) | Cameras, devices, NVR, views, events, MCP resources, plus the v7 surface (Phase 5a): arm profiles/alarm control, sirens, speakers, fobs, relays, bridges, link stations, alarm hubs, users, POS ingestion. Write paths await hardware verification |
| Mobility / InnerSpace / Carrier Fabric | Complete (mock-tested) | Phase 6: 8 + 6 + 11 tools over the Site Manager client and Cloud Connector proxy |
| Fleet | Complete | Per-call `controller` routing, Postgres controller registry, shared connection pool, Redis read cache, several replicas, workers and `fleet_*` tools, hardening (fleet Phases 0–5); cloud-account discovery deferred |
| A2A | Complete | Agent card, discovery, delegation, playbooks; `/a2a/*` served behind bearer auth |
| Access controls | Complete | Bearer auth on network transports, roles over risk tiers with server-issued tokens (fleet Phase 2b), `UNIFI_READ_ONLY`, `UNIFI_DRY_RUN`, `UNIFI_PROFILE` (network, devices, security, system, minimal, protect), `confirm=True` and `dry_run` on every write tool |
| Audit logging | Complete | Wrapper-level records for every mutating call, credential redaction, optional payload encryption, HMAC hash chain, append-only Postgres store with `DATABASE_URL`, SIEM export (syslog/TLS, signed webhook, OTLP) with chain-head anchors, retention for Postgres and for rotated JSONL files (verify, archive, delete); design in `docs/FLEET_SCALING_PLAN.md` §3.7 |

### 2.2 Known limitations

- Traffic flow historical trends and streaming are not feasible under the current v2 cap and remain documented as unsupported.
- Traffic Route writes are not available until the v2 write path is verified on real hardware.
- Access API is not yet implemented. **Blocked upstream**: no official Access spec exists as of 2026-09-26 (`developer.ui.com/access/` returns 404; the API does not appear in the developer portal index).
- Multi-controller orchestration: fleet Phases 0–5 shipped; discovering the consoles behind a cloud account is deferred until per-console routing exists (`docs/FLEET_SCALING_PLAN.md` Phase 4b).
- The Redis webhook event bus is not yet implemented (runbook only). The webhook receiver is served at `POST /webhooks/unifi` on network transports when `WEBHOOK_SECRET` is set.
- Tool profiles exist for network, devices, security, system, minimal, and protect; access, talk, and drive profiles are pending.
- **UniFi Network 11 / UniFi OS 6 support is not yet claimed.** Per the 2026-10-22 audit (§2.4) the server is compatible with Network 11.0.83 per released documentation, but two platform-level deployment targets are removed (USG gateways, the standalone Network Application Server) and four items still need a live-controller test before full support can be claimed. Phase 8 (§4) carries the work; the honest current claim is "compatible per released documentation, with four items pending live verification".

### 2.3 API specification baseline (audited 2026-09-26)

Official UniFi API specs are published at `developer.ui.com/{service}/{version}/` as human-readable pages plus machine-readable artifacts: `openapi.json`, `llms.txt`, and Postman collections. Canonical spec snapshots for this audit are committed under `scripts/` (`scraped-api-spec-v10.6.106.json`, `protect-api-spec-v7.3.68.json`, `mobility-api-spec-v1.0.0.json`, `innerspace-api-spec-v1.3.23.json`, `carrier-fabric-api-spec-v1.0.0.json`). Note: only the *current* version of each spec is hosted; older versions are not retrievable, so version-to-version spec diffs require keeping prior snapshots.

Findings from the Network v10.6.106 / Protect v7.3.68 audit:

- **Network Integration API is endpoint-stable**: 73 operations across 44 paths — unchanged in count since v10.3.55, and every spec path is already covered by `docs/UNIFI_API.md`. No new implementation work; the doc needs a version bump (10.3.55 → 10.6.106 header, version history) and cleanup of embedded v10.1.68 artifacts (example blobs ~lines 2697/2845, reference links ~line 3793).
- **Protect shipped a major version (v6.2.83 → v7.3.68)**: 74 operations across 55 paths, of which **39 operations are absent from the docs and implementation**. New surface: arm profiles with alarm enable/disable (7 ops), sirens (6), speakers (4), fobs (3), relays (4), bridges (3), link stations (3), alarm hubs (4), Protect users (2), UniFi Identity/ULP users (2), POS transaction ingestion (1).
- **Three entirely new APIs are now published** and unknown to the codebase: **Mobility v1.0.0** (8 ops: device configuration, workspaces, devices, clients), **InnerSpace v1.3.23** (6 ops via Cloud Connector proxy for indoor-location/analytics), **Carrier Fabric v1.0.0** (11 ops: subscribers, service state, service plans).
- **Scraper tooling**: `scripts/update-api-docs.js` pins were bumped to Network v10.6.106 / Protect v7.3.68 (Site Manager v1.0.0 unchanged). The puppeteer-based scrapers (`scrape-api-docs.js` authenticates to the UniFi portal; `update-api-docs.js` appends "new endpoint" sections) are legacy — the direct-download `openapi.json` artifacts above are the modern path and should replace them (Phase 4 item).

### 2.4 UniFi Network 11 / UniFi OS 6 compatibility baseline (audited 2026-10-22)

Source: `~/inbox/unifi-network-11-compatibility-audit.pdf` — "UniFi Network 11 Compatibility Audit", 2026-10-22, covering this repository at commit `b4f4f1dd89f23ea6d9229e6f94cf1ae494556405` (2026-10-19) against UniFi Network **11.0.83** (requires UniFi OS **6.0.10+**) and UniFi OS **6**.

The audited commit is an ancestor of the current `main`, and `git diff b4f4f1d..HEAD -- src/` is empty: no server code has changed since the audit, so every per-call verdict below still describes the code as it stands. The audit's own repository snapshot is partially stale in ways that do not affect its verdicts — see "Audit caveats" at the end of this section.

**Verdict: compatible, with two platform-level breaks and four items that must be verified on a live Network 11 controller.**

| Status | Count | Meaning |
|---|---:|---|
| Works | 55 | No change found in the released documentation. |
| Changed | 4 | Still usable; behaviour or data changed as noted. |
| Breaks | 2 | Documented removal affecting this call or target. |
| Needs live controller test | 4 | Cannot be confirmed from released documentation — explicitly not a confirmed break. |
| Call groups inventoried | 65 | Across the legacy site API, Integration API v1, the local v2 API and the Cloud APIs. |

**The breaks are deployment-target removals, not endpoint breaks.** No documented endpoint removal or rename affects the server's REST surface, and authentication is untouched: the server authenticates with a static `X-API-KEY` header (`src/config/config.py`, `Settings.get_headers`) and never performs a username/password session login, so UniFi OS 6.0.7's configurable "Remember Me" duration does not apply.

| Break | Affected in this repo | Nature |
|---|---|---|
| USG gateway support removed (10.6 is the last USG release) | Every device, client and stat call for a USG-gated site | The site has no Network 11 target at all. Surfaced as fleet-health state in Phase 8 (§4 Phase 8, Fix 6). |
| Standalone Network Application Server removed | `local` mode against a classic server | Replacement is UniFi OS Server, which keeps the `/proxy/network/...` paths the server already uses. A deployment action, not a code change. |

**The four "needs live controller test" items.** That status is not a confirmed break — it means the point cannot be settled from released material. These are the real risks, and none of them is an endpoint break:

| # | Item | Surface in this repo |
|---|---|---|
| 1 | Legacy firewall rules (`rest/firewallrule`) after the forced Zone-Based Firewall migration — every site is auto-migrated and legacy rules become zone policies | `src/tools/firewall.py` |
| 2 | Legacy firewall groups (`rest/firewallgroup`), same migration exposure | `src/tools/firewall_groups.py`, against the v2 policy tools in `src/tools/firewall_policies.py` |
| 3 | Site-UID stability across the upgrade (a single unverified community report, 2026-10-13 — not in any Ubiquiti material) | `src/api/client.py` (`resolve_site_id`, `_site_id_cache`, `_site_uuid_to_name` / `_site_name_to_uuid`), `src/api/pool.py` (`AuthState`), fleet site records in `src/fleet/db/models.py` and `src/worker/jobs.py` |
| 4 | v2 `traffic-flows` continuity — Live Flows is built on the new telemetry engine and the endpoint's continuity is undocumented | `src/tools/traffic_flows.py` (50-flow cap, `POST /proxy/network/v2/api/site/{site}/traffic-flows`) |

**The four "Changed" items.** The endpoints are unchanged; the behaviour or the data is not. The statistics engine change (PostgreSQL migration, history cleared and accruing fresh) still needs a live capture to confirm the payload shapes, so it is verified in the same pass as the four items above.

| Item | Change | Surface in this repo |
|---|---|---|
| `stat/sitedpi`, `stat/stadpi` | DPI history is cleared on upgrade; the endpoint is unchanged, the payload shape is to be verified live | `src/tools/dpi.py` |
| `stat/report/*` | Historical series return empty post-upgrade until new data accrues | `src/tools/diagnostics.py` (`get_historical_stats`) |
| `traffic-matching-lists` | External (URL-sourced) lists added upstream; the URL-source property is not modelled in the server | `src/tools/traffic_matching_lists.py`, `src/models/traffic_matching_list.py` |
| Statistics semantics overall | Same endpoints, new engine: empty history after an upgrade is expected, not a failure signal | The stats tools' output and docs |

**Everything else is documented as unchanged.** Devices, clients, networks, WLANs, port forwards, port profiles, RADIUS, hotspot packages, tags, dynamic DNS, events, alarms and backups keep their paths and payloads. Where a Network 11 novelty reaches an existing tool, it reaches it as new content through an old pipe: the new client-connection alarm flows through `stat/alarm` (`src/tools/events.py`), subnet-overlap entries flow through the system log, and new WAN-type and VPN-cipher values arrive as pass-through payload values in `rest/networkconf` (`src/tools/network_config.py`) and the VPN resources. The Integration API v1 surface holds across the board.

**New capability the server does not model.** External (URL-sourced) Network Lists, WiFi WAN configuration, Live Flows parity (no streaming, no terminate), Matter and Thread visibility, packet capture on AP radios, UPS self-test and 2U Pro power cycle, SD-WAN policies (Site Manager 5.10.2+), Time Machine topology history, and the console-level backup system UniFi OS 6 adds alongside the network-app backups. Each is scoped in §3.3 and in Phase 8.

**Audit caveats.** The audit is documentation-based by design: "Works" means no change was found in the released documentation, not that a live controller was exercised. Its inventory figures describe a smaller surface than this repository actually has — it reports "v0.2.4, 74 MCP tools, 1,325 tests" and "10 open pull requests, no open issues", while the audited commit `b4f4f1d` carries version `0.6.1`, the project publishes 343 tools in local mode from 60 modules (349 tool declarations across 61 modules in `src/tools/`), the suite holds 3,369 test functions, and the repository now has 11 open pull requests and 2 open issues. Read the audit as a Network-surface audit, not a whole-server inventory; the 65 call groups it covers are a subset of the 349 tool declarations. It also flags that merging the Python 3.14 base-image bump (PR #235) before the live-controller test work is worth sequencing, so the tests run on the current runtime — that PR is still open.

---

## 3. Gap taxonomy

### 3.1 Critical functional gaps

| ID | Gap | Priority | Outcome |
|---|---|---:|---|
| G1 | Protect API | Highest | v6 surface native (cameras, NVR, viewers, events); **v7.3.68 expansion outstanding — 39 ops unmapped** |
| G2 | Access API | Highest | Doors, credentials, visitors, and policy support — **blocked: no official spec published as of 2026-09-26** |
| G3 | Multi-controller orchestration | Highest | Single-server fleet operations across controllers |
| G4 | Protect v7 expansion | High | Arm profiles/alarm control, sirens, speakers, fobs, relays, bridges, link stations, alarm hubs, users, POS ingestion |
| G5 | Mobility API | Medium | Workspace/device/client config for UniFi Mobility |
| G6 | InnerSpace API | Medium | Indoor-location/analytics data via Cloud Connector proxy |
| G7 | Carrier Fabric API | Medium | Subscriber, service-plan, and service-state management for carrier deployments |

### 3.2 Platform gaps

| ID | Gap | Priority | Outcome |
|---|---|---:|---|
| P1 | Dry-run / change-safe mode | High | Preview write actions before execution |
| P2 | Tool-level RBAC | High | Built-in roles over registry-derived risk tiers, server-issued API tokens (`docs/FLEET_SCALING_PLAN.md` §3.6) |
| P3 | Append-only audit log | High | Every write, denial and admin event, hash-chained, in Postgres or JSONL, exported to SIEM (`docs/FLEET_SCALING_PLAN.md` §3.7) |
| P4 | Prometheus metrics | High | Observe server and tool health |
| P5 | A2A agent card | Medium | Enable machine-readable discovery |
| P6 | Webhook event bus | Medium | Convert webhooks into normalized events |
| P7 | Tool exposure profiles | Medium | Reduce context-window bloat |
| P8 | AI skills / runbooks | Medium | Give agents reusable operational knowledge |
| P9 | Developer workflow standardization | Medium | Make local dev, build, and release consistent |
| P10 | Spec-drift guardrail | High | Pin spec snapshots per release, keep scraper pins current, re-audit quarterly against `developer.ui.com` |

### 3.3 Network 11 and UniFi OS 6 gaps (from the 2026-10-22 audit)

Derived from §2.4. These are the items the audit could not close from released documentation, plus the capability the server does not model yet. Priority follows the audit's own ordering: P0 affects every upgraded fleet, P1 affects data correctness, P2 affects operability, P3 is feature work.

N1–N4 correspond to the audit's own Fixes 1–4. Note that the two cuts differ slightly: the audit counts its "needs live controller test" rows as the two legacy firewall endpoints separately, plus site resolution and traffic-flows, while it files the statistics engine under "Changed" because the endpoints are unchanged. Both cuts are carried here — N1 covers both firewall endpoints, and N3 is a "Changed" item that still needs a live capture to confirm its payload shapes.

| ID | Gap | Priority | Outcome | Audit status |
|---|---|---:|---|---|
| N1 | Legacy firewall behaviour after the forced Zone-Based Firewall migration | P0 | Verify `rest/firewallrule` / `rest/firewallgroup` read and write on a migrated site; steer users to the v2 policy tools in tool descriptions and the README if the legacy path errors, no-ops or lands somewhere unexpected | Needs live test |
| N2 | Site-UID stability across the upgrade | P0 | Compare `GET /integration/v1/sites` UUIDs before and after the upgrade against `UniFiClient.resolve_site_id`, the `_site_id_cache`, `_site_uuid_to_name` / `_site_name_to_uuid` maps and the fleet registry's site records; add cache invalidation and re-resolution on version change if UIDs do move | Needs live test (unverified community report) |
| N3 | Statistics tools against the new statistics engine | P1 | Confirm the payload shapes of `stat/report/*`, `stat/sitedpi` and `stat/stadpi` on 11.0.83 and fix parsers if fields drifted; surface the "history was reset by the upgrade" caveat in the stats tool output and the docs so empty history is not misread as an outage | Changed |
| N4 | v2 `traffic-flows` continuity | P1 | Confirm the endpoint still returns flow records on 11.0.83 and re-check the documented 50-flow drop behaviour against a 10.6 capture | Needs live test |
| N5 | External (URL-sourced) Network Lists | P2 | Model the URL-source property on the Integration API `traffic-matching-lists` payloads (`src/tools/traffic_matching_lists.py`, `src/models/traffic_matching_list.py`) once the field name is confirmed on a live controller or in the in-app Integrations documentation | Changed |
| N6 | Non-upgradable fleet members are invisible until a call fails | P2 | Mark USG-gated sites and hosts still on the classic Network Application Server as "cannot run Network 11 — stays on 10.6 / migrate to UniFi OS Server" in fleet health output and the README compatibility notes, instead of surfacing per-call errors | Breaks (platform) |
| N7 | Live Flows parity | P3 | Discovery on a live 11.0.83 controller: confirm `traffic-flows` continuity, look for a streaming or terminate endpoint (a browser dev-tools capture of the Live Flows UI is the practical route), then add `get_live_flows` and, only if an endpoint exists, `terminate_flow`. Keep the existing block-source / destination-IP rule creation as the fallback enforcement action | Partial (no public API) |
| N8 | WiFi WAN (WiFi Uplink / WISP) configuration | P3 | Discovery on Wi-Fi 7 hardware (UDR7, UDR-5G-Max, Express 7, UCG-Industrial): extend the WAN tools with the uplink fields and read the uplink link state. Upstream Wi-Fi credentials are secrets and must follow the existing secret-handling patterns — never logged or echoed | Partial (reads only) |
| N9 | Matter and Thread visibility | P3 | Run the Small discovery spike first (the version-local Integrations API documentation under Settings, plus a capture of the Topology / Matter UI's network calls). If a surface exists, add a Matter resource family and merge Thread nodes into `src/tools/topology.py`; if not, record it as a documented Gap and re-check each release. Matter pairing codes are credentials | Gap (no documented API) |
| N10 | Console-level backups (UniFi OS 6) | P3 | The OS adds a separate console-level backup system — schedules, multiple destinations — alongside the network-app backups `src/tools/backups.py` already covers. Model it only if the surface is discoverable | Partial (not exposed) |
| N11 | SD-WAN policies (Site Manager 5.10.2+) | P3 | The Site Manager client covers hosts, sites and devices; `src/tools/site_manager.py` exposes SD-WAN *configs* but not Network 11 SD-WAN *policies*. Scope only after the policy surface is identified | Gap |

Items the audit explicitly leaves alone, recorded here so they are not re-litigated: the new client-connection alarm flows through `stat/alarm` with no new code (though a dedicated filter would be a convenience); bulk client editing remains per-client; Channel Plan's country selector does not change the `countries` reference data the server already reads; IPIP WAN and the OpenVPN AES-192/128-CBC options pass through as payload values; packet capture on AP radios, UPS self-test and UPS 2U Pro power cycle have no modelled surface; and Time Machine topology history has no documented data source.

---

## 4. Phased implementation plan

### Phase 3: Protect API integration (complete)

**Goal:** deliver native Protect coverage on top of the existing Network and Site Manager foundation.

> **Superseded in part:** this phase covers the v6-era Protect surface. Protect v7.3.68 (2026) added a 39-operation device/alarm expansion that is *not* part of this phase — it is queued as Phase 5a (§4.5a).

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

- Full test coverage for new Phase 1–3 modules — done (2026-10-10: every module at 80%+)
- Dynamic DNS full CRUD — done
- Tagged MAC management — done
- Device migration tools — done
- `NETWORK_PLAYBOOK.md` runbook library — done
- `skills/` domain knowledge packs — done
- `Makefile`, `docker-compose.yml`, and `HARBOR_SETUP.md` — done
- Documentation synchronization across README, API, UNIFI_API, and changelog — done (2026-09-27: README tool totals, UNIFI_API.md v10.6.106 + v7.3.68 + Phase 6 mappings, CHANGELOG [0.5.0] fold; API.md spot-checks clean)
- API-spec alignment wave (§2.3) — done:
  - `docs/UNIFI_API.md` version bump 10.3.55 → 10.6.106 + version-history entry + removal of embedded v10.1.68 artifacts — done
  - `docs/UNIFI_API.md` Protect section updated to v7.3.68 with the 39 new operations documented as planned (not yet implemented) — done
  - Replace legacy puppeteer scrapers with direct-download spec artifacts (`openapi.json` / `llms.txt`) — done (`scripts/fetch-specs.sh`; scrapers deprecated in `scripts/README.md`)
  - Field-level verification of existing tool payloads against v10.6.106 schemas (73 ops, endpoint-stable but schemas may drift within versions) — done (`.analysis-reports/api-spec-audit-2026-09-26.md`: 3 latent write-path defects F1-F3 — adopt endpoint non-existent, port-action path drift, client-action legacy shape; hardware verification required before fixes ship)

#### Exit criteria

- Coverage target reached and stable
- Developer workflow is standardized
- Docs reflect the implemented feature set

---

### Phase 5: Enterprise scale and operational excellence (partially started)

**Goal:** turn the server into a multi-site, multi-team operating platform with strong safety and observability controls.

#### Deliverables

- Multi-controller / multi-site orchestration — done (fleet Phases 0–5, `docs/FLEET_SCALING_PLAN.md`; cloud-account discovery deferred)
- Dry-run / change-safe mode — partial
- Tool-level RBAC via roles and API tokens — partial (transport-level bearer auth only); design in `docs/FLEET_SCALING_PLAN.md` §3.6, Phases 1 and 2b
- Append-only audit log — done (payload encryption, hash chain, Postgres store, SIEM export and anchors, retention for Postgres and JSONL); design in `docs/FLEET_SCALING_PLAN.md` §3.7, Phases 1, 2b and 5
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

### Phase 5a: Protect v7 expansion (new — queued after Phase 4 docs alignment)

**Goal:** bring the Protect module from the v6-era surface to full v7.3.68 coverage, per the spec audit in §2.3.

#### Deliverables

- `src/models/protect_v7.py` models for the new v7 device categories — done
- Tool modules for:
  - Arm profiles (list, create, update, delete, set-current) and alarm enable/disable — **write tools must respect `UNIFI_READ_ONLY` and `confirm=True` conventions** — done (`src/tools/protect_alarm.py`)
  - Sirens (CRUD + play/stop/test-sound), speakers (CRUD + test-sound) — done (`protect_sirens.py`, `protect_speakers.py`)
  - Fobs, relays (incl. output activation), bridges, link stations, alarm hubs (incl. output trigger) — done (`protect_fobs.py`, `protect_relays.py`, `protect_bridges.py`, `protect_link_stations.py`, `protect_alarm_hubs.py`)
  - Protect users and UniFi Identity (ULP) users (read) — done (`protect_users.py`)
  - POS transaction ingestion (write; confirm-gated) — done (`protect_pos.py`)
- `docs/UNIFI_API.md` Protect section: 39 new operations documented with request/response shapes from `protect-api-spec-v7.3.68.json` — done (marked implemented with hardware-verification caveat)
- Mocked integration tests mirroring the Phase 3 pattern (no live hardware dependency) — done (+108 unit tests across 10 test modules; suite 2386 passed)
- Optional: alarm state exposed as MCP resources — deferred
- Live-hardware verification of write paths — **open** (mocked tests assert the code's assumptions; same class of risk as audit findings F1–F3)

#### Scope

- 39 new operations (of 74 total in v7.3.68); the other 35 are already covered by the Phase 3 surface — re-verify against the v7 spec for schema drift
- No new transport work: reuse the existing Protect integration API client (`/proxy/protect/integration/v1/...`)

#### Exit criteria

- All 74 v7.3.68 spec operations are either implemented or explicitly documented as out-of-scope
- New write tools are covered by dry-run interception and audit logging
- Mocked tests cover every new tool and model
- Docs mark the new surface as verified-against-spec v7.3.68

---

### Phase 6: New API domains — Mobility, InnerSpace, Carrier Fabric (new)

**Goal:** extend the platform beyond Network/Protect with the three newly published UniFi APIs, each of which is small enough to land as a focused increment (25 operations total).

#### 6.1 Mobility v1.0.0 (8 operations) — **done (2026-09-27)**

- Cloud API against `api.ui.com` (same auth model as the existing Site Manager cloud client)
- Ops: device configuration (3), workspaces (2), devices (2), clients (1)
- Deliverables: ~~`src/api/mobility_client.py`~~ tools reuse `SiteManagerClient` (zero new transport — deviation from plan, recorded here), `src/models/mobility.py`, `src/tools/mobility.py` (8 tools), docs section, 20 mocked tests — done

#### 6.2 InnerSpace v1.3.23 (6 operations) — **done (2026-09-27)**

- Served via the **Cloud Connector proxy** pattern already used for Network/Protect proxying (`/v1/connector/consoles/{consoleId}/proxy/innerspace/integration`)
- Indoor-location/analytics data (per spec tags); read-oriented surface
- Deliverables: `src/models/innerspace.py`, `src/tools/innerspace.py` (6 read-only tools), docs section, 16 mocked tests — done

#### 6.3 Carrier Fabric v1.0.0 (11 operations) — **done (2026-09-27)**

- Cloud API against `api.ui.com`; carrier/ISP domain: subscribers (7), service state (2), service plans (2)
- Highest blast radius of the three (subscriber lifecycle management) — all writes confirm-gated and audited
- Deliverables: ~~`src/api/carrier_fabric_client.py`~~ tools reuse `SiteManagerClient` (same deviation as 6.1), `src/models/carrier.py`, `src/tools/carrier.py` (11 tools), docs section, 30 mocked tests — done

#### Shared exit criteria

- Each domain ships behind its own tool exposure profile (extends P7)
- All writes respect `UNIFI_READ_ONLY`, `confirm=True`, dry-run, and audit
- Docs separate implemented vs planned per domain; spec snapshots pinned in `scripts/`
- Access API remains parked until Ubiquiti publishes a spec; if it appears, it slots into Phase 5/6 ahead of or alongside these domains

---

### Phase 7: Deployment automation (done; a molecule test for the playbook is open)

**Goal:** install the server and its fleet stack (Redis, Postgres) repeatably, from a single host to a cluster, without hand-editing compose files. Today the only paths are `docker-compose.yml` (server only), `docker-compose.fleet.yml` (server, Redis, Postgres on one host) and `docker-compose.fleet-scale.yml` (replicas and workers on one host).

#### 7.1 Ansible playbook (Docker hosts)

**Status: done** (`deploy/ansible/`, `deploy/ansible/README.md`). Redis and Postgres run as single containers; for high availability the inventory points at managed endpoints (`unifi_mcp_redis_url`, `unifi_mcp_database_url`) instead of running Sentinel or Patroni itself. The replicas serve plain HTTP on loopback or the private network, with TLS at nginx. A new unauthenticated `GET /healthz` backs the container health check and the load balancer. CI runs `--syntax-check`; a converge-and-idempotence test (molecule or equivalent) is still open.

- A role-based playbook (`deploy/ansible/`) that installs Docker, then the server, Redis and Postgres as containers, driven by an inventory:
  - **Single server:** everything on one host, equivalent to `docker-compose.fleet.yml`.
  - **Multi-server / clustered:** `mcp` hosts running several replicas and workers behind a load balancer with sticky sessions (the Phase 4 session-affinity finding in `docs/FLEET_SCALING_PLAN.md`), a `redis` group (Sentinel or a managed endpoint) and a `postgres` group (primary plus replica, or a managed endpoint).
- Each component optional, so an operator can point at an existing Redis or Postgres.
- Secrets (`UNIFI_API_KEY`, `MCP_AUTH_TOKEN`, `UNIFI_AUDIT_CHAIN_KEY`, `UNIFI_AUDIT_LOG_KEY`, `UNIFI_FLEET_CREDENTIAL_KEY`, database passwords) from Ansible Vault or an external lookup, never written into the repository or templates in clear.
- Runs `python -m src.fleet.cli migrate` once (as `MIGRATION_DATABASE_URL`) and creates the least-privilege runtime role from SECURITY.md.
- Safe defaults carried over: TLS on network transports, bearer auth on, `UNIFI_AUDIT_FAIL_CLOSED=true`, audit log and SIEM buffer on a persistent volume with 0700 permissions.
- Idempotent (a second run changes nothing), with `--check` support, and a molecule (or equivalent) test in CI.

#### 7.2 Kubernetes option (Helm chart)

**Status: done** (`deploy/helm/unifi-mcp/`). Redis and Postgres are external endpoints only, given as URLs in the chart's Secret: bundling third-party database charts would tie releases to theirs, and production clusters run operators or managed services. Without fleet mode the audit file sits on an emptyDir, or on a PersistentVolumeClaim with one replica. Metrics are scraped through a ServiceMonitor that sends the bearer token, rather than annotations, because `/metrics` needs it. The release workflow now also publishes `<version>-fleet` images. CI lints and renders the chart, validates it with kubeconform, and runs a kind smoke test in fleet mode.

- A Helm chart (`deploy/helm/unifi-mcp/`) with the server as a Deployment (replica count, HPA optional), workers as a second Deployment, `/healthz` readiness and liveness probes, and `/metrics` scrape annotations.
- Redis and Postgres either as chart dependencies (off by default for production) or external endpoints via values.
- Secrets from an existing Kubernetes Secret or External Secrets; the chart never templates secret values from `values.yaml` defaults.
- A pre-install/upgrade Job for migrations; a PersistentVolumeClaim (or SIEM export as the durable copy) for the audit log.
- `helm lint` and `helm template` checks in CI, with a kind-based smoke test.

#### 7.3 Pre-canned agent setup prompts

**Status: done** (`docs/deploy-prompts/`), using `/healthz` and an `initialize` call with the bearer token for verification.

Prompts an operator can hand to an AI coding agent (Claude Code or similar) to stand up the infrastructure, kept in `docs/deploy-prompts/`. Each lists what it will ask for, the safety rules it must follow (no secrets in files under version control, confirm before touching existing hosts, verify with `/health` and a read-only tool call) and how to check the result:

1. **MCP server only:** the server with a single UniFi controller, Docker or a Python install, stdio or streamable HTTP with bearer auth.
2. **MCP server with one Redis and one Postgres:** the single-server fleet stack (`docker-compose.fleet.yml` or the Ansible single-server inventory), including migrations and the first API token.
3. **Full clustered environment:** several replicas and workers, Redis and Postgres for high availability, load balancer, SIEM export, via the multi-server Ansible inventory or the Helm chart.

#### Exit criteria

- Each of the three prompts, followed by an agent in a clean environment, produces a working deployment that passes its own verification steps
- The playbook and chart deploy the same settings as the compose files (a test compares the environment variables each one sets)
- No secret value is ever committed, templated from a default or printed in a log
- The fleet verification (`make verify-fleet-scale`) passes against a clustered deployment

---

### Phase 8: UniFi Network 11 and UniFi OS 6 compatibility (new — planned)

**Goal:** turn the 2026-10-22 compatibility audit (§2.4) into a supportable position: settle the four items the audit could not resolve from documentation on a live Network 11 controller, model the capability that is safe to model from documentation alone, and make the two platform-level breaks visible before an operator hits them mid-migration.

This phase is deliberately split. The **verification** work (N1–N4) needs hardware and cannot be closed in this repository. The **code and documentation** work (N3's caveat, N5, N6, and the discovery steps for N7–N9) can land before that hardware exists, and should — a caveat that says "an empty statistics history right after the upgrade is the expected consequence of the engine change, not an outage" is worth shipping even if the payload shapes are still unconfirmed.

> **Naming note:** the audit refers to `UniFiClient._site_names_by_uuid` / `_site_uuids_by_name`. The attributes in this repository are `_site_uuid_to_name` and `_site_name_to_uuid` (`src/api/client.py:79-81`), alongside `_site_id_cache` (line 77). Use the repository's names.

#### Deliverables

- `docs/NETWORK_11_COMPATIBILITY.md` — a compatibility matrix for the published docs: Network 11.0.83 / UniFi OS 6 per surface, the two platform breaks, the four live-test items with their current status, and the "compatible per released documentation, with four items pending live verification" claim wording. Not a claim of full support until the checklist in §4 Phase 8, "Live-controller test checklist" has been run
- N6 — fleet health output and README compatibility notes marking USG-gated sites and classic-Network-Application-Server hosts as unable to run Network 11, in place of per-call errors
- N3 — the statistics-reset caveat in the stats tool output (`src/tools/dpi.py`, `src/tools/diagnostics.py`) and in the docs
- N5 — the URL-source property on the External Network List payloads (`src/models/traffic_matching_list.py`, `src/tools/traffic_matching_lists.py`), after the field name is confirmed
- N1 — a redirect in the legacy firewall tool descriptions and the README toward the v2 policy tools (`src/tools/firewall_policies.py`), plus a deprecation note if the legacy path is confirmed broken on a migrated site
- N2 — cache invalidation and site re-resolution on a detected version change (`src/api/client.py`, `src/api/pool.py`), if and only if the live test confirms UIDs move
- A live-controller test report, filed under `.analysis-reports/`, recording the observed responses for each of the five checklist steps

#### Scope

**In scope**

- The four surfaces the audit inventoried: legacy site API, Integration API v1, local v2 API, Cloud APIs
- The two platform-level deployment breaks and how the server surfaces them
- The four needs-live-test items and the four changed-data items (§2.4), as verification tasks plus the code and docs that make their failure modes legible
- The Network 11 feature set listed in §3.3, at the level of discovery and modelling that the available evidence supports

**Out of scope**

- UniFi Protect. It is a separate application, unaffected by the changes audited here
- Anything requiring a Ubiquiti-published API that does not exist. Where no surface is documented, the outcome is a documented Gap, not a speculative client
- The deployment migration itself. Moving a classic server to UniFi OS Server is an operator action; the server's job is to say the current target cannot be upgraded, and the replacement keeps the `/proxy/network/...` paths already in use
- The `rest/networkconf` and VPN pass-through values (IPIP WAN type, OpenVPN AES-192/128-CBC). They arrive as payload values and need no model change

#### The seven fixes, in the audit's order

**Fix 1 (P0) — legacy firewall after the forced ZBF migration.** Exercise `create_firewall_rule` / `update_firewall_rule` / `delete_firewall_rule` (`src/tools/firewall.py`, `rest/firewallrule`) and the `rest/firewallgroup` rule mutation (`src/tools/firewall_groups.py`) on a migrated site. These writes are safety-sensitive: if they error, no-op, or land somewhere unexpected, steer users to the v2 policy tools (`src/tools/firewall_policies.py`) in the tool descriptions and the README, and consider deprecating the legacy tools. Note that `list_firewall_rules` already falls back to the v2 `firewall-policies` endpoint when the legacy list comes back empty in local mode — that fallback exists for the older ZBF-era controllers and says nothing about write behaviour on a migrated one.

**Fix 2 (P0) — site-ID stability across the upgrade.** Record `GET /integration/v1/sites` UUIDs and site names before the upgrade and again after, and diff them against the server's caches (`_site_id_cache`, `_site_uuid_to_name`, `_site_name_to_uuid` in `src/api/client.py`) and the fleet registry's site records (`sites.site_uuid` in `src/fleet/db/models.py`, synced by `src/worker/jobs.py`). If UIDs do change, add cache invalidation and re-resolution on a detected version change so tools never target a stale UUID. Treat the claim as unverified until the diff is observed: it rests on a single community report.

**Fix 3 (P1) — stats tools against the new statistics engine.** Confirm the payload shapes of `stat/report/*`, `stat/sitedpi` and `stat/stadpi` on 11.0.83 and fix the parsers if fields drifted. Independently of the outcome, surface the "history was reset by the Network 11 upgrade" caveat in the stats tool output and the docs. The endpoints themselves are unchanged, so an empty history immediately after an upgrade is the expected consequence of the engine change — not evidence of an outage or a broken tool.

**Fix 4 (P1) — v2 traffic-flows continuity.** Poll `POST /proxy/network/v2/api/site/{site}/traffic-flows` for five minutes on a busy gateway and compare the record shape and drop behaviour against a 10.6 capture. The module already documents the 50-flow cap and the non-functional server-side filters (`src/tools/traffic_flows.py`); re-check whether either changed.

**Fix 5 (P2) — External Network Lists.** Network 11 lets Network Lists pull entries from an external URL. Add the URL-source property to the Integration API `traffic-matching-lists` payloads after confirming the field name on a live controller or in the version-local Integrations documentation. Do not guess the field name: an unconfirmed key silently produces a list that is not URL-sourced.

**Fix 6 (P2) — flag the fleets that cannot upgrade.** In fleet health output and the README compatibility notes, mark sites gated by a USG and hosts still running the classic Network Application Server as "cannot run Network 11 — stays on 10.6 / migrate to UniFi OS Server". The fleet worker already records the Network version per controller (`capabilities.network_version`, `src/worker/jobs.py`), and the device inventory carries the model (`src/fleet/db/models.py`), so both signals are available to the health snapshot. This is the fix that converts a silent platform break into a visible one.

**Fix 7 (P3) — feature work.** WiFi WAN configuration, Live Flows parity, and Matter / Thread visibility. Each is scoped in full in §3.3 (N7, N8, N9). All three start with discovery on live hardware, and each is blocked on it. For Matter and Thread, run the Small discovery spike before committing to the Large work.

#### Live-controller test checklist

The checklist the audit specifies for whoever runs Fixes 1–4. Until all five steps are run and recorded, the supportable claim is "compatible per released documentation, with four items pending live verification" — not "fully supports Network 11". That distinction is the point of the audit's status vocabulary, and it should survive into the published docs.

1. Record `GET /integration/v1/info` (`applicationVersion`) and all site UUIDs before the upgrade; repeat after; diff.
2. On a migrated site: read a legacy firewall rule, create a throwaway rule, delete it — record the exact responses from `rest/firewallrule` and `rest/firewallgroup`.
3. Pull `stat/report/hourly/site`, `stat/sitedpi` and `stat/stadpi` post-upgrade; compare the field sets against a 10.6 capture.
4. Poll the v2 `traffic-flows` endpoint for five minutes on a busy gateway; compare the record shape and the drop behaviour against 10.6.
5. While doing step 4, capture the Live Flows UI's network calls — the terminate action especially — for the N7 discovery work.

Step 5 is the only route to the Live Flows terminate endpoint: Ubiquiti documents no public API for it, and the UI's own calls are the practical evidence. A browser dev-tools capture of the Live Flows UI is the instrument.

**Sequencing note:** merge the Python 3.14 base-image bump (PR #235) before the live-controller test work, so the tests run on the current runtime.

#### Exit criteria

- The five-step checklist has been run on a live Network 11 controller and the observed responses are recorded in `.analysis-reports/`
- Each of N1–N4 carries a status of verified, changed or broken, and the published compatibility matrix states it — including a verified-broken outcome
- The two platform breaks are visible in fleet health and the README before an operator encounters them
- The statistics-reset caveat ships in the stats tool output regardless of the payload-shape outcome
- Every Network 11 feature gap is either modelled with a documented surface or recorded as a Gap with a re-check trigger, and none is claimed as working
- The compatibility claim wording matches the verification state

---

## 5. Version roadmap

| Version | Scope | Notes |
|---|---|---|
| v0.6.1 | Patch | **Released 2026-10-14**: publishes the wheel, sdist and SBOM missing from v0.6.0 (immutable-release asset upload fixed), Supermemory v5 client |
| v0.6.0 | Fleet Phases 0–5 + Phase 7 | **Released 2026-10-12**: multi-controller fleet stack (`docs/FLEET_SCALING_PLAN.md`), SIEM export and audit retention, Ansible playbook, Helm chart and `-fleet` images, agent setup prompts |
| v0.5.0 | Phases 3 + 4 + 5a + 6 | **Tagged 2026-09-28, not published** (see the note below): 343 tools / 60 modules, Network v10.6.106 + Protect v7.3.68 + Mobility/InnerSpace/Carrier Fabric, transport auth hardening, spec-audit baseline. Folds the never-tagged `[0.4.0]` changelog entries |
| v0.2.5 | Earlier release | Tag `v0.2.5`; `v0.2.6` exists only on `batch2-review*` branches, not `main` |
| v1.0.0 | Phase 5 | Enterprise scale & operational excellence |
| v0.7.0+ | Post-release increments | Access API if/when Ubiquiti publishes a spec; remaining Phase 5 items; a converge-and-idempotence test for the playbook; **Phase 8 (Network 11 / UniFi OS 6 compatibility)**, whose code and documentation half (N3 caveat, N5, N6, discovery for N7–N9) can ship ahead of the live-controller verification, and whose verification half (N1–N4) needs a Network 11 controller |

---

> **Versioning reconciled 2026-09-27 (release prep).** The next release is **v0.5.0**: `pyproject.toml` bumped 0.2.5 → 0.5.0, `CHANGELOG.md` folds `[0.4.0]` + `[Unreleased]` into `[0.5.0]`. The roadmap's earlier v1.1.0/v1.2.0 rows for Phases 5a/6 are superseded — both shipped before the first release cut and ride in v0.5.0. The `v0.2.6` tag remains a branch-only historical artifact and does not conflict. `v0.5.0` was tagged on 2026-09-28 after hardware verification but never published: its release workflow could not start (an account billing lock), and the re-run on 2026-10-12 failed because the job installed unpinned dev tools and a newer black rejected the tagged code. The release job now installs the locked versions (`uv sync --locked`). Everything in v0.5.0 plus fleet Phases 0–5 and Phase 7 ships as **v0.6.0**, the first release published since v0.2.6. The v0.6.0 release page has no assets: the repository has immutable releases on, and the workflow published before uploading the wheel, sdist and SBOM. The workflow now uploads to a draft and then publishes, and **v0.6.1** (2026-10-14) is the first release with its assets attached.

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
- `docs/NETWORK_11_COMPATIBILITY.md` (Phase 8)

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
| API/documentation drift returns | Medium | Medium | Phase gates require docs and implementation sync; spec snapshots pinned per release (P10) |
| Spec snapshots rot (pins drift again, as v10.1.68 did) | Medium | Medium | Quarterly re-audit against `developer.ui.com` index; keep `openapi.json` artifacts in-repo; legacy scrapers replaced with direct-download path |
| Latent Integration API write defects (audit 2026-09-26: adopt, port-action, client-action paths) | Resolved 2026-09-27 | High | Hardware probes confirmed all three (spec endpoints live, legacy routes 404); fixes shipped with spec-verified mocked tests — see `.analysis-reports/api-spec-audit-2026-09-26.md` addendum |
| Legacy firewall writes land wrongly or no-op after the forced ZBF migration (Network 11) | Medium — undocumented, affects every upgraded fleet | High | Live-controller test before claiming support (Phase 8, Fix 1); steer to the v2 policy tools in the tool descriptions and README; treat a silent no-op as a write failure, never a success |
| Site UIDs change on upgrade, leaving cached UUIDs and fleet site records stale (Network 11) | Low — a single unverified community report | High | Compare site UUIDs before and after an upgrade (Phase 8, Fix 2); add cache invalidation and re-resolution on a detected version change; keep fleet site records keyed on something stable if UIDs are confirmed to move |
| Empty statistics history after a Network 11 upgrade is misread as an outage or a broken tool | High if unsurfaced | Medium | Ship the statistics-reset caveat in the stats tool output and the docs (Phase 8, N3) independent of the payload-shape outcome |
| A tool claims to support a Network 11 feature with no documented API behind it | Medium | Medium | Model only what a live controller or the version-local Integrations documentation shows; record everything else as a documented Gap with a re-check trigger |
| The 2026-10-22 audit's repository snapshot is read as a current inventory | Medium | Low | The audit's counts (74 tools, 1,325 tests, 10 open PRs) describe a smaller surface than this repository; §2.4 records the discrepancy and every carried-forward claim is re-derived from the tree at `main` |

---

## 8. Maintenance rule

The development plan is not complete until documentation and implementation tell the same story. When a new capability is added, update the spec, roadmap, endpoint docs, and test strategy in the same change set.

The same rule applies to release support: a compatibility claim is only as good as the evidence behind it. The Network 11 position in §2.4 and §3.3 must be re-checked against each UniFi Network release — Ubiquiti publishes no Integration API changelog, so a release that changes the surface shows up as a live-controller observation, not as a notification. Each gap recorded in §3.3 carries either a status or a re-check trigger, and none may be promoted to "supported" without the evidence named in the Phase 8 exit criteria.
