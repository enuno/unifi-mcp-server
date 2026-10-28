# UniFi Network 11 / UniFi OS 6 Compatibility

**Status: compatible per released documentation, with four items pending live-controller verification.** This is not a claim of full support — see the live-controller test checklist in `DEVELOPMENT_PLAN.md` §4 Phase 8.

Source: `DEVELOPMENT_PLAN.md` §2.4 (2026-10-22 audit, covering commit `b4f4f1dd89f23ea6d9229e6f94cf1ae494556405` against UniFi Network **11.0.83**, UniFi OS **6.0.10+**) and the 2026-10-27 spec re-audit (`DEVELOPMENT_PLAN.md` §2.3), which found the live Network Integration API has advanced to **v11.0.97** but is endpoint-stable since 10.6.106/11.0.83 — nothing below is invalidated by that point-release drift.

## Summary

| Status | Count | Meaning |
|---|---:|---|
| Works | 55 | No change found in the released documentation |
| Changed | 4 | Still usable; behaviour or data changed as noted |
| Breaks | 2 | Documented removal affecting this call or target |
| Needs live controller test | 4 | Cannot be confirmed from released documentation — not a confirmed break |

The server authenticates with a static `X-API-KEY` header and never performs a username/password session login, so UniFi OS 6.0.7's configurable "Remember Me" duration does not apply.

## Platform-level breaks (confirmed, not endpoint breaks)

No documented endpoint removal or rename affects this server's REST surface. These two breaks are deployment-target removals:

| Break | Affected in this repo | Visibility |
|---|---|---|
| USG gateway support removed (10.6 is the last USG release) | Every device, client and stat call for a USG-gated site | **Implemented 2026-10-27**: `fleet_health` flags any controller with a USG anywhere in its synced device inventory — `platform_compat.network_11_capable: false` (`src/fleet/fleet_tools.py`, `USG_MODEL_SUBSTRING`/`USG_GATED_REASON`). |
| Standalone Network Application Server removed | `local` mode against a classic server | **Not auto-detectable**: the Integration API's `/v1/info` returns only `applicationVersion`, with no host-type/platform field — there is no API signal that distinguishes a classic self-hosted server from a UniFi OS console. Operators who know this about a controller should label it (e.g. `deployment=classic-server`) and filter `fleet_health`/`fleet_sites` on that label. Migrating is an operator action (replacement is UniFi OS Server, which keeps the same `/proxy/network/...` paths) — not a code change. |

## The four "needs live controller test" items

Not a confirmed break — the point cannot be settled from released material alone. None of these is an endpoint break.

| # | Item | Surface in this repo | Status |
|---|---|---|---|
| N1 | Legacy firewall rules/groups (`rest/firewallrule`, `rest/firewallgroup`) behaviour after the forced Zone-Based Firewall migration | `src/tools/firewall.py`, `src/tools/firewall_groups.py` vs. `src/tools/firewall_policies.py` | **Doc half landed 2026-10-27**: tool docstrings and module docstring now steer callers to the v2 policy tools on a migrated site. Whether the legacy write still takes effect is still unverified — needs live test. |
| N2 | Site-UID stability across the upgrade (single unverified community report) | `src/api/client.py`, `src/api/pool.py`, `src/fleet/db/models.py`, `src/worker/jobs.py` | Needs live test. No code change until UID drift is actually observed — see `DEVELOPMENT_PLAN.md` §4 Phase 8 Fix 2. |
| N3 | Statistics tools against the new statistics engine (`stat/report/*`, `stat/sitedpi`, `stat/stadpi`) | `src/tools/dpi.py`, `src/tools/diagnostics.py` | Needs live test for payload-shape drift. The "history was reset by the upgrade" caveat in the tool output itself has **not** shipped yet — tracked as a follow-up; do not read an empty post-upgrade history as an outage in the meantime. |
| N4 | v2 `traffic-flows` continuity | `src/tools/traffic_flows.py` (50-flow cap) | Needs live test. |

## The four "Changed" items

The endpoints are unchanged; the behaviour or the data is not.

| Item | Change | Surface in this repo |
|---|---|---|
| `stat/sitedpi`, `stat/stadpi` | DPI history cleared on upgrade; payload shape to be verified live | `src/tools/dpi.py` |
| `stat/report/*` | Historical series return empty post-upgrade until new data accrues | `src/tools/diagnostics.py` (`get_historical_stats`) |
| `traffic-matching-lists` | External (URL-sourced) lists added upstream; URL-source property not modelled (field name needs live confirmation — do not guess it) | `src/tools/traffic_matching_lists.py`, `src/models/traffic_matching_list.py` |
| Statistics semantics overall | Same endpoints, new engine: empty history after an upgrade is expected, not a failure signal | Stats tools' output and docs |

## Everything else

Devices, clients, networks, WLANs, port forwards, port profiles, RADIUS, hotspot packages, tags, dynamic DNS, events, alarms and backups keep their paths and payloads unchanged. New Network 11 content (client-connection alarms, subnet-overlap entries, new WAN-type/VPN-cipher values) arrives as pass-through payload values through existing tools, requiring no model change.

## New capability not modelled

External (URL-sourced) Network Lists, WiFi WAN configuration, Live Flows parity (no streaming, no terminate), Matter and Thread visibility, packet capture on AP radios, UPS self-test and 2U Pro power cycle, SD-WAN policies (Site Manager 5.10.2+), Time Machine topology history, and the console-level backup system UniFi OS 6 adds alongside the network-app backups. Each is scoped in `DEVELOPMENT_PLAN.md` §3.3 and Phase 8.

## Live-controller test checklist

Until all five steps are run and recorded under `.analysis-reports/`, the supportable claim stays "compatible per released documentation, with four items pending live verification":

1. Record `GET /integration/v1/info` (`applicationVersion`) and all site UUIDs before the upgrade; repeat after; diff.
2. On a migrated site: read a legacy firewall rule, create a throwaway rule, delete it — record the exact responses from `rest/firewallrule` and `rest/firewallgroup`.
3. Pull `stat/report/hourly/site`, `stat/sitedpi` and `stat/stadpi` post-upgrade; compare the field sets against a 10.6 capture.
4. Poll the v2 `traffic-flows` endpoint for five minutes on a busy gateway; compare the record shape and the drop behaviour against 10.6.
5. While doing step 4, capture the Live Flows UI's network calls (terminate action especially) — the only practical route to the undocumented terminate endpoint.

See `DEVELOPMENT_PLAN.md` §4 Phase 8 for the full fix list, sequencing notes, and exit criteria.

## Audit caveats

The underlying audit is documentation-based by design: "Works" means no change was found in released documentation, not that a live controller was exercised. Treat it as a Network-surface audit, not a whole-server inventory — see `DEVELOPMENT_PLAN.md` §2.4 "Audit caveats" for the full detail.
