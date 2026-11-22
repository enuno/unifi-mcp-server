# Coverage items 26, 5 and 9 — discovery findings

Three items from the partials-and-gaps brief (2026-11-21) that ask for
surfaces this project's console does not expose. Each was investigated
against the published specification and the live console, and each closes
as a **negative finding with a named limit** rather than an invention.

**Status: negative findings.** No code changes.

| Item | Surface sought | Outcome |
|---|---|---|
| 26 | SD-WAN policy authoring and typed policy visibility | **No authoring surface in Site Manager v1.0.0** — the SD-WAN routes are read-only, and the detail response carries no typed steering-policy contract |
| 5 | Object Oriented Networking objects on the Policy Engine | **No OON surface** on the console's v2 site API, the Integration API, or the UI bundle |
| 9 | Console-level backup schedules and local backup management | **Not a Network-API surface** — the console's backup belongs to the separate UniFi OS Portal service |

Controller address, credentials and site identifiers are **[REDACTED]**.

---

## Item 26 — SD-WAN policy authoring

### The reads are already aligned

`src/tools/site_manager.py` exposes `list_sdwan_configs`,
`get_sdwan_config` and `get_sdwan_config_status`, against Site Manager's
`sd-wan-configs`, `sd-wan-configs/{id}` and `sd-wan-configs/{id}/status`
paths (base `https://api.ui.com/v1/`). The brief agrees: *"Reads are
aligned to the documented Site Manager v1.0.0 endpoints since v0.9.0."*

### The authoring surface does not exist in v1.0.0

The Site Manager OpenAPI document is published without portal auth, the
same way the repository's other specs are fetched
(`scripts/fetch-specs.sh`):

```
GET https://developer.ui.com/site-manager/v1.0.0/openapi.json  -> 200, 247,388 bytes
```

**Every path in it — ten of them:**

| Path | Methods |
|---|---|
| `/v1/sd-wan-configs` | GET |
| `/v1/sd-wan-configs/{id}` | GET |
| `/v1/sd-wan-configs/{id}/status` | GET |
| `/v1/sites` | GET |
| `/v1/hosts` | GET |
| `/v1/hosts/{id}` | GET |
| `/v1/devices` | GET |
| `/v1/isp-metrics/{type}` | GET |
| `/v1/isp-metrics/{type}/query` | POST |
| `/v1/connector/consoles/{id}/*path` | GET, POST, PUT, PATCH, DELETE |

**Every non-GET operation in the whole document** is either the generic
console proxy (`/v1/connector/consoles/{id}/*path`) or an ISP-metrics
query. There is **no SD-WAN write path at all** — not create, not update,
not delete, not a policy sub-resource.

### And the typed policy contract is not there either

The SD-WAN detail response carries `settings` as **untyped** values:

```json
"settings": {
  "hubsInterconnect": null,
  "spokeToHubTunnelsMode": "scalable",
  "spokesAutoScaleAndNatEnabled": true,
  "spokesAutoScaleAndNatRange": "172.16.0.0/12",
  "spokesIsolate": true,
  "spokeStandardSettingsEnabled": false,
  "spokeStandardSettingsValues": null,
  "spokeToHubRouting": "geo"
}
```

The document's `components.schemas` is **empty** — it defines no schema at
all, so the SD-WAN response is an *example*, not a contract. The repository's own model already
said so, and the spec confirms it:

> `SDWANConfig`: *"The v1.0.0 list supplies id/name/type only. Detail
> includes settings, hubs and spokes; those nested values are **not a typed
> steering-policy contract**."*

### Conclusion

**SD-WAN policy authoring and typed policy visibility have no surface in
Site Manager v1.0.0.** The only way to write an SD-WAN configuration would
be the generic console proxy, which is a raw passthrough and yields no
typed contract — exactly what the brief's "discovery before invention" rule
rules out.

**What remains.** Issue #292's own title scopes the work to
**Network 11**: *"SD-WAN policies: destination and performance routing
(Network 11)"*. The console-side SD-WAN policy surface is a Network 11
feature; authoring needs a Network 11 console, and the typed contract has
to come from there.

---

## Item 5 — Object Oriented Networking

The brief: *"Model OON object types/fields as such on the Policy Engine
surface; today only adjacent pieces exist (v2 content-filtering CRUD,
Integration dns/policies)."*

### Route probes against the console's v2 site API

| Probe | Answer |
|---|---|
| `GET/POST /proxy/network/v2/api/site/{site}/oon` | 404 / 404 |
| `GET/POST .../oon/objects` | 404 / 404 |
| `GET .../policy-engine` | 404 |
| `GET/POST .../policy-engine/objects` | 404 / 404 |
| `GET .../objects` | 404 |
| `GET .../object-networking` | 404 |
| `GET .../oon-sites` | 404 |
| `GET .../site-objects` | 404 |
| **`GET .../content-filtering`** (control) | **200** |

The control matters: `content-filtering` sits under the same prefix and
answers 200, so the probe method works and the 404s are real absences
rather than a wrong path shape.

### The specification and the bundle agree

- The pinned **Network v11.0.97 Integration API** spec (44 paths) has **no**
  OON path. Its policy surface is `firewall/policies`, `dns/policies` and
  `content-filtering` — the "adjacent pieces" the brief names.
- The Network **UI bundle** contains **no** `policy-engine` or
  `object-networking` route string. (`oon` appears only as a substring of
  unrelated words.)

### Conclusion

**No OON surface is discoverable on Network 10.6.111** — not in the
console's v2 site API, not in the Integration API, not in the UI bundle.
Nothing was modelled, because there is no schema to model against.

**What remains.** OON is a Network 11 feature; the object types have to
come from a Network 11 console or the Network 11 documentation.

---

## Item 9 — Console-level backups

The brief: *"Discovery on the UniFi OS surface for multi-destination backup
schedules and local backup management; the Network-application backup
surface is already covered."*

The Network-application backup surface **is** covered — the repository has
eight tools over `cmd/backup` and the backup download route
(`src/api/client.py`).

### Route probes find nothing on the Network API

| Probe | Answer |
|---|---|
| `GET/POST .../backups` | 404 / 404 |
| `GET .../system/backup` | 404 |
| `GET .../system/backups` | 404 |
| `GET .../system/backup-schedules` | 404 |
| `GET/POST .../backup-schedules` | 404 / 404 |
| `GET /proxy/network/v2/api/backups` (controller-wide) | 404 |
| `GET /proxy/network/v2/api/backup-schedules` | 404 |

### The console's backup is a different application's backup

The Network UI bundle carries the message that says so:

```
API_ERROR_UNIFI_OS_BACKUP_NOT_ALLOWED:
  "Please use the file generated from UniFi Network's System page, not the
   configuration backup in your UniFi OS Portal."
```

The **UniFi OS Portal** is a separate service from the UniFi Network
application. The multi-destination backup schedules and the local backup
management the brief asks about live on the Portal, not on the Network API
this server talks to. The bundle also carries
`API_ERROR_INVALID_AUTO_BACKUP_MAX_FILES` ("Automatic backup storage is
full."), which confirms automatic backups exist — in the Network
application's vocabulary, on the routes that were already covered.

### Conclusion

**The console-level backup surface is not reachable from the Network API.**
It is a UniFi OS Portal surface, and the Portal's API was not probed here —
it is a different service with its own authentication.

**What remains.** Reaching the Portal's backup schedules needs the UniFi OS
console API and its credentials, which this project does not hold. The
Network application's own backup surface remains covered as it was.

---

## A note on how these were probed

Every route probe used the wrong-verb method the repository already
documents: **405** means the path exists but refuses that verb, **404**
means it is absent, **200** means it is there. A control probe was run
alongside each family so a 404 could not be mistaken for "the probe method
is wrong" — the same control that caught the misleading 405s in item 17's
terminate-action search.
