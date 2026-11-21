# Live verification plan — UniFi Network 11 upgrade (coverage items 12, 13, 16)

**Status:** prepared, not executed. No Network 11 controller is available to
this project, so nothing in this plan has been run.

**What this covers.** Three coverage items whose claims are settled by the
same event — a controller moving from Network 10.6 to Network 11:

| Item | Claim | Where it is recorded now |
|---|---|---|
| 12 | The statistics engine changed: history resets, and the new MODERN series appears | `docs/NETWORK_11_COMPATIBILITY.md` N3, and the `statistics_note` shipped in `src/utils/helpers.py` |
| 13 | Zone-Based Firewall auto-migration changes the legacy `rest/firewallrule` / `rest/firewallgroup` surface | `docs/NETWORK_11_COMPATIBILITY.md` N1, and the 10.6.109 baseline report |
| 16 | The site UUID may change across the upgrade | `docs/NETWORK_11_COMPATIBILITY.md` N2 — **UNVERIFIED, and this plan's job is to confirm or kill it** |

**The "before" half is already recorded.** The 10.6.109 baseline of
2026-10-29 (`.analysis-reports/live-controller-10.6-baseline-2026-10-29/`)
captured the pre-upgrade state of all three. The controller used was
Network `10.6.109` with one site, `Default`, UUID
`88f7af54-98f8-306a-a1c7-c9349722b1f6`, `internalReference: default`.

**This plan is the "after" half.** It is written to be executed against the
**same controller**, upgraded in place, so that the before/after diff is
meaningful.

**Recording.** Record the **verbatim** response bodies and status codes for
every step, into a directory beside the baseline captures. Controller
addresses, credentials and site identifiers are **[REDACTED]** and must not
be committed. Where a step says "compare against", the comparison target is
named with the baseline capture file it came from.

---

## Part 1 — Item 16: does the site UUID change? (do this FIRST)

**This is the only item here whose outcome can change a shipped behaviour**,
and it must be captured **before** anything else touches the site, because
the upgrade itself is the event being observed.

### 1.1 Capture the "before" state, on the same controller

Even though the 10.6.109 baseline exists, capture it again on the exact
controller you are about to upgrade, so the two captures are minutes apart
rather than days:

```
GET /proxy/network/api/s/default/stat/sysinfo
GET /proxy/network/api/s/default/rest/networkconf
GET /proxy/network/integration/v1/sites
```

Record, for **every site**:

| Field | Where |
|---|---|
| site UUID | `internalReference` in the integration `sites` list; `_id` in `networkconf` |
| short name | `internalReference` in the `networkconf` entry |
| display name | `name` |
| purpose | `purpose` (`site-vpn`, `corporate`, `wan`, …) |
| the site-to-site VPN peer | `ipsec_peer_ip`, `openvpn_remote_host`, and any `openvpn_remote_address` |

The VPN peer matters because a site-to-site VPN binds a peer by address: if
the site UUID changes, every reference to the old UUID — in a VPN peer
record, in a firewall policy, in an API key's scope, in a saved bookmark —
must be re-pointed, and that is a real operational cost worth quantifying
before it happens.

### 1.2 Upgrade the controller to Network 11

Record the exact application version before and after.

### 1.3 Capture the "after" state

Repeat the three calls from 1.1.

### 1.4 Diff

**The claim under test:** "site UID change on upgrade".

For each site, compare the UUID before and after.

- **Unchanged** → the claim is **refuted** for this controller. Record it as
  refuted with the version pair. Item 16 can then be closed as
  *no observed change*, and `DEVELOPMENT_PLAN.md` §4 Phase 8 Fix 2 and
  `docs/NETWORK_11_COMPATIBILITY.md` N2 should be updated to say so.
- **Changed** → the claim is **confirmed** for this controller. Record the
  old and new UUIDs, and then enumerate every place the old UUID was
  referenced. Check at minimum:
  - the site-to-site VPN peer records
  - `GET /integration/v1/sites/{old-uuid}/traffic-matching-lists` — does it
    still resolve, and does the new UUID resolve?
  - any API key scoped to a site
  - the fleet registry, if the controller is registered there

A single controller is one observation. A confirmed change is worth stating
as "observed on one controller, Network 10.6.109 → 11.x"; a refutation is
worth stating the same way. Neither is a general law, and the plan should
say so.

---

## Part 2 — Item 12: the statistics engine

### 2.1 Empty-history behaviour

Immediately after the upgrade, before any traffic accrues:

```
get_historical_stats(site_id="default", timeframe="24h")
get_speed_test_history(site_id="default", ...)
get_dpi_statistics(site_id="default", ...)
list_top_applications(site_id="default", ...)
get_client_dpi(site_id="default", ...)
```

Expected: each returns an **empty** history, and each carries
`statistics_note` — the shared text in `src/utils/helpers.py`
(`STATISTICS_RESET_NOTE`):

> An empty statistics history immediately after a UniFi Network 11 upgrade is
> the expected consequence of the statistics-engine change, not evidence of an
> outage or a broken tool; series re-accrue from the upgrade onward.

Record, for each: the status code, the shape of the result, whether
`statistics_note` is present, and the number of rows.

**The empty responses must carry the note.** A bare empty list without it is
a defect — that note is the entire difference between "the engine reset" and
"the tool is broken", and it is the reason those three bare-list returns
became dicts.

### 2.2 The MODERN series

Item 12's specific claim is that the new statistics engine serves a
**MODERN** series where the old one served a legacy shape. Compare against
the 10.6.109 baseline (`step3_historical_stats_tool.json`):

- `stat/report/hourly.site` (24h) — on 10.6.109 this returned **24 rows**
  with the key union
  `{num_sta, o, oid, site, time, wan-rx_bytes, wan-tx_bytes, wlan-num_sta, wlan_bytes}`.
  Note that the requested **`bytes` attribute is absent** from the 10.6.109
  rows.
- After the upgrade: record the row count and the **exact key union**. If a
  `MODERN` series is what the new engine serves, the row shape and the
  attribute set are where it will show.
- If the rows are still empty at this point, that is consistent with 2.1 —
  record it and re-check after traffic has accrued.

### 2.3 Re-accrual

Generate traffic (a speed test, some browsing) and re-poll after the
interval. Confirm the series **starts filling** and that `statistics_note`
disappears once history exists — the note must not linger on a non-empty
response, or it would misdescribe a working tool as reset.

This is the half of item 12 that distinguishes "the engine reset, as
expected" from "the engine is broken".

### 2.4 The other three stat surfaces

The 10.6.109 baseline recorded:

| Surface | 10.6.109 result | What to compare |
|---|---|---|
| `stat/sitedpi` (`by_app`/`by_cat`) | 1 row, `{}` — DPI counters empty; traffic identification runs via the flow engine on this controller | does it still return the empty-object row, and does the tool's own `note` still apply? |
| `stat/stadpi/{mac}` | 0 rows for an active client | still 0, or now populated? |
| v2 `traffic-flows` | 20 polls, all 200; **50-flow cap confirmed**; **pagination params ignored**; **server-side filter non-functional** (`{"filter": {"protocols": ["udp"]}}` returned the identical 50 flows) | repeat the three probes; the 50-flow cap and the ignored pagination are the load-bearing facts for `src/tools/traffic_flows.py`'s client-side filtering and slicing |

For `traffic-flows`, the baseline notes the **rolling-window churn was not
observable** on that quiet home gateway — all 20 polls returned the same 50
flow ids. If the upgrade target is a busy site, repeat the poll there and
record whether the window actually rolls; if it is the same quiet
controller, record that the churn remains unobservable rather than claiming
the behaviour was confirmed.

---

## Part 3 — Item 13: Zone-Based Firewall auto-migration

### 3.1 The legacy collection is empty

```
GET /ea/sites/{site}/rest/firewallrule
```

Compare against `step2_legacy_list_raw.json`: on the already-migrated
10.6.109 site this returned **0 rules**, while
`GET v2 firewall-policies` returned **78 policies**.

After the upgrade on a site that **had** legacy rules before the upgrade,
the expectation is the same shape: legacy reads empty, v2 policies carry
the configuration. If the legacy collection still returns rules after
migration, that is a finding — record it.

Record both counts.

### 3.2 Legacy rule writes are rejected — loudly

The 10.6.109 baseline probed 15 `rule_index` bands and **no band accepted
a write**:

> `POST rest/firewallrule` → HTTP 400 in all 15 probed `rule_index` bands
> (1, 999, 1000, 1999, 2001, 2500, 2999, 3000, 3001, 3999, 4000, 5000,
> 9999, 10000, 65535). Two error flavours: `api.err.InvalidPayload` +
> `api.err.InvalidValue` (empty `validationError` object) and
> `api.err.FirewallRuleIndexOutOfRange` — the 2000-2999/4000-ish bands get
> the latter, everything else the former.

Repeat the probe on Network 11 — at minimum the bands 1, 1999, 2001, 2999,
3000, 4000 and 65535, to sample both error flavours — and record the exact
error code and message for each.

**The property that matters is the loudness**, not the specific code: a
rejected write must fail with an error, never silently no-op. A silent
success on a migrated site would mean an operator believes they changed a
rule that did not change. Record whether the rejection is loud.

### 3.3 `rest/firewallgroup` mutations still work

On 10.6.109 this was **fully functional**: create → update → delete of a
throwaway port group all succeeded through the public tools
(`step2_firewallgroup_cleanup.json`), and the group appeared via the
Integration API's `traffic-matching-lists` while it lived.

Repeat the same create → update → delete cycle after the upgrade, and
confirm the group appeared via `traffic-matching-lists` while it lived.
**Delete the throwaway group** and confirm it is gone — leaving it behind
would pollute the site.

This asymmetry is the interesting part of item 13: the migration closes
`rest/firewallrule` writes but leaves `rest/firewallgroup` working. Whether
that holds on Network 11 is what the step settles.

### 3.4 The v2 surface is the live one

Confirm the v2 policy surface is usable for the same intent:

```
list_firewall_policies(site_id="default")
create_firewall_policy(site_id="default", ...)   # throwaway
update_firewall_policy(...)
delete_firewall_policy(...)
```

On the 10.6.109 site this reported 78 policies. Record the count and the
shape, and clean up anything you create.

---

## Part 4 — Close

Per item, record:

- **12** — did the empty responses carry `statistics_note`? did the series
  re-accrue? what did the MODERN row shape and key union look like?
- **13** — are legacy rule writes still loudly rejected? does
  `rest/firewallgroup` still mutate? are the v2 policies the live surface?
- **16** — did the site UUID change, stay the same, or partially change?

Then update the three records in the repository to match what was observed:

- `docs/NETWORK_11_COMPATIBILITY.md` N1, N2 and N3.
- `DEVELOPMENT_PLAN.md` §4 Phase 8 Fixes 2 and 3.
- `.analysis-reports/` — add this session's captures beside the 10.6.109
  baseline, with the controller address and site identifiers **[REDACTED]**.

**Where the console disagrees with the pinned documentation, the console
wins.** The spec and the release notes are published documents; the running
controller is the authority. Record the difference and re-pin the
documentation rather than the behaviour.

If item 16 shows a UUID change, that is an **operational** finding as well
as a coverage one: every stored reference to the old UUID has to be
re-pointed. Note which references exist in this project's own configuration
(`.env`, the fleet registry, the API key scopes) so the upgrade guidance can
say what to update.
