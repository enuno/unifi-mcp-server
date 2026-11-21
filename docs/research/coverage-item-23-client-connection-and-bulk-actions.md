# Coverage item 23 — client-connection events and bulk client actions

**Item 23 of the partials-and-gaps brief (2026-11-21).** Two parts:

- **(a)** a dedicated tool for the client-connection alarm, and
- **(b)** bulk client editing — a batch surface, or safe fan-out with
  per-client result reporting.

**Status: implemented and live-verified** against the local development
console, **Network 10.6.111** (UniFi OS), on 2026-11-21.

Controller address, credentials, site identifiers, client MAC addresses and
client names are **[REDACTED]** throughout.

---

## (a) The client-connection events surface

### `stat/alarm` does not exist on Network 10.x

```
GET /ea/sites/default/stat/alarm              -> 404
GET /ea/sites/default/stat/alarm?archived=false -> 404
```

The brief points at `stat/alarm`, and `list_alarms` already falls back to the
v2 system log when that route 404s. But the fallback only queries the
**critical** tab:

```
POST /proxy/network/v2/api/site/default/system-log/critical -> 200, 0 rows
```

Zero rows: a quiet controller raises no critical events, so the existing
fallback cannot surface client connections at all.

### The events are in the v2 system log's `all` tab

```
POST /proxy/network/v2/api/site/default/system-log/all
  body: {"timestampFrom": ..., "timestampTo": ..., "pageNumber": 0, "pageSize": 500}
  -> 200, 500 rows
```

The vocabulary in those rows:

| Field | Values observed |
|---|---|
| `type` | `CLIENT_CONNECTION` (460 of 500), `ADMIN_ACCESS` (31), `AP_CHANNEL_CHANGE` (3), `BACKUP_CONNECTION_IN_USE` (2), `ISP` (1), `THREAT_DETECTION_AND_PREVENTION` (2), `FIRMWARE_UPDATE` (1) |
| `category` | `CLIENT_DEVICES` (460), `AUDIT` (31), `UNIFI_DEVICES` (3), `INTERNET_AND_WAN` (3), `SECURITY` (2), `SOFTWARE_UPDATES` (1) |
| `key` | `CLIENT_DISCONNECTED_WIRELESS_2` (235), `CLIENT_CONNECTED_WIRELESS_2` (225), plus admin/threat keys |
| `severity` | `LOW` (all 460 client rows) |
| `status` | `NEW` (all 460 client rows) |
| `target` | `CLIENT` |

Row shape — top level: `category, event, id, key, message_raw, parameters,
severity, show_on_dashboard, status, subcategory, target, timestamp,
title_raw, type`.

`parameters` carries the detail, under these keys:

`AUTH_METHOD`, `AVG_INTERFERENCE`, `AVG_UTILIZATION`, `CHANNEL`,
`CHANNEL_WIDTH`, `CLIENT`, `CONSOLE_NAME`, `DATA_DOWN`, `DATA_UP`,
`DEVICE`, `DURATION`, `IP`, `NETWORK`, `RADIO_BAND`, `SIGNAL_STRENGTH`,
`WIFI_STATS`, `WLAN`.

- `parameters.CLIENT` — `{id: <client MAC>, name, hostname, ip,
  device_fingerprint_id, fingerprint_source}` — **the client MAC is
  `parameters.CLIENT.id`**.
- `parameters.DEVICE` — the access point: `{id: <AP MAC>, name, model,
  model_name, version, ip, fingerprint_source}`.

### The console ignores its own filter object

Three server-side filter shapes were sent against the same window:

| `filter` sent | Rows returned | Type mix |
|---|---|---|
| `{"category": ["CLIENT_DEVICES"]}` | 500 | identical mix |
| `{"type": ["CLIENT_CONNECTION"]}` | 500 | identical mix |
| `{"key": ["CLIENT_CONNECTED_WIRELESS_2"]}` | 500 | identical mix |

Every shape returned the same unfiltered page. **The system log's `filter`
is inert**, so the type/key/client selection has to happen on the returned
rows.

### Pagination does work

| Request | Rows | First `id` |
|---|---|---|
| `pageNumber=0, pageSize=100` | 100 | `6b020bc1…f083a` |
| `pageNumber=1, pageSize=100` | 100 | `6b01e6cc…f0522` |
| `pageNumber=0, pageSize=1000` | 937 | `6b020bc1…f083a` |

Page 0 and page 1 share **0** ids, so `pageNumber` is honoured. The 937
rows are the whole 90-day window — the earlier 500 was exactly the
`pageSize` asked for, not a server cap. There is **no `totalCount` field**.

### What was built

`list_client_connection_events` in `src/tools/events.py` (a read tool):

- pulls the window page by page until enough matching events are found or
  the pages run out;
- selects `type == CLIENT_CONNECTION` on the returned rows, then the
  direction from the row `key`'s prefix, then an optional client MAC
  against `parameters.CLIENT.id`;
- normalises each row into the fields a caller wants (`event`, `timestamp`,
  `client_mac`, `client_name`, `client_ip`, `device_model`, `wlan`,
  `channel`, `signal_strength`, `auth_method`, `data_up`, `data_down`,
  `duration`, …);
- returns a `note` recording both console behaviours, so a caller is not
  left guessing why `stat/alarm` was not used.

**Live check:** 5 events returned from 500 scanned rows in one page, with
real client names, AP model, WLAN and channel.

**Caveat.** The `key` values carry a version suffix (`_2`). The direction is
matched on the prefix (`CLIENT_CONNECTED_WIRELESS` /
`CLIENT_DISCONNECTED_WIRELESS`), so a new suffix would not break the
filter. The `key` set for Network 11 is **not** verified — this console is
Network 10.6.111 and the brief's client-connection *alarm* is a Network 11
addition, so on Network 11 the events may carry a different key set.

---

## (b) The bulk client action surface

### There is a batch surface on `cmd/stamgr`

The brief said `cmd/stamgr` and the Integration API's `clients/{id}/actions`
are per-client "today", and asked for a batch surface to be discovered.

The repository already sent `forget-sta` with a **list**:

```python
json_data={"cmd": "forget-sta", "macs": [mac.lower()]}
```

Probing the same shape across the command vocabulary, with MACs that do not
exist on the site:

| Command | `macs` list | `mac` singular |
|---|---|---|
| `block-sta` | **200**, one record per MAC | 200, one record |
| `unblock-sta` | **200**, one record per MAC | 200 |
| `forget-sta` | **200**, one record per MAC | 404 |
| `kick-sta` | **500** | 400 `api.err.UnknownStation` |

So `block-sta`, `unblock-sta` and `forget-sta` **do** take the batch list —
the batch surface the brief asked to discover exists. `kick-sta` does not:
it reads only the singular `mac` field, and with the field absent it
answers an unhandled HTTP 500.

Two shapes are therefore needed, and the tool says which it used:

- `block` / `unblock` / `forget` — **one** request carrying `macs`;
- `reconnect` — one request per client, using the singular `mac`.

### The Integration API has no bulk clients endpoint

| Probe | Answer |
|---|---|
| `POST /integration/v1/sites/{site}/clients/actions` | 405 `METHOD_NOT_ALLOWED` |
| `GET /integration/v1/sites/{site}/clients/actions` | 400 `api.request.argument-type-mismatch` — `'actions' is not a valid 'clientId' value` |
| `POST /integration/v1/sites/{site}/clients/{mac}/actions` | 400 `api.request.argument-type-mismatch` — `'aa:bb:…' is not a valid 'clientId' value` |

The third answer confirms the route wants a **UUID**, not a MAC — which
matches what `authorize_guest` already documents. The second shows
`/clients/{clientId}` is the route shape, so `/clients/actions` is read as a
clientId and there is no plural collection route. **`cmd/stamgr` is the only
batch surface.**

### The controller creates records for MACs it has never seen

This is the finding that shaped the tool. `block-sta` on a MAC that is not
on the site:

```
POST /ea/sites/default/cmd/stamgr  {"cmd": "block-sta", "mac": "aa:bb:cc:dd:ee:01"}
-> 200 {"data": [{"site_id": "...", "mac": "aa:bb:cc:dd:ee:01", "blocked": true, "_id": "..."}]}
```

It **succeeded and created a blocked client record**. The controller does
not validate the MAC. A bulk tool that forwards a typo — or a stale client
list — would leave phantom blocked clients behind, and the operator would
see blocks they never asked for.

`bulk_client_action` therefore resolves every requested MAC against
`/ea/sites/{site}/stat/alluser` first and sends **only the known ones**.
Unknown MACs come back as `status: not_found` and are never sent.

### Probe residue — disclosed and removed

The first `block-sta` probe above created a client record on the live
console (`aa:bb:cc:dd:ee:01`, `blocked: true`). It was removed with
`unblock-sta` followed by `forget-sta`, and the removal was verified
against `stat/alluser`:

- before the probe: **101** clients, **1** blocked;
- after cleanup: **101** clients, **1** blocked, **0** leftover records
  with the probe MAC.

Every later write probe used `unblock-sta` on clients that were **already
unblocked**, so no real client's state changed, and the fake MACs that rode
along were removed the same way. The final state was re-verified after
every probe: 101 clients, 1 blocked, no residue.

### What was built

`bulk_client_action` in `src/tools/client_management.py` (a write tool):

- `action` ∈ `block` / `unblock` / `reconnect` / `forget`;
- deduplicates the MAC list and caps it at 100;
- checks the site inventory and splits known from unknown;
- issues the batch request (or the per-client fan-out for `reconnect`);
- reports **per client**: `status` ∈ `ok` / `not_found` / `failed` /
  `no_result`, with `blocked` where the console returned it, plus the
  `applied` / `failed` / `not_found` counts;
- is confirmation-gated and supports `dry_run`;
- a failure on one client during a reconnect fan-out does not stop the
  others;
- a MAC the controller omits from a batch response is reported `no_result`
  rather than assumed done.

**Live check.** A batch `unblock` over two already-unblocked clients: one
request, two `ok` results, and the site's state was **unchanged** (1
blocked before and after, 101 clients before and after). An unknown MAC
came back `not_found` with nothing sent and no record left behind.

---

## What remains

- **Network 11's client-connection key set is unverified.** The console
  here is Network 10.6.111 and reports
  `CLIENT_CONNECTED_WIRELESS_2` / `CLIENT_DISCONNECTED_WIRELESS_2`. The
  brief describes a Network 11 *alarm*; on a Network 11 controller the
  event may live on a different route or under a different key set. The
  tool matches on the key **prefix** and on `type`, so a new suffix is
  tolerated, but a different key entirely would not be.
- **The batch surface was verified on Network 10.6.111 only.** A Network 11
  controller may retire `cmd/stamgr` in favour of a native bulk endpoint;
  `bulk_client_action` would then need the newer route.
- **`kick-sta` was not exercised against a connected client.** Proving the
  per-client fan-out needs a client that is actually associated, and
  kicking one interrupts a live connection. The shape was confirmed by
  isolating the variable — `kick-sta` with no `mac` field and with an
  empty list both answer 500, while the singular `mac` form answers a
  clean `api.err.UnknownStation` — but the successful path is
  mock-tested only.
