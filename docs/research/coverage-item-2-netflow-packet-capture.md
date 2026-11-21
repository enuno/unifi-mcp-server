# Coverage Item 2 discovery: NetFlow export and gateway packet capture

**Status:** implemented; NetFlow live-verified, capture routes verified in error paths only
**Target:** direct UniFi OS console, Network 8.5+ through 11.x
**Verified against:** Network application `10.6.111` (UDM, model `UDMA69B`)
**Last researched:** 2026-11-21

## Executive decision

The official Network Integration API exposes neither NetFlow nor packet
capture. Both features are therefore implemented as direct-console-only tools
against private Network routes, with confirmation gates on every controller
mutation and on the capture download.

Evidence is sufficient to implement without inventing endpoints: every route
below was exercised against a live console with an API key, and the
discriminating responses are recorded verbatim.

## Evidence grading

| Grade | Meaning |
|---|---|
| **Official** | Ubiquiti developer specification, release note, or Help Center article. |
| **Derived** | Read from an authenticated controller application bundle. |
| **Observed** | Request executed against the live console and the response recorded. |

## 1. NetFlow/IPFIX export — live-verified

### Product and version evidence

Network 8.5.6 introduced gateway NetFlow versions 5, 9 and 10, requiring
UniFi gateway firmware 4.1+ and excluding Express and UXG-Lite.[1] The
current Help Center places it at **Settings > CyberSecure > Traffic Logging >
NetFlow (IPFIX)**.[2]

### Routes and verbs

| Operation | Console path | Method | Grade |
|---|---|---:|---|
| Read | `/proxy/network/api/s/{site}/get/setting/netflow` | GET | Observed |
| Read (alias) | `/proxy/network/api/s/{site}/rest/setting/netflow` | GET | Observed — byte-identical body |
| Write | `/proxy/network/api/s/{site}/set/setting/netflow` | POST | Observed — persisted |

`POST` is what the Network UI itself issues: the settings module defines
`SET_PATH = C1("set/setting")` and the submit helper defaults to
`method.POST`.[Derived] `PUT` to the same path also persisted in testing, but
`POST` is the verb the product uses and the one the implementation sends.

A `GET` on the write path returns `api.err.NotFound`, so the read and write
paths are genuinely distinct rather than one resource with two verbs.

### Observed record

```json
{
  "key": "netflow",
  "enabled": false,
  "port": 2055,
  "version": 10,
  "auto_engine_id_enabled": true,
  "export_frequency": 5,
  "refresh_rate": 20,
  "sampling_mode": "hash",
  "sampling_rate": 512
}
```

Responses use the legacy envelope `{"meta": {"rc": "ok"}, "data": [ ... ]}`.
Note that `server` and `network_ids` are **absent until first set** — they are
not returned with empty defaults.

### The write merges; it does not replace

This is the single most important behavioural finding, and it was established
by experiment rather than assumed:

- Posting the record with `sampling_mode` removed left the stored
  `sampling_mode` at `hash`. **Omitted keys keep their stored values.**
- Posting `server: ""` or `server: null` was rejected with
  `api.err.InvalidPayload` / `api.err.InvalidValue`.
- `DELETE` on the write path, on the `rest` alias, and on an `_id`-scoped
  variant all returned `api.err.NotFound`.
- `PUT /rest/setting/netflow/{_id}` returned `200` but also merged rather
  than replacing.

**Consequence:** no API route observed can remove a key once written, so a
field cannot be cleared by omission. The implementation therefore performs a
full read-modify-write and reads the record back to report a `verified` flag,
and the tool does not advertise a "clear this field" capability it cannot
deliver.

### Validation, confirmed live

| Field | Constraint | How established |
|---|---|---|
| `version` | `5`, `9`, `10` | Derived (UI enum `VERSION_5/9/10`) |
| `port` | `1024..65535` | Upper bound Observed — `70000` rejected `api.err.InvalidValue`, state unchanged. Lower bound Derived from the UI; not probed |
| `server` | non-empty while enabled | Observed — `""` and `null` rejected |
| `network_ids` | at least one network while enabled | Derived (UI requires one) |
| `sampling_mode` | `off`, `hash`, `random`, `deterministic` | Derived (UI enum) |
| `sampling_rate` | `2..16383` | Derived |
| `export_frequency` | `1..60` | Derived |
| `refresh_rate` | `1..2147483647` | Derived |
| `engine_id` | `1..127` for v5, else `1..2147483647` | Derived |

A rejected write left the stored record unchanged, so validation happens
before persistence: the tool can validate optimistically and surface the
server's rejection rather than pre-emptively refusing input the server would
take.

Only a *rejected* value proves a bound. Every range marked Derived above is
the UI's own constraint, encoded because it is the product's behaviour, not
because this pass measured it.

### NetFlow verification boundary

Verified: read, write, persistence, merge semantics, rejection of an empty
collector, port range enforcement, and that a rejected write is atomic.

Not verified: behaviour on Network 8.x/9.x/11.x, whether enabling export
actually emits flows to a collector (no collector was stood up), and any
Cloud Connector route — none was found, and the tools reject cloud mode.

**Probe residue, disclosed:** the live record now carries `server: " "` and
`network_ids: []` that it did not have before this investigation, because the
merge-only behaviour above makes them unremovable via the API. `enabled` is
still `false` and every pre-existing field is byte-identical, so export
remains off, but the console is not bit-for-bit as found.

Root cause, for the next person: both keys were **absent** before the probe,
and they were introduced before merge-only semantics had been established. On
a merge-only endpoint that first write is permanent. Probe such an endpoint by
varying a field that is already present and restoring its original value —
establish merge-vs-replace *before* introducing any key that is absent.

## 2. Gateway packet capture — routes live-confirmed, lifecycle not

### Product and version evidence

Network 8.5.6 added gateway packet capture by network and duration, on
gateway firmware 4.1+, excluding Express and UXG-Lite.[1] Network 9.1.120
changed capture output to `tar.gz`.[3] Network 10.1.84 added text/clipboard
result support.[4]

### Routes

All site-scoped under `/proxy/network/v2/api/site/{site}`. `{mac}` is the
target device MAC.

| Operation | Path | Method | Observed response |
|---|---|---:|---|
| Start | `/pcap-start` | POST | `405` on GET; `400 api.err.UnknownDevice` for a bogus MAC |
| Status | `/pcap-status/{mac}` | GET | `200` with the bare JSON string `"NOT_FOUND"` |
| Stop | `/pcap-stop/{mac}` | POST | `400 api.err.NoRunningPacketCapturing` |
| Download | `/pcap-get/{mac}` | GET | `400 api.err.NoPcapFileExist` |
| Download text | `/pcap-get/{mac}/txt` | GET | `406` with no capture present |

These are not guesses. The command names come from the UI's command enum
(`PCAP_START = "pcap-start"`, `PCAP_STOP = "pcap-stop"`), the path prefix from
its site-path constant (`/v2/api/site/{site}`), and the download suffix from
the UI's own download helper.[Derived] Each was then exercised live, and the
distinct, feature-specific error codes — `NoPcapFileExist`,
`NoRunningPacketCapturing`, `NoMonitoredInterfaces` — confirm the handlers
exist and are reached.

### Start payload, field requirements established by experiment

```json
{
  "mac": "<gateway-mac>",
  "network_id": "<network-object-id>",
  "traffic_type": "WIRED",
  "duration": 60
}
```

Dropping one field at a time against a real gateway MAC separated required
from optional:

- Omitting `mac`, `network_id` or `traffic_type` produced a field-validation
  error. **All three are required.**
- Omitting `duration` passed validation and reached
  `api.err.NoMonitoredInterfaces`. Optional, with a server default.
- `duration: 5` produced a field-validation error, so *some* lower bound is
  enforced server-side; `duration: 30` passed. Neither `29` nor `300` was
  probed, so the exact `30`-`300` range the tool enforces is UI-derived (the
  form's own default and range), not measured. The tool may therefore refuse
  a duration the console would accept.
- A `cmd` key is **not** required; requests without it behaved identically.

`NoMonitoredInterfaces` for a bogus `network_id` is what kept these probes
from ever starting a real capture.

The shared UI helper also carries AP-only fields (`radio_bands`, radio
selection). Those are deliberately left to coverage Item 24 rather than
guessed into a gateway tool.

### Safety decisions

- Start and stop are confirmation-gated write tools with dry-run.
- Download is confirmation-gated too, because it writes private packet data
  to local disk.
- Only the filename component of `output_path` is honoured; the file lands
  inside `UNIFI_PACKET_CAPTURE_DOWNLOAD_DIR`, is opened without following
  symlinks, and is written mode `0600`.
- The tool returns path, size and SHA-256 — never packet contents.
- `pcap-status` returns a bare JSON string rather than an envelope, so it is
  passed through verbatim instead of being coerced into a record shape.
- Cloud Connector mode is rejected explicitly.

### Capture verification boundary

Verified: every route exists and is reachable with API-key auth; the required
start fields; that a lower duration bound is enforced; the status response
shape; and the stop/download error codes when nothing is running.

### Live capture run — the full lifecycle, executed

A complete capture was run on the local console (Network application
`10.6.111`, gateway `udm` / `UDMA69B`), against the **Home Lab network**
(VLAN 3) with a 30-second duration.

| Step | Call | Observed |
|---|---|---|
| 1 | `POST …/pcap-start` | `200`, empty body `{}` |
| 2 | `GET …/pcap-status/{mac}` | `"CAPTURING"` at t+10/20/30/40s |
| 3 | `GET …/pcap-status/{mac}` | `"READY_TO_DOWNLOAD"` at t+50/60/70s |
| 4 | `POST …/pcap-stop/{mac}` | `400 api.err.NotCapturingDevice` — **correct**: the capture had already finished on its own |
| 5 | `GET …/pcap-get/{mac}` | `200`, `application/gzip`, 626,941 bytes |

So the status enum is `NOT_FOUND` → `CAPTURING` → `READY_TO_DOWNLOAD`, and
`pcap-stop` on a finished capture is refused with `NotCapturingDevice`.

#### The artefact is a gzip-compressed tar, not a bare pcap

The downloaded bytes begin `1f 8b 08` — gzip — and untar them to a single
member `br3.pcap` (1,362,337 bytes). The inner file is a valid pcap:

- magic `d4c3b2a1`, **pcap version 2.4**, link type 1 (Ethernet), snaplen 128
- **12,916 packets**, parsed to the exact end of the file (no trailing bytes)
- independently cross-checked with `tcpdump -r`, which reports the same
  link-type and packet count

The tool's returned SHA-256 matches a recomputation over the file on disk, and
the file is written mode `0600`.

#### The `/txt` rendering is content-negotiated — a real defect this run found

`pcap-get/{mac}/txt` answered `406 Not Acceptable` on the first attempt. Probing
the route with each `Accept` header separately isolated the cause:

| `Accept` | Status |
|---|---|
| `text/plain` | **200**, `text/plain;charset=UTF-8`, 1,976,425 bytes |
| `*/*` | 406 |
| `application/json` | 406 |
| `text/csv` | 406 |
| `application/x-tar` | 406 |
| `application/gzip` | 406 |
| `application/octet-stream` | 406 |

The route serves the console's own **tcpdump-style text dump**, framed as
`===== BEGIN br3.pcap =====` … `===== END br3.pcap =====`, and it refuses every
media type except `text/plain`. The tool as first implemented sent no `Accept`
header at all, so httpx defaulted to `*/*` and the text variant could never
have succeeded. `download_bytes` now takes an optional `accept`, and the tool
sends `text/plain` for the text variant and nothing for the binary route.

Re-running the fixed tool against the live console returned 1,976,424 bytes
with a SHA-256, written mode `0600`. The text dump contains **12,916**
timestamped packet lines — the same count as the binary capture — and its first
and last packet timestamps match the binary file's.

The 406 seen earlier was therefore **not** evidence that `/txt` was
unavailable; it was evidence of a missing request header. That distinction is
the whole result of this run.

#### Still not verified

- **Retention**: how long the console keeps the finished capture, and whether
  the artefact is removed after the download, was not measured.
- The capture was taken on one network of one site. Other networks, `WIRELESS`
  traffic type, and the AP-radio variant (coverage item 24) remain unexercised.


## 3. Official API coverage check

The published Network OpenAPI documents for 10.6.106 and 11.0.97 contain 44
paths each, none matching `netflow`, `capture`, or `pcap`.[5][6] These tools
consequently use private direct-console routes by necessity, not preference.

The `v2` settings route `/v2/api/site/{site}/settings/netflow` claimed by a
reverse-engineered inventory returned `404` live; only its `/defaults`
sibling exists, returning UI defaults rather than stored state. That claim is
rejected, and the legacy `get`/`set` pair above is used instead.

## 4. Coverage decision

| Surface | Status | Evidence |
|---|---|---|
| NetFlow read | Implemented | Live-verified |
| NetFlow write | Implemented, read-modify-write | Live-verified incl. merge + validation |
| Capture start/status/stop | Implemented | Full lifecycle live-run: `CAPTURING` → `READY_TO_DOWNLOAD` |
| Capture download | Implemented, confined `0600` write | Live: gzip tar holding a valid 12,916-packet pcap; SHA-256 verified |
| Capture `/txt` rendering | Implemented, content-negotiated | Live: needs `Accept: text/plain`; 12,916 packet lines |
| Cloud Connector | Explicitly unsupported | No route found |
| AP-radio capture | Deferred to Item 24 | Shared route found; AP semantics out of scope |

Item 2 should be recorded as **covered**, with the retention behaviour and the
AP-radio variant noted as out of scope. The capture lifecycle, the artefact
format and the `/txt` rendering have all now been exercised against live
hardware; the `/txt` route additionally yielded a real defect, which is
fixed and regression-tested.

## Sources

1. Ubiquiti, [UniFi Network Application 8.5.6](https://community.ui.com/releases/UniFi-Network-Application-8-5-6/bfa15dd8-8b58-4d40-9d83-73ebe8c9a955).
2. Ubiquiti Help Center, [Traffic Flows and Traffic Logging in UniFi Network](https://help.ui.com/hc/en-us/articles/32201256219799-Traffic-Flows-and-Traffic-Logging-in-UniFi-Network).
3. Ubiquiti, [UniFi Network Application 9.1.120](https://community.ui.com/releases/UniFi-Network-Application-9-1-120/a5e88ae2-3c44-420a-bebb-5120bf2288b2).
4. Ubiquiti, [UniFi Network Application 10.1.84](https://community.ui.com/releases/UniFi-Network-Application-10-1-84/482c0a2f-5ab3-4c4b-9d0c-77e7bd38323d).
5. Ubiquiti Developer, [Network 10.6.106 OpenAPI](https://developer.ui.com/network/v10.6.106/openapi.json).
6. Ubiquiti Developer, [Network 11.0.97 OpenAPI](https://developer.ui.com/network/v11.0.97/openapi.json).
7. Ubiquiti Help Center, [Required Ports Reference](https://help.ui.com/hc/en-us/articles/218506997-Required-Ports-Reference) — TCP 28082 carries device capture transfer, and is not the controller API.

## Verification record

- Console: Network application `10.6.111`; gateway `udm` / `UDMA69B`.
- Authentication: console API key in `X-API-Key`. The controller address, the
  key, and the secret-store identifiers are **[REDACTED]** and are not
  committed.
- Authenticated UI bundles were analysed from scratch storage, not the repo.
  Hashes recorded at analysis time:
  - `settings.3ed975ba8d8cb232fbc4.js` — `882306521ee0cd21cff4deca76fbcf49cecf618f004fb30ac32ae77944357d65`
  - `swai.f8decf3e794da37f450a.js` — `e12b25d41f5f20b342746ec860da82ea6d9777ff9a48d9457e16029975a0acfa`
  - `83447.7aa1a0c38a350a707bc4.js` — `44bfc31177996c99688114fb65e3f1a47a954f17fe00e54f4dc45b56cce9f2e3`
- NetFlow configuration writes were executed and reverted as far as the API
  permits; the irreducible residue is disclosed above.
- One packet capture **was** started, and its artefact downloaded, during the
  live run described in section 2. It was a 30-second capture of the Home Lab
  network (VLAN 3) on the local console. The capture files live in a scratch
  directory outside the repository and are not committed; they contain private
  traffic and should be deleted by the operator.
