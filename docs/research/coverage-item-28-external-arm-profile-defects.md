# Coverage item 28 — Protect external arm profile defects

**Status:** implemented, pinned-spec verified. Not live-verified.
**Scope:** the external Alarm Manager arm-profile family in
`src/tools/protect_external_arm.py`.

Two defects were left open by the Codex review of #316; #319 fixed the third.
Both are defects of *expectation*, not of routing: the routes are correct, but
the tool assumed the console behaves in ways the specification says it does not.

## Evidence grading

| Grade | Meaning |
|---|---|
| **Official** | Ubiquiti published specification, here the pinned `scripts/protect-api-spec-v7.4.96.json`. |
| **Derived** | Read from the pinned specification's schemas and parameter definitions. |
| **Observed** | Request executed against live hardware. |

Everything in this record is **Official** or **Derived** from the pinned
specification. Nothing here is Observed: no Protect 7.4.96 controller is
available to this project, so no live request was made and no live response was
recorded. The controller address, credentials and site identifiers are
**[REDACTED]** and are not committed.

## Defect 1 — pagination was forwarded where the route accepts none

### What the specification says

`GET /v1/external/arm-profiles` in the pinned specification:

| Property | Value |
|---|---|
| Query parameters | **none** |
| 200 response schema | `externalArmProfiles`, `type: array` of `externalArmProfile` |
| 200 envelope | none — the body is a bare array |

A repository-wide scan of the pinned specification for *any* route declaring a
`limit` or `offset` query parameter returns **zero** matches across all
paths and methods. The Protect Integration API has no pagination parameters at
all.

### What the tool did

```python
response = await client.get(
    settings.get_protect_integration_path("external/arm-profiles"),
    params={"limit": final_limit, "offset": final_offset},
)
```

The parameters were sent and then ignored by the console. The tool then
returned the entire collection while reporting the requested `limit` and
`offset` in its result envelope, so a caller asking for 10 of 47 profiles
received all 47 and was told the window was applied.

The reported `count` and `totalCount` had the same defect: they were read from
`response["count"]` / `response["totalCount"]`, keys that exist only in the
`data`-envelope shape. Against the bare array the specification defines, both
fell back to the length of the whole collection.

### Why it was never noticed

The unit test mocked the controller's response as `{"count": 1, "totalCount": 1,
"data": [PROFILE]}` — the envelope shape — so the test asserted a call the
console never makes and a count the console never reports. The mock encoded
the assumption instead of contradicting it.

### The fix

The route is requested once, without query parameters, and the window is
applied to the returned collection locally:

```python
response = await client.get(
    settings.get_protect_integration_path("external/arm-profiles"),
)
data = _extract_collection(response)
profiles = [_serialize_profile(item) for item in data]
total_count = len(profiles)
page = profiles[final_offset : final_offset + final_limit]
```

`totalCount` now reports the size of the whole collection and `count` the size
of the returned page, which is what a caller needs to page through a collection
whose size the console does not report.

Forwarding the parameters *as well as* slicing locally would be wrong: on a
console that honours them the two windows would compose and rows would be
silently dropped. The parameters are therefore not sent.

## Defect 2 — IDs were interpolated into a path unvalidated

### What the specification says

Every route that carries a profile ID constrains the path parameter the same
way:

| Route | Parameter | Schema |
|---|---|---|
| `GET /v1/external/arm-profiles/{id}` | `id` | `minLength: 1`, `maxLength: 64`, `pattern: ^[0-9A-Za-z-]+$` |
| `PATCH /v1/external/arm-profiles/{id}` | `id` | as above |
| `DELETE /v1/external/arm-profiles/{id}` | `id` | as above |
| `POST /v1/external/arm-profiles/{id}/actions/arm` | `id` | as above |
| `POST /v1/external/arm-profiles/{id}/actions/disarm` | `id` | as above |

These are the only path parameters in the entire pinned specification that carry
a `pattern` constraint.

### What the tool did

```python
def _validate_profile_id(arm_profile_id: str) -> str:
    arm_profile_id = arm_profile_id.strip()
    if not arm_profile_id:
        raise ValidationError("arm_profile_id is required")
    return arm_profile_id
```

Only emptiness was checked. The value was then interpolated into a path in
five places — get, update, delete, arm and disarm — so an ID containing `/`,
`..` or a query character could retarget the request at a different route.

### The fix

The repository already has the right validator for this: `validate_path_segment`
in `src/utils/validators.py`, which permits only RFC 3986 unreserved characters
and `:`, refuses a value made only of dots, and so keeps the value a single
plain segment. It is what the sibling Protect tool
`src/tools/protect_events.py` already uses for its own `webhook_id` path
parameter.

`_validate_profile_id` now delegates to it, and because all five call sites
route through that one helper, the guard applies to every path interpolation.

The specification's `pattern` is stricter than the repository validator's
character set. The repository convention was kept rather than the stricter
pattern, for two reasons: the repository validator is what the sibling Protect
tool uses, and the pattern is the console's own input constraint rather than a
requirement of the route shape. A value the console would reject reaches the
console and is rejected there.

## Verification

### Regression tests

Twelve new tool-level tests and two client-level tests, in the style of #319's:

- `limit` slices the returned collection locally.
- `offset` slices the returned collection locally.
- No `params` keyword reaches the client for this route.
- An offset past the end returns an empty page with the true `totalCount`.
- Six traversal-shaped IDs (`../../external/arm-profiles`, `ext-1/../other`,
  `ext 1`, `..`, `ext-1?limit=100`, `ext-1#fragment`) are rejected for the get
  tool, and the write tools reject one before any request is issued.
- A valid ID still reaches the expected path.
- Client level: `get` sends no query string when the caller supplies none, and
  still forwards a caller's explicit parameters, so the client stays generic.

### Proof the tests detect the defects

The tool-level tests were run against the previous implementation of
`src/tools/protect_external_arm.py`, with the new tests unchanged. **All twelve
failed** — four pagination tests and eight ID-validation tests — and all pass
against the fix. A regression test that cannot fail against the code it
regresses is not a regression test.

### Coverage

`src/tools/protect_external_arm.py` reaches 100% statement and branch
coverage.

## Not verified

- **No live Protect 7.4.96 controller was available**, so no request in this
  change has been executed against hardware. The behaviour of the console when
  it receives the `limit`/`offset` query parameters the specification does not
  declare is **not** observed. The specification says they are not defined;
  whether the console ignores them or rejects them was not measured. The fix
  does not depend on the answer, since the parameters are no longer sent.
- The **success** response body of each external arm-profile route is
  unchanged by this work and remains unverified against hardware.
- The console's own `pattern` enforcement on `{id}` was not exercised.

## Sibling family, deliberately not changed here

`src/tools/protect_alarm.py` has the same two shapes: it forwards
`limit`/`offset` to `GET /v1/arm-profiles`, whose pinned specification also
declares no query parameters and a bare-array response, and its
`_validate_arm_profile_id` only checks emptiness. Coverage item 28 is scoped to
the external family, so that file is left alone here and flagged separately
rather than silently changed inside an unrelated item's PR.

## Sources

1. UniFi Protect integration API, pinned snapshot `scripts/protect-api-spec-v7.4.96.json`
   in this repository — paths `/v1/external/arm-profiles` and
   `/v1/external/arm-profiles/{id}`, and the `externalArmProfiles`,
   `externalArmProfile` schemas.
