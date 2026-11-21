# Live verification plan — UniFi Protect 7.4.96 (coverage items 28–30)

**Status:** prepared, not executed. No Protect 7.4.96 console is available to
this project, so nothing in this plan has been run. Every step below is
written to be executed as-is on the first session with such a controller.

**What this covers.** The three Protect 7.4.96 items the coverage map tracks
as implemented-but-unverified:

| Item | Surface | Tools | PR |
|---|---|---|---|
| 28 | External Alarm Manager arm profiles | `list`/`get`/`create`/`update`/`delete`/`arm`/`disarm` on `/v1/external/arm-profiles` | #316, #327 |
| 29 | Model-update subscription | `list_protect_model_updates` over `/v1/subscribe/updates` (WebSocket) | #319 |
| 30 | Speaker siren stop | `stop_protect_speaker_siren` on `/v1/speakers/{id}/stop-siren` | #316 |

**Evidence class of the code being verified:** *pinned spec*. Everything below
is checked against `scripts/protect-api-spec-v7.4.96.json`, and the client
and tools are mock-tested against it — including a real local HTTP 101
WebSocket upgrade in `tests/unit/api/test_protect_client.py`. What is missing
is the one thing a mock cannot supply: the console's own answers.

**Before you start.** Read `AGENTS.md` — these are live mutations of a
security system's arm state and of a speaker. Plan the session for a window
where the space is not in use.

**Recording.** For each step, record the **verbatim** response body and the
status code. A paraphrase is not evidence: the whole point of this plan is
that the recorded answers replace the pinned-spec inference. Controller
addresses, credentials, camera/speaker IDs and site identifiers are
**[REDACTED]** and must not be committed.

---

## Part 1 — Item 28: external arm profiles

### 1.0 Which family applies

The external family is only the right one when the NVR reports the feature
flag. Check it **first**, because the two families are different routes and
the wrong one will produce confusing 404s:

```
get_nvr(...).featureFlags.useExternalAlarmManager == true
```

If it is false, stop and record that: item 28's tools are correct for the
external family only, and the local `arm-profiles` family applies instead.

### 1.1 Read the collection

**The external-profile tools take `arm_profile_id`, not `id`** — that is the
parameter name in `src/tools/protect_external_arm.py`, and an example using
`id=` fails argument validation before a request is ever made. Every call
below uses `arm_profile_id`.

```
list_protect_external_arm_profiles(limit=100, offset=0)
```

Expected against the spec: the route returns a **bare array** of
`externalArmProfile` objects — `id`, `title`, `alarm_ids`, `schedule`,
`state`, `has_pin`, `activation_delay`, `deactivation_delay`, the
`created_*`/`updated_*` timestamps. **Not** a `data` envelope.

**Two different things, two different checks.** The *console* returns a bare
array; the *tool* always returns an envelope —
`{"data": [...], "count": N, "totalCount": M}` — because
`src/tools/protect_external_arm.py` wraps the response and pages it locally.
So:

- **Wire level** (the console's own answer): is the body an array rather than
  `{"data": [...]}`? **The tool result cannot answer this** — it is always a
  dict by construction. Assert it from a raw HTTP capture or client
  instrumentation, not from the MCP result. Checking the tool result for a
  bare array would fail a perfectly conforming console.
- **Tool level** (the MCP result): `count` and `totalCount` both equal the
  number of profiles, because the tool pages a bare array locally; and
  **no PIN-like key survives** — `pin`, `pin_code`, `pincode`, `pincodes`
  (case-insensitive) absent from every profile, including nested values. The
  tool strips them; confirm it did.

Record: the number of profiles, and one profile's keys verbatim.

### 1.2 Pagination behaves locally

With at least 3 profiles present, call:

```
list_protect_external_arm_profiles(limit=2, offset=0)
list_protect_external_arm_profiles(limit=2, offset=1)
list_protect_external_arm_profiles(limit=2, offset=99)
```

Expected: the first two return **different, overlapping** pages of 2, and
the third returns an **empty** `data` with `totalCount` still equal to the
collection size. This is the defect #327 fixed — the route takes no query
parameters, so the window is applied locally. If the console ever honours
`limit`/`offset` instead, the tool's local window and the console's would
compose and rows would be dropped; a page that does not look like a plain
slice is the signal for that.

### 1.3 Read one profile

```
get_protect_external_arm_profile(arm_profile_id=<one from 1.1>)
```

Expected: the profile object, unwrapped from a `data` envelope if the
console uses one. The spec's `{id}` parameter pattern is
`^[0-9A-Za-z-]+$` with `maxLength: 64` — note the ID's shape, and confirm it
matches that pattern.

### 1.4 Create, read back, update, read back

```
create_protect_external_arm_profile(title="VERIFY-<timestamp>", confirm=True)
```

Expected: `201` or `200` with the created profile, including a
server-assigned `id`.

Read it back with `get_protect_external_arm_profile`. **The read-back is
the point of this step**: confirm the `id` the console assigned is the one
returned, and that `has_pin` reflects the PIN you supplied rather than being
dropped.

Then:

```
update_protect_external_arm_profile(arm_profile_id=<id>, title="VERIFY-<timestamp>-updated", confirm=True)
```

Expected: the updated profile. Confirm the title changed and that the
fields you did **not** change survived — a partial update that wipes
`alarm_ids` or `schedule` is a defect worth recording.

### 1.5 Arm and disarm

```
arm_protect_external_arm_profile(arm_profile_id=<id>, confirm=True)
```

Expected: a profile whose `state` is `armed`. Confirm `state` really
changed, and record the exact state string — the spec does not enumerate the
state values, so the first live answer is the only evidence of what they
are.

```
disarm_protect_external_arm_profile(arm_profile_id=<id>, confirm=True)
```

Expected: `state` back to `disarmed`.

**Safety note.** Arming an external Alarm Manager profile changes the live
security posture of the space. Confirm the profile is bound to a test alarm
or a space that is not occupied before arming.

### 1.6 Delete — and the 204 that matters

```
delete_protect_external_arm_profile(arm_profile_id=<id>, confirm=True)
```

Expected: **`204 No Content`**. This is the step that most needs a live
console: an empty body on a 204 must be normalised to `{}` by `ProtectClient`
rather than raising a JSON decode error. The client was changed to do this
for exactly this reason (#319), and the tool should report success.

Then confirm the deletion took:

```
get_protect_external_arm_profile(arm_profile_id=<id>)   # expect a not-found error
list_protect_external_arm_profiles(...)     # expect the profile gone
```

Record the **exact** error shape for the not-found case — it is the
difference between a clean 404 and an unhandled exception.

### 1.7 ID handling

The tool validates the ID as a single path segment before interpolating it,
so these are refused locally, without a request:

```
get_protect_external_arm_profile("../../../etc/passwd")
get_protect_external_arm_profile("ext-1/../other")
```

Expected: a `ValidationError` naming `arm_profile_id`, and **no** HTTP
request. This confirms the guard from the client side: you should see the
refusal, not a 404 or a 400 from the console.

---

## Part 2 — Item 29: the model-update WebSocket

### 2.1 The URL and the upgrade

```
list_protect_model_updates(model_keys="camera", duration_seconds=5)
```

The tool derives the URL from the **configured console origin** — it never
accepts a caller-supplied absolute URL. Record the URL it actually opened;
it should be:

```
wss://<console>[:port]/proxy/protect/integration/v1/subscribe/updates?modelKeys=camera
```

(URL-encoded: `modelKeys=camera%2Cevent` for more than one key.)

The upgrade carries the API key in the **`X-API-KEY` header**, never in the
query string and never in a log. Confirm from the console's own access log
that the key did not appear in the URL.

Expected result: a bounded sample. Note the shape — the tool returns the
sampled frames under **`data`**, not `messages`; `messages` is the name of
the websocket library's frame list, not the tool's result key. Alongside it
the result carries `elapsedMs` and `stopReason`.

On a quiet controller the honest answer is **zero frames**; that is a pass,
not a failure. What must be true is that the upgrade succeeded (HTTP 101),
the subscription was accepted, and the sample ended for a *reported* reason
rather than an exception.

### 2.2 Produce a real update

With the subscription running, change something so the controller pushes a
frame:

```
list_protect_model_updates(model_keys="camera,event", duration_seconds=30)
```

In another session, arm or disarm a camera, or move a client so an event
fires.

Expected: at least one frame under `data`, each a JSON **object** with
`type` and `item`, where `item` carries `id` and `modelKey`. The `modelKey`
must be one of the keys you asked for — a frame for an unrequested key is a
finding.

Record the **verbatim** first frame. Its exact field names are the evidence
the pinned spec does not give.

### 2.3 The bounds

```
list_protect_model_updates(model_keys="camera", duration_seconds=0)     # refused
list_protect_model_updates(model_keys="camera", duration_seconds=31)    # refused
```

Expected: a `ValidationError` for both, and no connection attempt.

And confirm the sampling bounds hold under load: run with `duration_seconds=30`
while generating updates, and check the result reports `stopReason` and a
message count consistent with the cap you passed.

### 2.4 Stop reasons

Four distinct endings must be reachable, and the tool must report which
happened rather than throwing:

| Situation | Expected `stopReason` |
|---|---|
| the window elapsed with nothing arriving | the elapsed-window reason |
| the message cap was reached | the message-limit reason |
| the server closed the connection cleanly | `peer_closed` |
| the server closed it abnormally | an `APIError`, **not** a silent success |

The abnormal case is the one that cannot be produced by mocking the happy
path. If you can interrupt the controller's network during a sample, do
so: the tool must raise rather than report a clean finish.

### 2.5 Cloud Connector must fail loudly

Configure the same controller as a Cloud Connector and repeat step 2.1.

Expected: an explicit failure saying the Cloud Connector cannot proxy a
WebSocket upgrade. **A fallback to a plain HTTP request would be a defect** —
the spec defines this route as a WebSocket, so an HTTP answer would be a
different surface entirely.

---

## Part 3 — Item 30: stop the speaker siren

### 3.1 Start a siren, then stop it

```
test_protect_speaker_sound(speaker_id=<id>, ...)   # or whatever starts a test sound
stop_protect_speaker_siren(speaker_id=<id>, confirm=True)
```

Expected: **`204 No Content`**, normalised to `{}` and reported as success.
This is the same empty-body handling as item 28's delete, on a different
route.

### 3.2 Confirm it stopped

Call `stop_protect_speaker_siren` again on the same speaker. Expected:
either `204` again (idempotent) or a specific error — record which. An
unhandled exception here means the empty-body handling is route-specific
rather than general.

### 3.3 The write gate

```
stop_protect_speaker_siren(speaker_id=<id>)          # no confirm
```

Expected: refused locally with a message naming `confirm`, and **no**
request sent. Same for `dry_run=True`, which must make no request.

---

## Part 4 — Record and close

For every step, record: the tool call, the status code, and the **verbatim**
response body (redacted). Then answer, per item:

- **28** — does the collection return a bare array? do the pages slice
  correctly? does delete answer 204 and normalise to `{}`? does arm change
  `state`?
- **29** — does the upgrade reach HTTP 101 against real hardware? what does a
  real frame look like? are all four stop reasons reachable?
- **30** — does the stop answer 204? is it idempotent?

Anything that differs from the pinned spec is a finding, not a surprise: the
spec is a published document and the console is the authority. Where they
disagree, **record the console's answer and update the spec file in the
repository** — the pinned spec is a vendored snapshot, and a live console
that has moved is a reason to re-pin it.

Where the recorded answer is a **204 with an empty body**, confirm the tool
reported success rather than raising. That normalisation is the specific
thing this plan exists to prove.
