# Phase 8 live-controller report — Network 10.6.109 baseline (2026-10-29)

**Runner:** noesis-praxis (Hermes agent), at the operator's request.
**Controller:** UDM (`stat/device` model `UDMA69B`, one device total, no USG — N6 signal clean), UniFi Network **10.6.109** (`GET /proxy/network/integration/v1/info` → `applicationVersion`).
**Client:** locally built image `unifi-mcp-server:local-9d027fa8482b` (commit `9d027fa8482b`, `Dockerfile` on `python:3.14-alpine` — the PR #235 sequencing note was already satisfied on `main`). Every capture ran *inside* the container against the shipped code path; an MCP-stdio smoke test (initialize → tools/list → tools/call `list_sites`) registered 343 tools and returned the live site before any capture ran.
**Writes made on the controller:** exactly two throwaway objects, both deleted during the run and verified absent afterwards — one disabled drop rule attempt (rejected by the controller, never existed) and one port group `PHASE8-THROWAWAY-PORTS` (created, updated, deleted through the public tools). `step2_leftover_check.json` proves nothing `PHASE8*` remained.
**Evidence:** raw JSON captures in `./captures/` (client MAC and console hostname redacted; one full flow record structure kept with values masked).

## Checklist status (DEVELOPMENT_PLAN.md §4 Phase 8)

| Step | Status | What this run established |
|---|---|---|
| 1. `applicationVersion` + site UUIDs before/after upgrade | **"Before" half recorded** | `10.6.109`; one site `Default`, UUID `88f7af54-98f8-306a-a1c7-c9349722b1f6`, `internalReference: default` (`step1_*.json`). The "after" half needs the same controller on Network 11. |
| 2. Legacy firewall reads/writes on a migrated site | **Substantive early answer on 10.6.109** — see N1 below | This site is already ZBF-migrated (0 legacy rules, 78 v2 policies). Legacy rule *writes* are rejected outright; `rest/firewallgroup` mutations still work. |
| 3. Stats payload shapes post-upgrade vs 10.6 | **10.6 baseline recorded** | Field sets for `stat/report/hourly.site`, `stat/sitedpi`, `stat/stadpi` captured (`step3_*.json`). Diff target for the Network 11 run. |
| 4. v2 `traffic-flows` continuity vs 10.6 | **10.6 baseline recorded** | 5-minute poll, 20/20 OK, 50-flow cap held every poll, pagination params ignored, server-side protocol filter non-functional (`step4_*.json`). |
| 5. Live Flows UI network capture (terminate endpoint) | **BLOCKED** | Needs interactive console-UI login (browser dev-tools). No UI credentials are held in the vault — access here is API-key-only by design. |

## N1 — legacy firewall writes on a ZBF-migrated site (Fix 1)

Observed on 10.6.109, a release the plan treated as *pre*-migration baseline. This site's migration has already happened, which made the N1 question answerable one release early:

- `GET rest/firewallrule` → **0 rules**; `GET v2 firewall-policies` → **78 policies** (`step2_legacy_list_raw.json`, `step2_v2_policies_raw.json`).
- `POST rest/firewallrule` → **HTTP 400 in all 15 probed `rule_index` bands** (1, 999, 1000, 1999, 2001, 2500, 2999, 3000, 3001, 3999, 4000, 5000, 9999, 10000, 65535), via the public `create_firewall_rule` tool (`step2_legacy_index_probe.json`). Two error flavours: `api.err.InvalidPayload` + `api.err.InvalidValue` (empty `validationError` object) and `api.err.FirewallRuleIndexOutOfRange` — the 2000-2999/4000-ish bands get the latter, everything else the former. **No band accepts a write.**
- Failure is **loud, never silent**: the tool raises `APIError`; nothing lands in the legacy table or in v2 policies. This is exactly the behaviour the risk register asks for ("treat a silent no-op as a write failure") — the controller itself fails the write.
- `update_firewall_rule` / `delete_firewall_rule` against a legacy id on this site raise `ResourceNotFoundError` **client-side** (the tools read the legacy list first), so the API surface is never even hit (`step2_update_missing.json`, `step2_delete_missing.json`).
- `rest/firewallgroup` mutation is **fully functional**: create → update → delete of a throwaway port group all succeeded through the public tools (`step2_firewallgroup_cleanup.json`), and the group appeared via the Integration API's `traffic-matching-lists` while it lived.

**Consequence for the repo:** the docstring steering shipped 2026-10-27 is directionally confirmed on 10.6.109 — on a migrated site the legacy rule *table* is read-only-empty and legacy *rule* writes hard-fail, so steer callers to the v2 policy tools. The remaining open piece is the same observation on Network 11 (the audit's actual target), plus the deprecation-note decision the plan gates on it. Note `block_flow_*` (`src/tools/traffic_flows.py`) routes through `create_firewall_rule`, so on a migrated site those tools fail the same way — worth a docstring pointer there too.

## N2 — site-UID stability (Fix 2)

"Before" record: `Default` = `88f7af54-98f8-306a-a1c7-c9349722b1f6`. No code change until a post-upgrade diff shows drift; the claim stays unverified as designed.

## N3 — stats tools against the statistics engine (Fix 3)

10.6.109 baselines (diff targets for the Network 11 run):

- `stat/report/hourly.site` (24h): 24 rows; key union `{num_sta, o, oid, site, time, wan-rx_bytes, wan-tx_bytes, wlan-num_sta, wlan_bytes}`. Note: the requested `bytes` attr is **absent** from the response rows on 10.6.109 (`step3_historical_stats_tool.json`).
- `stat/sitedpi` (`by_app`/`by_cat`): 1 row, `{}` — DPI counters empty; traffic identification runs via the flow engine on this controller. The tool's existing `note` covers this (`step3_dpi_statistics_tool.json`, `step3_sitedpi_*.json`).
- `stat/stadpi/{mac}`: 0 rows for an active client (`step3_stadpi_raw.json`).

Tool-half shipped this session: `statistics_note` rides every empty response from `get_historical_stats`, `get_speed_test_history`, `get_dpi_statistics`, `list_top_applications`, `get_client_dpi` (shared text in `src/utils/helpers.py:STATISTICS_RESET_NOTE`; the three bare-list returns became `{"samples"|"results"|"applications": [...]}` dicts to carry it).

## N4 — v2 `traffic-flows` continuity (Fix 4)

20 polls at 15 s over 5 minutes, all HTTP 200 (`step4_traffic_flows_poll.json`):

- **50-flow cap: confirmed** — every poll returned exactly 50 (`count_min == count_max == 50`).
- **Pagination params ignored: confirmed** — `{limit, offset, page_size}` returned 50 (`param_probes`).
- **Server-side filter non-functional: confirmed sharply** — `{"filter": {"protocols": ["udp"]}}` returned the identical 50 flows (11 TCP + 39 UDP) as the unfiltered call (`step4_filter_sharp_probe.json`). Client-side filtering in `traffic_flows.py` remains required.
- Record shape on 10.6.109: top-level `{action, category?, count, destination, direction, duration_milliseconds?, flow_end_time?, flow_start_time?, id, next_ai, policies, protocol, risk, service, source, time, traffic_data}`; `source{id, ip, mac, port, region}`, `destination{domains, id, ip, mac, port, zone_id, zone_name}`, `traffic_data{bytes_rx, packets_rx}` on a blocked-incoming sample (tx counters appear on allowed/outgoing records — union across polls shows both directions). Matches the model the tools parse.
- **Rolling-window churn: not observable here** — all 20 polls returned the same 50 flow ids. This is a quiet home gateway, not a busy one; the documented rolling behaviour from 10.2 stands untested by this run, and the 5-minute poll should be repeated on a busier gateway (or during a busy window) for the Network 11 comparison.

## N5 — External Network Lists URL-source property

`GET /integration/v1/sites/{uuid}/traffic-matching-lists` on 10.6.109 returns lists shaped `{type, id, name, items[{type, value}]}` — **no URL-source field exists on 10.6**, as expected for a Network 11 feature (`n5_traffic_matching_lists.json`). The field name is still **unconfirmed**: guessing it would silently produce non-URL-sourced lists (the plan's explicit warning). Blocked on a Network 11 controller (or version-local Integrations documentation), unchanged.

## N6 — fleets that cannot upgrade

The single device is a UDM — no USG anywhere in inventory (`n6_device_inventory.json`), so this fleet is *not* USG-gated and the `platform_compat` field correctly stays absent. The classic-server break remains label-only by design.

## What remains for the Network 11 run

1. Repeat steps 1–4 on the same controller after a Network 11 upgrade (an operator action — not performed here) and diff against this report.
2. Step 5's browser capture of the Live Flows UI terminate action — needs console UI credentials.
3. N5's field name on a Network 11 controller.
4. N1's confirmation on Network 11 specifically, then the deprecation-note decision.
