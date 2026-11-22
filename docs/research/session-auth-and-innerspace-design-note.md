# Session authentication: where it is actually required

A design note, not an implementation. It answers one question that recurs
across four parity items — *does this server need a username/password
console login?* — and records the evidence behind each answer so the
decision is Elvis's to make on facts rather than on a competitor's design
choice.

This server is **API-key only** today. It never performs a console login,
holds no username or password, and has no session lifecycle to manage. That
is a security property worth keeping unless something genuinely needs
breaking it.

## The short answer

| Item | Needs a console session? | Basis |
| --- | --- | --- |
| Matter / Thread reads (items 19, 20) | **No** | Live probe |
| InnerSpace reads | **No — already shipped without one** | Working code |
| UniFi Access reads | Probably not (separate API port) | Vendor-adjacent docs |
| UniFi Access **mutations** | **Yes** | Competitor's documented dual-auth |
| Protect alarm **rules** | Yes, and privileged | Competitor's SuperAdmin requirement |

So the answer is not "session auth, yes or no" for the whole server. It is
needed only for two specific write surfaces, and both are out of scope under
the current brief.

## 1. Matter and Thread do not need it

sirkirby/unifi-mcp implements these reads **session-only and refuses an API
key by design** (PR #1105: "key-only refusal (no request sent)").

It would be easy to read that as "the controller requires a session." It
does not follow, and the probe says otherwise. Against Network 10.6.111,
with this server's ordinary API key, in one run:

* `GET /proxy/network/v2/api/site/{site}/thread-networks` → **404**
* `GET /proxy/network/v2/api/site/{site}/matter/nodes` → **404**
* `GET /proxy/network/v2/api/site/{site}/trafficroutes` → **200** (control)
* `GET /proxy/network/v2/api/site/{site}/clients/active` → **200**

The API key is accepted on this exact route family. A route that rejected
key auth would answer 401, not 404. The 404s are route absence on Network
10.6, so no session path was added.

Full record: `matter-thread-network-11-discovery.md`.

**Residual risk, stated plainly:** this shows the *family* accepts key auth
on 10.6. It does not prove a Network 11 controller serves the Matter routes
to a key-authenticated caller. Only a Network 11 console settles that, and
if it refuses the key, these three tools return the refusal rather than
silently doing nothing.

## 2. InnerSpace already works without it

The premise that InnerSpace needs a console login does not apply here,
because this server already reads InnerSpace **through the Cloud Connector
proxy with the same API key as Site Manager**:

`https://api.ui.com/v1/connector/consoles/{console_id}/proxy/innerspace/...`

Six read tools exist today in `src/tools/innerspace.py`
(`list_innerspace_access_points`, `list_innerspace_floor_plans`,
`list_innerspace_inventory`, `get_innerspace_project`,
`list_innerspace_switches`, `download_innerspace_asset`), against the
official InnerSpace API `v1.3.23`, whose spec is pinned at
`scripts/innerspace-api-spec-v1.3.23.json`. Ubiquiti publishes InnerSpace as
a first-class API service.

A competitor reaching the same data by console login is an implementation
difference, not a capability gap. **No InnerSpace work is needed, and no
session path is needed to get it.**

The building-sensitivity concern is still real and is about *disclosure*,
not auth: a floor plan describes a physical building. `download_innerspace_asset`
should stay an explicit, per-asset call rather than anything that bulk-exports
plans, and floor-plan content should not be relayed into shared transcripts.
That is a usage guideline for the existing tools, not a reason to add auth.

## 3. Where a session genuinely is required

### UniFi Access mutations

Access runs a **dual-auth** model. Per its own documentation: an API key
path on the dedicated Access API port (default 12445) serves reads and
device listing, while door lock/unlock, credential management, policies,
visitors and events go through a **console login at `/api/auth/login`** and
are proxied via `/proxy/access/api/v2/...`.

So an Access read tranche may be reachable with a key; an Access *write*
tranche is not. This is the first place where session auth is unavoidable
rather than merely conventional.

It is also moot for now: **Ubiquiti publishes no UniFi Access API.** The
canonical index at `https://developer.ui.com/llms.txt` lists six services —
Network, Protect, Mobility, InnerSpace, Site Manager, Carrier Fabric — and
Access is not among them. There is no official spec to pin, so the brief's
"pin the spec" step cannot be satisfied as written.

### Protect alarm rules

The official Protect API has **no alarm-rule surface at any published
version**. Both `v7.4.96` (pinned here) and the current `v7.4.102` expose
61 paths with an identical path set, and the only alarm-related paths are:

* `GET /v1/alarm-hubs`
* `GET|PATCH /v1/alarm-hubs/{id}`
* `POST /v1/alarm-hubs/{id}/outputs/{outputId}/trigger`
* `POST /v1/alarm-manager/webhook/{id}`

All four are already covered by this server. Rule CRUD is reached by the
competitor through the UniFi OS Alarm Manager **when the account is
SuperAdmin**, falling back to classic automations otherwise — a privileged
private surface, not a documented API.

## 4. What adopting session auth would touch

Recorded so the cost is visible if Elvis ever wants it, for Access writes or
Protect rules:

1. **Credential handling.** Username and password, not just a key. New
   secret material in config, in the fleet registry's per-controller
   records, and in every deployment artifact (Compose, Helm, Ansible).
2. **Client lifecycle.** Login, cookie/CSRF token storage, expiry, re-login
   on 401, and concurrency control so parallel calls do not stampede the
   login route. The API-key client has none of this.
3. **Fleet mode.** Per-controller sessions multiply: N controllers means N
   live sessions to acquire, refresh and invalidate, with a connection cap.
4. **Audit and redaction.** A session is a new credential class to keep out
   of logs, audit records and support bundles.
5. **Blast radius.** A console admin login is materially more privileged
   than a scoped API key. A compromised config would leak full console
   admin, not a revocable key.
6. **Lockout.** Repeated failed logins can lock a console admin account,
   so a retry loop becomes an availability risk.

### Options

| Option | What it costs | What it buys |
| --- | --- | --- |
| **A. Stay key-only** (recommended) | Access writes and Protect rules stay out of reach | Keeps today's security posture; nothing to build |
| **B. Opt-in session, reads excluded** | Items 1–6 above, gated behind an explicit env flag, default off | Unlocks Access writes and Protect rules for operators who opt in |
| **C. Session as a general fallback** | Items 1–6, applied to every call path | Little: every surface this server needs today already answers to a key |

**Recommendation: Option A for now, Option B only when a specific approved
item requires it.** Nothing in the current parity set is blocked by key-only
auth except two write surfaces that are themselves blocked by a missing
official contract. Option C is the worst trade: maximum new attack surface
for capability this server does not currently need.

This is a decision item for Elvis, not something to adopt implicitly by
building a tool that happens to need it.
