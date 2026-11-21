# Coverage item 22 — External Network Lists: negative finding

**Status:** gap-with-negative-finding. The external-URL source field does not
exist in the documented surface, and no live controller available to this
project exposes one.

**Scope:** the external-URL source field of traffic matching lists, and its
wiring into traffic-matching-list create/update.

## What the brief asked for

> The external-URL source field was absent in the 10.6 capture and its name is
> still unconfirmed. Re-probe on current firmware; if the field now exists,
> model it and wire it into traffic-matching-list create/update with the
> typed-item constraints from the #287/#288 fixes.

The brief's own expectation is conditional: **if** the field exists, model it;
otherwise record the negative finding. This document is that negative finding,
with the evidence.

## Evidence grading

| Grade | Meaning |
|---|---|
| **Official** | Ubiquiti published specification, here the vendored `scripts/scraped-api-spec-v11.0.97.json`. |
| **Derived** | Read from that specification's schemas and parameter definitions. |
| **Observed** | Request executed against the live console and the response recorded. |
| **Bundle-only** | Read from an authenticated controller application bundle, with no live request confirming it. |

The controller address, credentials and site identifiers are **[REDACTED]** and
are not committed.

## Evidence

### 1. The published specification has no such field

`scripts/scraped-api-spec-v11.0.97.json` (Network 11.0.97) defines:

```
POST /v1/sites/{siteId}/traffic-matching-lists
```

with a request body of `Create or update traffic matching list`. That schema is
a discriminator over three per-type DTOs:

| Schema | Properties | Required |
|---|---|---|
| `Create or update traffic matching list` (base) | `name`, `type` | `name`, `type` |
| `IntegrationPortTrafficMatchingListCreateUpdateDto` | `items` | `items`, `name` |
| `IntegrationIpV4TrafficMatchingListCreateUpdateDto` | `items` | `items`, `name` |
| `IntegrationIpV6TrafficMatchingListCreateUpdateDto` | `items` | `items`, `name` |

The read side, `Traffic matching list`, is the same shape plus `id`: `id`,
`name`, `type`, and the per-type `items`.

**A search of every traffic-matching-list schema for a property whose name
contains `url`, `source` or `external` returns nothing.** The only properties
any of them carry are the four above.

The `items` themselves are discriminators too — `PORT_NUMBER`,
`PORT_NUMBER_RANGE`, `IP_ADDRESS`, `IP_ADDRESS_RANGE`, `SUBNET` — each carrying
`value`, or `start`/`stop` for the range types. There is no "URL" item type and
no source discriminator.

### 2. The live console has no traffic matching lists to inspect

The Integration API route the tools use, read live against the local console:

```
GET /proxy/network/integration/v1/sites/{site-uuid}/traffic-matching-lists
-> 200, 0 records
```

So the console has no traffic matching list configured, and therefore no
existing record whose field set could be observed. The legacy `/rest/` route
family is not usable for this: `rest/trafficmatchinglist` and
`rest/trafficmatchinglists` both answer `400 api.err.InvalidObject`, and the
v2 spelling answers `404`.

This is the one part of the negative finding that is **not** closed: with zero
lists on the console, a firmware-gated field that the console only exposes on
an existing record could not be observed. Two things bound that:

- the specification is version 11.0.97, the current Network 11 line, and it
  carries no such field; and
- the 10.6.109 capture that the brief refers to already found the field
  absent, and this console (Network 10.6.111) is the same minor line.

### 3. The console's UI bundle carries no traffic-matching-list module

The authenticated Network UI bundles were mined for the traffic-matching-list
surface. There is **no** traffic-matching-list chunk or module among them — no
occurrence of `trafficmatchinglist` or `traffic-matching-list` in any of the
59 downloaded bundles.

The `source_type` and `external_source` strings that do appear belong to
**Simple App Blocking** (`source_type` switching between `DEVICE` and
`NETWORK`, with `source_devices` / `source_networks` / `app_ids`), and to
firewall rule source/destination type selectors. Neither is the traffic
matching list, and neither carries a URL.

The bundle does contain the WAN-type and VPN-type enums, which are useful for
coverage item 27 and are recorded there.

## Conclusion

**The external-URL source field is not part of the documented traffic-matching-list
surface.** It does not appear in the Network 11.0.97 specification's create,
update or read schemas, no traffic-matching-list UI module exists in the
controller bundle to reveal it, and the live console has no list whose field set
could be observed.

Therefore **no model, parameter or tool change is made for item 22.** Adding a
speculative `external_url` / `source` field would be inventing an endpoint,
which the brief's ground rules forbid. The item is recorded as a
gap-with-negative-finding rather than closed as covered.

## What would close the remaining doubt

One of:

1. A traffic matching list configured on the local console, whose read
   response could then be inspected for any field the specification omits.
2. A Network 11 console running a firmware whose bundle contains a
   traffic-matching-list module, which could be mined for the field name and
   its value shape.
3. Ubiquiti publishing the field in the Network Integration API specification.

Until one of those exists, the honest status is the negative finding above.

## Sibling observation, out of scope here

`src/models/traffic_matching_list.py` models the list types and the item
types, and `src/tools/traffic_matching_lists.py` wires them into create and
update with the typed-item constraints from the #287/#288 fixes. Those are
consistent with the specification and were not changed by this item.

## Sources

1. UniFi Network Integration API, vendored snapshot
   `scripts/scraped-api-spec-v11.0.97.json` in this repository — path
   `/v1/sites/{siteId}/traffic-matching-lists`, and the schemas
   `Traffic matching list`, `Create or update traffic matching list`,
   `IntegrationPortTrafficMatchingListCreateUpdateDto`,
   `IntegrationIpV4TrafficMatchingListCreateUpdateDto`,
   `IntegrationIpV6TrafficMatchingListCreateUpdateDto`, `Port matching`,
   `IPv4 matching`, `IPv6 matching`.
2. Authenticated Network UI bundles, analysed from scratch storage and not
   committed; hashes are recorded in the item 2 evidence record.
