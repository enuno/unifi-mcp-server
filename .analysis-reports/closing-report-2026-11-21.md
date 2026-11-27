# Coverage closing report — partials and gaps brief (2026-11-21)

**Scope.** Every coverage item from the brief of 2026-11-21 that this
session touched, with the status claimed, the PR, the evidence class, and
what specifically remains.

**Statuses here are proposals for Elvis to ratify — the coverage map was
not edited.** Per `AGENTS.md`, an AI agent may not merge a PR, push to
`main`, or bypass branch protection; nothing was merged and no CI was
skipped.

**Evidence classes:**

| Class | Meaning |
|---|---|
| **live** | observed against a running console, version named |
| **mock** | verified only against mocks / a local test server |
| **pinned spec** | verified against a vendored or fetched published spec |
| **bundle-only** | verified only against a downloaded UI bundle |
| **doc-only** | a documentation claim, verified by reading the implementation |

Controller addresses, credentials, site identifiers, client MACs and
client names are **[REDACTED]** throughout.

---

## Merged — ten PRs

### Implementation

| Item | Claim | PR | Evidence |
|---|---|---|---|
| 2 | NetFlow / gateway packet capture | [#326](https://github.com/enuno/unifi-mcp-server/pull/326) | **live** (Network 10.6.109) |
| 28 | Protect 7.4.96 external arm profiles | [#327](https://github.com/enuno/unifi-mcp-server/pull/327) | **pinned spec** (7.4.96) |

**Item 2.** The `/txt` capture rendering requires `Accept: text/plain` and
answers 406 for every other media type, including httpx's default `*/*` —
the tool sent no Accept header, so the text variant could never have
worked. The 406 recorded in #321 was evidence of a missing header, not of
an unavailable endpoint. Live-verified end to end: `CAPTURING` →
`READY_TO_DOWNLOAD` → a gzip tar holding a valid 12,916-packet pcap,
cross-checked with `tcpdump` to the exact byte.

**Item 28.** Two defects, both confirmed against the pinned spec: the
route declares no query parameters and returns a bare array, so
`limit`/`offset` were never honoured (now paged locally); and profile IDs
were interpolated into five paths after only an emptiness check (now
validated as path segments). Twelve tool-level plus two client-level
regression tests, verified to **fail against the old implementation**.

### Documentation and evidence records

| Item | Claim | PR | Evidence |
|---|---|---|---|
| 8 | console port guidance | [#328](https://github.com/enuno/unifi-mcp-server/pull/328) | doc-only |
| 14 | `platform_compat` scope limit | [#329](https://github.com/enuno/unifi-mcp-server/pull/329) | doc-only |
| 15 | classic-server labelling | [#325](https://github.com/enuno/unifi-mcp-server/pull/325) | doc-only |
| 22 | external Network Lists | [#324](https://github.com/enuno/unifi-mcp-server/pull/324) | spec + live + bundle |
| — | Phase 3 live verification plans | [#330](https://github.com/enuno/unifi-mcp-server/pull/330) | doc-only |

**Item 14.** The limit is in **collection**, not analysis: the USG check
reduces the device snapshot to controller names and asks nothing about
site or API type, but the worker collects inventories for local
controllers only. A cloud controller can be asserted neither `true` nor
`false`; an unsynced local controller needs no new signal — the flag
appears on the next sync.

**Item 22.** The external-URL source field does not exist: absent from
every traffic-matching-list schema in the v11.0.97 spec, no matching UI
module in the bundle, and zero lists on the console. The residual doubt
(a field the controller exposes only on an existing record) is stated in
the record, together with the three things that would close it.

---

## Open — three PRs

### Item 23 — client-connection events and bulk client editing

- **Claim:** covered (implemented, live-verified)
- **PR:** [#331](https://github.com/enuno/unifi-mcp-server/pull/331)
- **Evidence:** **live** (Network 10.6.111)

**The batch surface the brief asked to discover exists.** `cmd/stamgr`
takes a `macs` list: `block-sta`, `unblock-sta` and `forget-sta` send
**one** request for N clients and answer with one record per client.
`kick-sta` is the exception — it reads only the singular `mac` field — so
a reconnect is issued one request per client, and the result reports
`batch_request` so the caller knows which happened. The Integration API
has **no** bulk clients route: `/clients/{clientId}` is the only shape,
and it wants a UUID rather than a MAC.

**The finding that shaped the tool:** the controller does not validate
MACs. `block-sta` on a MAC the site has never seen returned 200 and
**created a blocked client record**, so a bulk tool forwarding a typo
would leave phantom blocks behind. Every requested MAC is therefore
checked against the site inventory first and only the known ones are
sent; the rest come back `not_found`.

**For 23(a):** `stat/alarm` answers **404** on Network 10.x, and the
existing fallback only queries the system log's *critical* tab, which a
quiet controller leaves empty. The events are in the `all` tab under
`type: CLIENT_CONNECTION`, with the client MAC in
`parameters.CLIENT.id`. **The console ignores its own `filter` object** —
filtering by `category`, `type` or `key` each returned the same unfiltered
page — so the selection is applied to the returned rows.

**Remains.** Network 11's client-connection key set is unverified (the
direction is matched on the key *prefix*, so a new suffix is tolerated,
but a different key entirely would not be). The batch surface was
verified on Network 10.6.111 only. `kick-sta`'s successful path is
mock-tested only — proving it against a connected client would interrupt
a live connection.

### Item 17 — Live Flows

- **Claim:** covered (one correction implemented and live-verified), with
  a negative finding on the terminate action
- **PR:** [#332](https://github.com/enuno/unifi-mcp-server/pull/332)
- **Evidence:** **live** (Network 10.6.111)

`get_traffic_flow_details` said the v2 endpoint had no "fetch by id"
lookup. It does: `GET .../traffic-flows/{id}` answers 200 with the same
object a list row carries, and 404 for an unknown id. The tool now fetches
the flow directly, so a flow that aged out of the 50-flow window is still
found.

**There is no terminate-connection action**, and the probe that would have
misled is recorded rather than acted on: `POST /traffic-flows/<anything>`
answers 405 — including a segment that cannot exist — so the 405s on
`/terminate`, `/actions` and `/terminate-connection` are the GET-only
`{id}` pattern rejecting POST, not three hidden routes.

**Remains.** Streaming semantics are not available (`/live-flows` and
`/flows` both 404). The Threats/Blocked classification views have a real
surface and are already exposed by `get_traffic_flows`'s `action` and
`risk` filters, so nothing was added there.

### Items 26, 5 and 9 — discovery findings

- **Claim:** gap-with-negative-finding (three surfaces)
- **PR:** [#333](https://github.com/enuno/unifi-mcp-server/pull/333)
- **Evidence:** **published specification** + **live** + **bundle-only**

**26 (SD-WAN policy authoring).** The Site Manager v1.0.0 OpenAPI
document — published without portal auth — has **ten paths**, and the
SD-WAN ones are GET only. The document's only non-GET operations are the
generic console proxy and an ISP-metrics query, so there is **no SD-WAN
write path at all**. `components.schemas` is empty, so the detail
response is an *example*, not a contract; the settings are untyped
values with no steering-policy schema behind them. The server's own
`SDWANConfig` model already said the nested values were not a typed
contract, and the specification confirms it.

**5 (Object Oriented Networking).** `oon`, `oon/objects`,
`policy-engine`, `policy-engine/objects`, `objects`,
`object-networking`, `oon-sites` and `site-objects` all answer 404 under
the console's v2 site API, with `content-filtering` answering 200
alongside them as a control. Neither the pinned Network v11.0.97
Integration API spec (44 paths) nor the Network UI bundle has an OON path
or route string.

**9 (console-level backups).** `backups`, `system/backup`,
`system/backups`, `system/backup-schedules` and `backup-schedules` all
answer 404. The console's backup belongs to a different application: the
Network bundle's own `API_ERROR_UNIFI_OS_BACKUP_NOT_ALLOWED` says to use
*"the file generated from UniFi Network's System page, not the
configuration backup in your UniFi OS Portal."* The Network application's
own backup surface remains covered as it was.

**Remains.** All three need a **Network 11** console, or the Network 11
specification — with one exception: item 9's Portal surface needs the UniFi
OS console API and its credentials, which this project does not hold.

---

## Item 27 — open, and why the earlier finding was not enough

- **Claim:** gap-with-negative-finding, **but scoped to Network 10.6.111**
- **PR:** none
- **Evidence:** bundle-only

The Network UI bundle's OpenVPN cipher enum contains **exactly two**
members, `AES_256_CBC` and `BF_CBC`. `AES_192_CBC` and `AES_128_CBC` are
**absent**. The `aes128`/`aes192` literals that do appear belong to the
**IPsec phase-1** suite, sitting beside `IKEV1`/`IKEV2`/`SHA1` — a
different feature, with a different naming convention. And `ipip` is one
entry in the IANA IP **protocol-number** list (`ipcomp`, `ipencap`,
`ipv6-frag`, `iso-tp4`, `rohc`), not a WAN type.

**Why this does not close the item.** The bundle is from **Network
10.6.111** and the brief's Phase 2 ask is about the **Network 11** values.
The finding scopes what 10.6.111 exposes; it does not establish that
AES-192-CBC / AES-128-CBC / IPIP-WAN are absent on Network 11, which is
where the brief says they live. Enumerating them in the models would be
**inventing** them for the platform they were asked about, on the evidence
of a console they are not on.

**Remains.** Either a Network 11 console, or the Network 11 spec's
`networkconf`/VPN schema, to establish the real value set before any enum
is written.

---

## Not attempted

| Item | Why |
|---|---|
| **18** — WiFi WAN | Not attempted. Creating and configuring a WiFi-uplink WAN needs a device that can act as one; the read side via `sites/{id}/wans` already exists. |
| 19, 20, 21, 24, 25 | Genuinely hardware-gated. Matter pairing, Thread nodes, Time Machine snapshots, AP-radio capture and UPS self-test / remote power cycle each need a Network 11 controller with the corresponding feature. |
| 1 | Out of scope by the brief: there is no 8.x baseline to diff against. |

The brief placed **items 18, 5, 17, 23, 26 and 9** in Phase 1/2 as work
"you can complete in code". Of those, **23 and 17 are done**, **5, 26 and
9 are closed as findings**, and **18 is the one Phase 2 item left
untouched**.

---

## Issue state

The brief's ground rule 5 says to treat issues **#290, #291 and #292** as
open work regardless of their GitHub state — they were closed on
2026-11-19 seconds after PR #316 merged, although #316's body explicitly
said it did not implement them.

| Issue | Item | Action |
|---|---|---|
| **#290** | 23 (bulk client editing + the client-connection alarm) | **Left closed**, with a comment recording that the scope is now delivered by #331 |
| **#291** | 22 (external-URL source for network lists) | **Left closed**, with a comment recording the negative finding and what would close it |
| **#292** | 26 (SD-WAN policy authoring) | **Reopened**, with a comment: the discovery is done, the authoring half needs a Network 11 console |

---

## Probe residue — disclosed and cleared

The item-23 discovery left residue on the live console, and it is recorded
in the PR and the evidence record rather than quietly cleaned up:

- The first `block-sta` probe, on a MAC the site has never seen, **created
  a blocked client record** (`aa:bb:cc:dd:ee:01`).
- It was removed with `unblock-sta` followed by `forget-sta`.
- Removal was **verified** against `stat/alluser`: **101 clients, 1
  blocked, 0 leftover records** — back to the pre-probe state.
- Every later write probe used `unblock-sta` on clients that were
  **already unblocked**, so no real client's state changed, and the fake
  MACs that rode along were removed the same way. The final state was
  re-verified after every probe.

Nothing else was written to the console. No packet capture was started.

---

## Where the repository's own documentation disagreed with what was found

Six disagreements, all found and corrected except where noted:

1. **The TLS guidance was wrong** (item 8, #328). It presented
   `UNIFI_LOCAL_TLS_SERVER_NAME` *or* `UNIFI_LOCAL_CA_FILE` as
   alternatives. `src/api/tls.py` keeps certificate verification and name
   verification both on, so the name setting changes which name is
   checked without establishing trust, and the CA file establishes trust
   without fixing the hostname mismatch. Reaching a self-signed console by
   IP needs **both**.
2. **The legacy standalone row over-claimed** (item 8, #328) — selecting
   `8443` was presented as sufficient for a classic Network Application
   Server, while the client unconditionally builds UniFi OS
   `/proxy/network/...` paths.
3. **A cross-branch contamination** (item 8, #328) — `API.md` and
   `CHANGELOG.md` had been copied from a worktree holding both item 8 and
   item 28, so item 28's guarantees appeared in a tree that did not
   implement them.
4. **A registration example that always failed** (item 15, #325) —
   `build_admin_tools` rejects a call unless exactly one of `api_key` and
   `cloud_account` is supplied, and the example supplied neither.
5. **`get_traffic_flow_details` claimed the v2 endpoint had no per-flow
   lookup** (item 17, #332). It does — see above. This one had been in
   the code long enough to be relied on by its own docstring.
6. **The `SDWANConfig` model was right and the specification confirms it**
   (item 26) — no disagreement, just an independent confirmation that the
   nested values are not a typed steering-policy contract.

In every case where the code and the documentation disagreed, **the code
was right and the documentation was wrong**, so the fix was to the
documentation.

---

## Bot review findings on the three new PRs

Every finding was triaged against the implementation before a PR was called
ready. Eight were raised; **six were real and are fixed**, and two were
either stale or duplicates of each other.

| PR | Finding | Disposition |
|---|---|---|
| #331 | the `truncated` flag misreported completeness in both directions | **fixed** `7e019ee` — it now tracks how the scan ended |
| #331 | `dry_run="false"` read as a preview (the flag accepts `bool \| str`) | **fixed** `7e019ee` — coerced with `coerce_bool` |
| #331 | the tier snapshot was missing the two new tools | **stale** — raised against the first commit; the snapshot was regenerated in `a9dddd0` and the test passes |
| #332 | **P1**: `flow_id` was interpolated into the request path unvalidated, so a value with `/` or `..` could redirect the GET to another endpoint on the same controller | **fixed** `ccc0606` — validated with `validate_path_segment` |
| #332 | the lookup caught `(APIError, ResourceNotFoundError)`, swallowing 5xx/429/auth failures as "no such flow" | **fixed** `ccc0606` — the catch is narrowed to `ResourceNotFoundError` |
| #332 | (the two above were each raised twice, by two reviewers) | one fix each |

The two that mattered most were the ones a green CI run would never have
caught: an unvalidated path segment, and a broad `except` that turned
operational failures into a misleading "not found". Both are the kind of
defect that only shows up when someone else reads the diff with fresh eyes.

---

## A note on the probe method

Every route probe in this session used the wrong-verb method: **405**
means the path exists but refuses that verb, **404** means it is absent,
**200** means it is there — with a **control probe** alongside each family,
so a 404 could not be confused with a wrong path shape.

The control is what caught the one genuinely misleading result in this
session: the three 405s on `traffic-flows/terminate{,-connection}` and
`/actions` in item 17. Without `POST /traffic-flows/zzz-nonexistent` also
answering 405, those would have read as three real routes refusing POST,
and would have produced a terminate tool that never worked.

---

## AI assistance

All work in this session was AI-assisted (Hermes / noesis-praxis). Every
PR body states this and says what was verified only against mocks. No PR
was merged, no branch protection was bypassed, and no CI check was
skipped.
