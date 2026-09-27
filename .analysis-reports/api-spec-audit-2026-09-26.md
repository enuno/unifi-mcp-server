# UniFi API Field-Level Payload Audit — 2026-09-26

**Auditor:** noesis-orchestrator
**Spec baseline:** `scripts/scraped-api-spec-v10.6.106.json` (Network Integration API v10.6.106, 73 ops / 44 paths / 380 schemas)
**Method:** parsed the spec's per-operation request bodies (resolved `$ref` chains into `components.schemas`), extracted every `/v1/` / `integration/v1` path literal and f-string from `src/tools/`, normalized placeholders and the `/integration` prefix (the client's canonical cloud form of the spec's `/v1`), then compared paths, identifiers, and body field-by-field. Write tools that route through the local legacy/v2 endpoints (`/ea/sites/.../rest/*`, `/proxy/network/v2/...`) were excluded from body comparison — that split is a deliberate architecture decision (see #178/#179), and the local API has no published spec to audit against.

## Summary

- **13 unique Integration API paths called by code** (10 tool modules). All reads match the spec exactly.
- **3 write operations mismatch the spec** — paths, identifiers, and/or body shapes. All three are mock-tested only, so the drift is latent (tests assert the code's own assumptions, not the spec).
- **19 spec operations carry request bodies.** 16 are documented in `docs/UNIFI_API.md` but implemented via local legacy/v2 endpoints by design. 3 are the mismatches below.

## Findings

### F1 — HIGH — `adopt_device` calls a non-existent endpoint

- **Code:** `src/tools/devices.py:333` — `POST /integration/v1/sites/{site_id}/devices/{device_id}/adopt`, body `{"name"?: ...}`; validates a device UUID.
- **Spec:** no `/adopt` path exists. Adoption is `POST /v1/sites/{siteId}/devices` ("Adopt Devices"), body **required** `{"macAddress": string, "ignoreDeviceLimit": boolean}`. Identifies the device by **MAC**, not device ID.
- **Impact:** almost certainly 404s against the current Integration API (cloud or local proxy); the tool has never been verified on hardware.
- **Fix direction:** accept a MAC, `validate_mac`, POST to the collection with `ignoreDeviceLimit`, update docs/tests. Verify on hardware before release.

### F2 — HIGH — `port_action` path drift + unspecced body field

- **Code:** `src/tools/devices.py:404` — `POST .../devices/{device_id}/ports/{port_idx}/action`, body `{"action": ..., "params": {...}}`.
- **Spec:** `POST .../devices/{deviceId}/interfaces/ports/{portIdx}/actions` — plural `actions`, **and the `interfaces` path segment is missing in code**. Body: `{"action": string}` only; `params` is not a spec property.
- **Impact:** path almost certainly 404s; the extra `params` field would at best be ignored.
- **Fix direction:** insert `interfaces`, pluralize, drop or gate `params`, verify action value vocabulary on hardware.

### F3 — MEDIUM — client action endpoints use legacy singular path + MAC identifier

- **Code:** `src/tools/client_management.py:351` (`authorize_guest`) and `:463` (`limit_bandwidth`) — `POST .../clients/{client_mac}/action`, body `{"action": "authorize-guest"|"limit-bandwidth", "params": {...}}`.
- **Spec:** `POST .../clients/{clientId}/actions` — plural `actions`, `{clientId}` path parameter. Body: `{"action": string}` only; `params` unspecced.
- **Impact:** legacy-shaped. Some controllers tolerate the old form, but it is not in the current spec; the `params` sub-object (duration, limits) has no spec-defined carrier, so if the endpoint 404s there is no specced way to pass those values — needs hardware verification and possibly a different mechanism.
- **Fix direction:** pluralize path, re-verify identifier acceptance (MAC vs UUID), confirm how action parameters are carried on a live controller, update docs/tests.

## Verified clean

- All Integration API **read** paths used by code match spec exactly: countries, DPI applications/categories, device-tags, RADIUS profiles, VPN servers, site-to-site tunnels, WANs (`dpi_tools.py`, `reference_data.py`, `vpn.py`, `wans.py`).
- `POST /v1/sites/{siteId}/devices/{deviceId}/actions` (Execute Adopted Device Action) is not called via integration path by any tool — device restart/locate/LED go through local endpoints; spec body `{"action"}` noted for Phase 5a work.
- Spec GET operations expose no required query parameters beyond path segments — no query drift detected.

## Caveats

- Local legacy (`rest/*`) and v2 (`/proxy/network/v2/...`) endpoints have **no published spec**; their payloads cannot be field-audited against official sources. They were reviewed only for consistency with `docs/UNIFI_API.md`'s local-surface documentation.
- The three findings are latent by construction: unit tests mock `httpx`, so they validate the code's assumptions, not the spec. Hardware verification is required before any fix ships.
- The 16 spec body operations implemented via local endpoints are **not** gaps against the spec — they are a documented coverage strategy (`docs/UNIFI_API.md` covers both surfaces, and commits #178/#179 deliberately moved writes to v2/local).

## Follow-ups

1. Verify F1–F3 against live hardware; fix paths/bodies per spec; keep `params` only if hardware shows it is honored.
2. Decide whether `adopt_device` should take a MAC (spec) or keep device-ID UX and resolve MAC internally.
3. Re-run this audit after each spec snapshot refresh (`scripts/fetch-specs.sh` + this method; consider scripting it as `scripts/audit-spec-coverage.py` with F1–F3 as regression cases).
