# sirkirby/unifi-mcp parity: negative findings

Four parity items were investigated and **none of them needs code**. Three
are blocked by a missing surface rather than by missing work, and one is
already at parity. This record exists so the same ground is not re-covered.

Comparison baseline: the sirkirby comparison of 2026-11-21, an external
dashboard goal file that is **not** part of this repository — it cannot be
consulted from here. The in-repo reconciliation record is
`docs/COMPETITOR_GAP_RECONCILIATION.md`. Nothing here changes the coverage
map or the dashboard.

Every official claim below is checked against a vendor source. Ubiquiti's
own agent-onboarding note for the Network API names the canonical discovery
chain used throughout this record — the root index at
`https://developer.ui.com/llms.txt` for "which APIs exist, current
versions", the per-service surface at
`https://developer.ui.com/{service}/{version}/llms.txt`, and the
machine-readable contract at
`https://developer.ui.com/{service}/{version}/openapi.json`
([ai-gettingstarted.md](https://developer.ui.com/network/v11.0.97/ai-gettingstarted.md)).
That matters for the Access finding: the root index is the vendor's own
statement of which APIs exist, not an inference of ours.

The same note states Network authenticates with an `X-API-Key` header, with
keys generated at `unifi.ui.com`, and that the Site Manager Connector
(`POST /v1/connector/consoles/{id}/proxy/...`) is the sanctioned cloud
to on-premises bridge "without a VPN". Both corroborate findings recorded
here and in the session-auth note.

## Summary

| Item | Finding | Evidence class |
| --- | --- | --- |
| UniFi Access (whole application) | **Ubiquiti publishes no Access API** — there is no spec to pin | Official (negative) |
| Protect alarm **rules** | **No documented rule surface at any published version** | Official (negative) |
| Site Manager tool parity | **Already at parity and beyond** — 16 tools vs their 9 | Repo + official spec |
| Network real-time events | **Event WebSocket upgrades, then closes without delivering** | Live (observed) |
| Supplied spec bundle | **Authentic, adds no endpoint**; Site Manager is unpinned | Official |

Two of the brief's premises did not survive checking; both are corrected in
their sections below.

---

## 1. UniFi Access — no official API exists

The task was to pin the official Access spec from `developer.ui.com` the way
the Protect spec is pinned, then map the competitor's 37–38 Access tools
against it.

**That cannot be done, because the artifact does not exist.** Ubiquiti's own
canonical index at `https://developer.ui.com/llms.txt` lists exactly six API
services:

| Service | Version |
| --- | --- |
| Network | v11.0.97 |
| Protect | v7.4.102 |
| Mobility | v1.0.0 |
| InnerSpace | v1.3.23 |
| Site Manager | v1.0.0 |
| Carrier Fabric | v1.0.0 |

UniFi Access is **not among them**, and it has no OpenAPI entry in the
specification list either. Direct requests for the obvious paths confirm it:

| URL | Status |
| --- | --- |
| `https://developer.ui.com/access/openapi.json` | 404 |
| `https://developer.ui.com/access/v1.0.0/openapi.json` | 404 |
| `https://developer.ui.com/unifi-access/openapi.json` | 404 |

So "pin the spec, then build against it" has no starting point. The
competitor reaches Access through two non-published paths, per their own
documentation:

1. An API key against the dedicated Access API port (default **12445**),
   used for reads and device listing.
2. A **console login** at `/api/auth/login`, proxied through
   `/proxy/access/api/v2/...`, which they state is *required* for door
   lock/unlock, credential management, policies, visitors and events.

Two consequences for this server:

* An Access **read** tranche might be reachable with a key, but only against
  an undocumented private API — the same evidence class as a bundle-derived
  route, with no vendor contract to validate shapes against.
* An Access **write** tranche needs username/password session auth, which
  this server does not have and should not acquire implicitly. See
  `session-auth-and-innerspace-design-note.md`.

No Access controller was available either, so even a read tranche could only
have been mock-evidenced.

**Recommendation:** do not start Access until Ubiquiti publishes a contract,
or until Elvis explicitly accepts a private-API implementation *and* decides
the session-auth question. Any coverage-map items for an Access family should
be created only after that decision — this record proposes none.

---

## 2. Protect alarm rules — no documented surface

The task was to assess whether the competitor's alarm **rule** CRUD
(`list/get/create/update/delete`) has a documented equivalent this server
could implement, given that `src/tools/protect_alarm.py` covers arm
profiles, settings and enable/disable but not rules.

It does not, and this was checked against the **current** spec rather than
only the pinned one:

| Spec | Paths | Alarm-rule paths |
| --- | --- | --- |
| Protect v7.4.96 (pinned here) | 61 | none |
| Protect v7.4.102 (current) | 61 | none |

The two path sets are **identical** — no paths added, none removed between
7.4.96 and 7.4.102. The only alarm-related paths in either are:

* `GET /v1/alarm-hubs`
* `GET|PATCH /v1/alarm-hubs/{id}`
* `POST /v1/alarm-hubs/{id}/outputs/{outputId}/trigger`
* `POST /v1/alarm-manager/webhook/{id}`

All four are already covered by this server (`protect_alarm_hubs.py` and
`protect_alarm.py`). There is no rule resource to read, create, update or
delete.

The competitor reaches rules through the UniFi OS Alarm Manager **when the
account is SuperAdmin**, falling back to the classic automations view
otherwise. That is a privileged private surface, and it is gated on an
account privilege this server deliberately does not require.

**Recommendation:** no implementation. Revisit only if a published Protect
version adds a rule resource.

**Correction on the pin.** An earlier draft of this record said the repo's
Protect pin was "one release behind" and should be refreshed. That was
wrong, and checking it properly showed why: `developer.ui.com` serves the
**same document** under both version paths. The repo's
`protect-api-spec-v7.4.96.json` and the vendor's
`protect/v7.4.102/openapi.json` are **equal when parsed** — identical 61
paths, identical 83 operations, identical 321 component schemas, and both
carry `info.version: 0.0.0`. Only byte-level formatting differs.

So there is no spec drift and nothing to refresh: bumping the pin would
change the filename and nothing else. The version in a Protect spec URL is
a documentation label, not a contract version. Worth knowing before anyone
spends time chasing a Protect spec upgrade.

---

## 3. Site Manager — already at parity, and the premise was wrong

The brief expected this server's Site Manager set to be "smaller on paper"
than the competitor's 9 read tools. **It is larger: 16 tools.**

| # | Tool |
| --- | --- |
| 1 | `list_all_sites_aggregated` |
| 2 | `get_internet_health` |
| 3 | `get_site_health_summary` |
| 4 | `get_cross_site_statistics` |
| 5 | `list_vantage_points` |
| 6 | `get_site_inventory` |
| 7 | `compare_site_performance` |
| 8 | `search_across_sites` |
| 9 | `get_isp_metrics` |
| 10 | `query_isp_metrics` |
| 11 | `list_sdwan_configs` |
| 12 | `get_sdwan_config` |
| 13 | `get_sdwan_config_status` |
| 14 | `list_hosts` |
| 15 | `get_host` |
| 16 | `get_version_control` |

Tool count is the weaker test, so the real check is spec coverage. All **10**
documented Site Manager v1.0.0 paths have an implementation:

| Documented path | Covered by |
| --- | --- |
| `GET /v1/sites` | `list_all_sites_aggregated`, and the cross-site tools |
| `GET /v1/devices` | `get_site_inventory` |
| `GET /v1/hosts` | `list_hosts` |
| `GET /v1/hosts/{id}` | `get_host` |
| `GET /v1/isp-metrics/{type}` | `get_isp_metrics` |
| `POST /v1/isp-metrics/{type}/query` | `query_isp_metrics` |
| `GET /v1/sd-wan-configs` | `list_sdwan_configs` |
| `GET /v1/sd-wan-configs/{id}` | `get_sdwan_config` |
| `GET /v1/sd-wan-configs/{id}/status` | `get_sdwan_config_status` |
| `* /v1/connector/consoles/{id}/*path` | the 10 `connector_*` tools, and the InnerSpace tools |

**Recommendation:** no code. The item is closed as parity-met.

**One thing to look at separately.** Several Site Manager client endpoints
are *not* in the published v1.0.0 contract: `internet/health`,
`sites/health`, `sites/{site_id}/health`, `sites/{site_id}/internet/health`,
`vantage-points` and `version`. Most notably, the client calls
`sites/{site_id}/isp/metrics` while the documented path is
`isp-metrics/{type}`. These are pre-existing and out of scope here, and they
could not be probed because the available Site Manager credential returns
**HTTP 401**. Worth its own verification pass when a working credential
exists.

---

## 4. Network real-time events — the stream closes before delivering

The task was to implement a bounded recent-events read following the
Protect WebSocket pattern from #319, *if* the Network event stream is
reachable under this server's existing auth.

It is reachable, and it still does not work. Probed live against Network
10.6.111 with the ordinary API key:

| Endpoint | Outcome |
| --- | --- |
| `wss://…/proxy/network/wss/s/{site}/events` | **Upgrade succeeds**, then closed |
| `wss://…/proxy/network/v2/api/site/{site}/events` | HTTP 404 (no such route) |
| `wss://…/wss/s/{site}/events` | HTTP 200 (not a WebSocket route) |

The first one is the interesting case. The HTTP upgrade is **accepted** — so
this is not an auth rejection at the handshake — and then the controller
closes the connection cleanly, with **no event frame ever delivered**:

| Attempt | Upgrade | Time to close | Close code | Reason |
| --- | --- | --- | --- | --- |
| 1 | 0.27s | 0.09s | 1000 (OK) | none |
| 2 | 0.24s | 0.08s | 1000 (OK) | none |
| 3 | 0.38s | 0.08s | 1000 (OK) | none |
| + `Origin` header | 0.24s | 0.13s | 1000 (OK) | none |

Reproducible 4/4, including with the `Origin` header a browser would send.
A clean 1000 with no reason and no frames is the controller accepting the
socket and then declining to stream to this caller.

So a bounded recent-events tool built on this would connect successfully and
return **zero messages, every time** — strictly worse than the existing
poll-based `list_events`, `list_alarms` and `list_client_connection_events`,
because it would look like "no events happened" rather than "this is not
available."

The likely requirement is a console session cookie, which is consistent with
the competitor's session-based listener, but **that is unverified**: no
session was attempted, because this server has no session auth and adding
one is a standing decision for Elvis.

**Recommendation:** no implementation. The existing poll-based event tools
remain the supported path. Revisit only if the session-auth question is
settled in favour of adding one, at which point this probe should be re-run
to confirm a session actually keeps the stream open.

Note also that the brief's own guardrail applies here: an always-on listener
daemon would be an architecture change, not a tool addition. Nothing in this
record proposes one.

---

---

## 5. Review of the supplied spec bundle (`~/inbox/unifi-api-spec`)

Six OpenAPI documents were supplied for review. All six parse, all six are
authentic, and together they independently confirm the Access finding above.

### Authenticity

Each file was compared against the live vendor URL it corresponds to. All
six are **byte-identical** to what `developer.ui.com` serves, so they are
unmodified official documents rather than exports or scrapes:

| File | OAS | Title | Paths | Ops | vs live vendor URL |
| --- | --- | --- | --- | --- | --- |
| `site-manager_v1.0.0_openapi.json` | 3.0.3 | UniFi Site Manager API | 10 | 14 | byte-identical |
| `network_v11.0.97_openapi.json` | 3.1.0 | UniFi Network API | 44 | 73 | byte-identical |
| `protect_v7.4.102_openapi.json` | 3.1.0 | UniFi Protect API | 61 | 83 | byte-identical |
| `innerspace_v1.3.23_openapi.json` | 3.1.0 | UniFi InnerSpace Integration API | 6 | 6 | byte-identical |
| `mobility_v1.0.0_openapi.json` | 3.0.3 | UniFi Mobility API | 7 | 8 | byte-identical |
| `carrier-fabric_v1.0.0_openapi.json` | 3.0.3 | UniFi Carrier / ISP Fabric | 8 | 11 | byte-identical |

### The bundle contains no Access spec

The bundle is exactly the six services the vendor's root index lists. There
is **no UniFi Access document**, which corroborates section 1 from a second
direction: the omission is not a gap in our retrieval, it is the shape of
Ubiquiti's published surface.

### Against what the repo already pins

No new endpoint appears anywhere. For all five services the repo pins, the
supplied document is **equal when parsed** to the pinned one — same paths,
same operations, same schemas:

| Service | Repo pin | Paths | Ops | Schemas | Parsed-equal |
| --- | --- | --- | --- | --- | --- |
| Carrier Fabric | `carrier-fabric-api-spec-v1.0.0.json` | 8 | 11 | 26 | yes |
| InnerSpace | `innerspace-api-spec-v1.3.23.json` | 6 | 6 | 0 | yes |
| Mobility | `mobility-api-spec-v1.0.0.json` | 7 | 8 | 17 | yes |
| Network | `scraped-api-spec-v11.0.97.json` | 44 | 73 | 380 | yes |
| Protect | `protect-api-spec-v7.4.96.json` | 61 | 83 | 321 | yes |

So the bundle adds no coverage. Its value is confirmatory, and it surfaces
two housekeeping items:

**1. Site Manager v1.0.0 is not pinned at all.** It is the only supplied
service with no counterpart in `scripts/`, yet the repo depends on it:
`src/api/site_manager_client.py` and the 16 Site Manager tools are built
against it, and section 3 above had to fetch it live to check coverage.
Pinning it would close that, and would let
`scripts/audit-spec-coverage.py` cover the Site Manager surface the same
way it covers the others. This is the one actionable item in the bundle.

**2. `scraped-api-spec-v11.0.97.json` is not a scrape.** Despite the
filename it is parsed-equal to the official `network/v11.0.97/openapi.json`,
including all 380 component schemas. The name implies lower-fidelity
provenance than the file actually has, which could lead someone to distrust
it or re-derive it unnecessarily. Worth renaming when something else touches
`scripts/`.

Neither item is a coverage change, so neither is actioned here.

---

## What would change these answers

1. **Access** — Ubiquiti publishing an Access API, or an explicit decision to
   build against the private one.
2. **Protect rules** — a published Protect version adding a rule resource.
3. **Site Manager** — a working Site Manager credential, to verify the six
   undocumented endpoints listed above.
4. **Network events** — a decision on session auth, then a re-probe.

## Sources

- Root index, "which APIs exist, current versions":
  <https://developer.ui.com/llms.txt>
- Network API agent onboarding, naming the discovery chain, the
  `X-API-Key` auth model and the Site Manager Connector bridge:
  <https://developer.ui.com/network/v11.0.97/ai-gettingstarted.md>
- Machine-readable contracts, fetched and compared directly:
  `https://developer.ui.com/{service}/{version}/openapi.json` for
  site-manager v1.0.0, network v11.0.97, protect v7.4.102,
  innerspace v1.3.23, mobility v1.0.0 and carrier-fabric v1.0.0
- Live probes against Network 10.6.111 using this server's own client and
  API key (host, site and credential redacted)
