# Coverage item 17 — Live Flows: per-flow lookup and the terminate-connection action

**Item 17 of the partials-and-gaps brief (2026-11-21).** The brief asks
for two things:

- *"Discover and expose the terminate-connection action"*, and
- *"streaming semantics and Threats/Blocked classification views **only if a
  real surface exists** — the v2 polling endpoint's limits are already
  documented, do not paper over them."*

**Status:** one correction implemented and live-verified; one negative
finding.

Controller address, credentials, site identifiers, client and flow
identifiers are **[REDACTED]** throughout.

The evidence class for the live work is **Network 10.6.111** (UniFi OS),
2026-11-21.

---

## 1. The repository's own claim was wrong — there IS a per-flow lookup

`src/tools/traffic_flows.py` said:

> *"Find a specific flow in the current 50-flow snapshot. Raises
> ResourceNotFoundError if the flow has rolled out of the window (**the v2
> endpoint has no "fetch by id" lookup**)."*

That is not true. Live probe of the v2 traffic-flows route:

| Request | Answer |
|---|---|
| `POST /proxy/network/v2/api/site/{site}/traffic-flows` | 200, 50 flow rows |
| `GET  /proxy/network/v2/api/site/{site}/traffic-flows/{real_id}` | **200**, the flow object |
| `GET  /proxy/network/v2/api/site/{site}/traffic-flows/{bogus_id}` | **404** |

The per-flow GET returns the **same object shape as a list row** — the key
sets are identical:

```
action, category, count, destination, direction, id, next_ai, policies,
protocol, risk, service, source, time
```

So the old behaviour was a workaround for a limitation that does not exist:
the tool fetched the whole 50-flow window and scanned it for the id, which
meant a flow that had aged out of the window could not be found even
though the controller still had it.

### What changed

`get_traffic_flow_details` now fetches the flow by id, and keeps the list
scan as a fallback for a controller that has the flow in the window but not
by id. The docstring is corrected, and the module's claim is gone.

Live check after the change:

```
flow id from the list: 6b020cbf99dcbc ...
tool -> id: 6b020cbf99dcbc action: blocked risk: low category: CONTENT_FILTERING_ADVERTISEMENT
MATCHES the list row: True
unknown id -> ResourceNotFoundError: traffic_flow '6b020cbf99dcbc1dbf0ffff' not found
```

Four unit tests cover it: the per-flow GET is used and the list is not
fetched; a flow outside the list window is still found; the fallback to
the list still works; an unknown id still raises.

---

## 2. There is no terminate-connection action — and the probe that could have misled

This is the part worth recording, because the obvious probe gives the
**wrong answer**.

Every candidate terminate route on `traffic-flows` answers **405 Method
Not Allowed** on POST:

| Probe | Answer |
|---|---|
| `POST /traffic-flows/actions` | 405 |
| `POST /traffic-flows/terminate` | 405 |
| `POST /traffic-flows/terminate-connection` | 405 |
| `POST /traffic-flows/{real_id}` | 405 |
| `POST /traffic-flows/{real_id}/terminate` | 404 |
| `POST /traffic-flows/{real_id}/actions` | 404 |
| `POST /traffic-flows` | **200** (the known list route) |
| `GET  /traffic-flows/{real_id}` | **200** |

Read naively, "405 on three different terminate paths" looks like three
real routes that simply refuse POST. **They are not.** The control probe
settles it:

```
POST /traffic-flows/zzz-nonexistent  -> 405
GET  /traffic-flows/zzz-nonexistent  -> 404
```

`POST /traffic-flows/<anything>` answers 405, whatever the segment is. The
route pattern is `/traffic-flows/{id}` and it accepts **GET only**. So every
405 above is the *same* `{id}` pattern rejecting POST, not evidence of a
terminate action.

**The correct conclusion: `traffic-flows` has no terminate-connection
action on Network 10.6.111.** The one genuine discovery is the per-flow
GET, which is GET-only like its parent.

This is the same trap the item-2 traffic-flows finding already recorded for
that endpoint's other parameters — *"pagination params ignored"*,
*"server-side filter non-functional"* — and it is why the control probe
matters: without it, a 405 read as "the route exists" would have produced
a terminate tool that never worked.

---

## 3. Threats / Blocked classification views — a real surface, already covered

The brief asks for these *"only if a real surface exists"*. It does, and
the repository already exposes it:

- each flow carries `action` (`blocked` / `allowed`), `category`
  (`CONTENT_FILTERING_ADVERTISEMENT`, …), `risk` (`low` / `medium` / …) and
  the `policies` that matched;
- `get_traffic_flows` already accepts `action` and `risk` as **client-side**
  filters, and `get_flow_risks` / `get_flow_statistics` already aggregate
  on them.

The one caveat the brief warns about is the one already documented on the
endpoint: the console's own `filter` object is **not** honoured for this
route (the same inert-filter behaviour the client-connection events show in
item 23), so the selection is done on the returned rows.

So there is **nothing to add** here, and the brief's "only if a real
surface exists" condition is met by the existing tools. This PR does not
change them.

---

## What remains

- **Streaming semantics are not available.** The route is a POST that
  returns a completed-flow snapshot; there is no subscribe/stream route
  under `/traffic-flows` or `/live-flows` (both `/live-flows` and `/flows`
  answer 404). The brief's "only if a real surface exists" condition is
  not met, so no streaming tool was written.
- **A Network 11 controller may add the terminate action.** The conclusion
  here is scoped to Network 10.6.111, where the client-connection alarm
  (item 23) is also not present in the form the brief describes.
- **The per-flow GET's behaviour on a flow that has aged out of the
  50-flow window was not exercised live** — the console's retention beyond
  the window is unknown. The lookup is strictly better than the previous
  list scan either way.
