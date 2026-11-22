# Matter and Thread inventory on Network 11 — discovery record

Coverage items 19 (Matter) and 20 (Thread). Related issue: #293.

This record documents how the Matter and Thread routes were established, and
draws an explicit line between what was observed live and what was derived
from a vendor artifact. Controller addresses, credentials, site UUIDs and
device identifiers are redacted throughout.

## Summary

| Question | Answer | Evidence class |
| --- | --- | --- |
| Does a published API expose Matter or Thread? | No | Official (negative) |
| Do the routes exist in Network 11? | Yes | Derived (vendor package) |
| Do they answer on Network 10.6.111? | No — 404 | Observed (live) |
| Is this server's API key refused on these routes? | No | Observed (live) |
| Has a successful Matter/Thread read been observed? | **No** | — |

## 1. The published contracts do not carry the feature

Both official contracts were parsed directly, not read from a cache:

* Site Manager `v1.0.0` (`https://developer.ui.com/site-manager/v1.0.0/openapi.json`)
  — 10 paths, none matching Matter or Thread.
* Network `v11.0.97` (`https://developer.ui.com/network/v11.0.97/openapi.json`)
  — 44 paths, none matching Matter or Thread.

So the feature is private-API only. This is a negative finding about the
*published* surface, and says nothing about the private one.

## 2. The routes were derived from the vendor artifact

The authentic Network Application package was obtained from Ubiquiti's own
firmware catalogue and checksum-verified before being trusted:

* product `unifi`, platform `uos-deb13-amd64`, version `v11.0.97-37231-1`
* MD5 expected and observed: `6f0359d2bc4c01eebd5f92bdacb6447d`

Its Spring route annotations were decoded from the private backend archive
(`internal-dependencies.jar`, SHA-256
`c9666d78e7c84ec97956df91156ba808a9810ff6bb25875b503db1611f844c97`),
yielding 599 route mappings. Eleven concern Matter or Thread. All of the
following carry the Swagger tag `Matter`, and the quoted text is the
vendor's own `@Operation(summary = ...)`:

| Verb | Path | Vendor operation summary |
| --- | --- | --- |
| GET | `/api/site/{siteName}/thread-networks` | List detected Thread networks for the site |
| GET | `/api/site/{siteName}/matter/nodes` | List the site's Matter nodes and their commissioning state |
| POST | `/api/site/{siteName}/matter/nodes` | Queue a Matter pairing code for commissioning |
| PUT | `/api/site/{siteName}/matter/nodes/{nodeId}` | Update settings for a Matter device |
| DELETE | `/api/site/{siteName}/matter/nodes/{nodeId}` | Unpair a Matter node from the site |
| POST | `/api/site/{siteName}/matter/nodes/{nodeId}/commissioning-window` | Open a pairing window so the Matter device can be added to another ecosystem |
| POST | `/api/site/{siteName}/matter/nodes/{nodeId}/identify` | Make a Matter device identify itself (blink) so it can be located |
| PUT | `/api/site/{siteName}/matter/nodes/{nodeId}/ai-icon` | Set the AI-generated icon shown for a Matter node |
| DELETE | `/api/site/{siteName}/matter/nodes/{nodeId}/ai-icon` | Remove the AI-generated icon shown for a Matter node |

The controller's web UI bundle confirms the same two read paths are what the
Settings > Matter page calls, as `/api/site/{siteName}/thread-networks` and
`/api/site/{siteName}/matter/nodes` under the v2 API base — i.e.
`/proxy/network/v2/api/site/{site}/...` through the local gateway proxy.

**Only the two GET routes are implemented.** The seven write routes are
recorded here as derived evidence for a future, separately-approved tranche;
nothing in this change can commission, unpair, identify or re-pair a device.

### Commissioning states

From the UI bundle, a node's `status` is one of:

`QUEUED`, `COMMISSIONING`, `PROVISIONING`, `COMMISSIONED`, `FAILED`,
`UNVERIFIED`, `REMOVED`

Failure causes seen alongside them include `COMMISSIONING_REJECTED` and
`MATTER_CONTROLLER_UNREACHABLE`. The model surfaces `status` as a plain
string so a state added by a newer controller passes through rather than
failing validation.

## 3. Live probe against Network 10.6.111

Probed with this server's own client and its ordinary API-key credential.

| Route | Result |
| --- | --- |
| `GET /proxy/network/v2/api/site/{site}/thread-networks` | **404** |
| `GET /proxy/network/v2/api/site/{site}/matter/nodes` | **404** |
| `GET /proxy/network/v2/api/site/{site}/trafficroutes` (control) | **200** |
| `GET /proxy/network/v2/api/site/{site}/clients/active` | **200** |
| `GET /proxy/network/v2/api/site/{site}/clients/history` | **200** |

The control route matters. It is in the same `/v2/api/site/{site}/` family
and was fetched with the same credential in the same run, and it answered
200. So the two 404s are **route absence on Network 10.6**, not an
authentication or authorization failure.

### The client inventory join is live-verified

`clients/active` answered 200 with records carrying the `type`
discriminator — observed values on this console were `WIRELESS` only, with
no `client_id` key on those records. The route and the discriminator field
are therefore observed; the `MATTER_THREAD` value is not, because it
requires a Network 11 site with a commissioned node.

## 4. The authentication question, answered against evidence

sirkirby/unifi-mcp's equivalent implementation is **session-only and refuses
an API key by design in their core** (PR #1105: "key-only refusal (no
request sent)"; maintainer review: "The session-only refusal ... match[es]
the patterns we settled on").

That is a design decision in their codebase. It is **not** evidence that the
controller requires a session, and this probe found no such requirement:
this server's API key is accepted on the exact `/v2/api/site/{site}/`
family these routes live in, and the Matter routes answer 404 (absent)
rather than 401 (refused).

Conclusion: no session-auth path is needed to attempt these reads, so none
was added. Whether a Network 11 controller *additionally* gates Matter
routes behind a session remains unverified and is the single open question
a Network 11 console would settle.

## 5. Deliberate exclusions

Two exclusions are security decisions, not oversights, and are each locked
by a regression test:

* **`setupCode`** — a Matter node's pairing code. Anyone holding it can
  commission the device into another Matter fabric, so it is a live
  credential. The field is confirmed real in the 11.0.97 schema: the
  application carries a `widenMatterNodeSetupCode` database migration.
  `MatterNode.from_api` reads an allowlist of keys, so a setup code cannot
  reach a result even if a future controller renames it.
* **Thread border-router internals** — `fingerprint`, `host`, `domainName`,
  `stateBitmap`, `sequenceNumber`, `backboneRouterPort`. Identification
  material with no operator-facing diagnostic value.

Matter fabric identifiers are reduced to a count (`fabric_count`) for the
same reason: a fabric ID identifies the owning ecosystem's trust domain.

## 6. What remains unverified

1. A successful (200) Matter or Thread read has not been observed. The
   response field names, their casing and their types are derived from the
   application artifact, not from a controller response.
2. Whether Matter routes are additionally session-gated or privilege-gated
   on Network 11.
3. Whether `clients/active` on Network 11 carries `MATTER_THREAD` records
   with a `client_id` that matches a node's `clientId` — the join these
   tools assume is documented in sirkirby's follow-up work but unobserved
   here.
4. The entire write surface in section 2, which is intentionally not built.

Closing these requires a Network 11 console with at least one commissioned
Matter node. Until then these tools are **implemented-needs-verification**.
