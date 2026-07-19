# Phase 3 Protect API Readiness Report

**Repository:** UniFi MCP Server  
**Assessment date:** 2026-07-19  
**Scope:** current Phase 3 Protect readiness based on `DEVELOPMENT_PLAN.md`, `ROADMAP.md`, `GAP_REPORT.md`, `TODO.md`, and the Protect scaffold/tests in `src/` and `tests/`.

## Executive verdict

Phase 3 is **not ready to ship**. The repo contains a small but useful Protect scaffold, but it is still missing the runtime wiring, package exports, config support, and most of the endpoint surface that Phase 3 promises.

The best summary is:

- **Implemented:** basic Protect client wrapper, two Pydantic models, two read-only tool modules, one resource class, and targeted unit tests for the client.
- **Not yet integrated:** Protect code is not exported through the package init files, not registered in `main.py`, and not available through the current tool/resource bootstrapping path.
- **Not yet complete:** the broader Phase 3 scope in the plan/documentation still includes devices, views, events, snapshots/streams/talkback/PTZ, and mocked integration tests.
- **Blocked at runtime:** the Protect code expects `Settings.get_protect_integration_path(...)`, but that method is not implemented in `src/config/config.py`.

## What is already implemented

### API client
- `src/api/protect_client.py` exists and provides:
  - async context manager support
  - `get/post/put/patch/delete`
  - response parsing and basic error wrapping
  - a simple `authenticate()` probe
  - local/cloud path handling via `settings.get_protect_integration_path(...)`

### Models
- `src/models/protect_camera.py`
- `src/models/protect_nvr.py`

These models cover only a narrow subset of the real Protect object shape:
- camera id/name/model/type/state, recording, speaker/mic/PTZ flags, MAC, firmware
- NVR id/name/model/state/host/firmware version/uptime

### Tools
- `src/tools/protect_cameras.py`
  - list cameras
  - get camera by id
  - limit/offset validation
  - response normalization into `ProtectCamera`
- `src/tools/protect_nvr.py`
  - list NVRs
  - get NVR by id
  - response normalization into `ProtectNVR`

### Resource
- `src/resources/protect.py`
  - list/get NVRs
  - list/get cameras
  - returns typed model objects

### Tests
- `tests/unit/api/test_protect_client.py` passes in isolation: **6 passed**.
- Unit tests exist for cameras, NVRs, and the Protect resource.

## What is missing or incomplete

### 1) Package and bootstrap wiring is incomplete
The Protect scaffold is not actually reachable through the package surface used by the rest of the repo.

Observed gaps:
- `src/api/__init__.py` exports only `UniFiClient` and `RateLimiter`; it does **not** export `ProtectClient`.
- `src/models/__init__.py` does **not** export `ProtectCamera` or `ProtectNVR`.
- `src/resources/__init__.py` does **not** export `ProtectResource`.
- `src/tools/__init__.py` does **not** import or export any Protect tool module.
- `src/main.py` does **not** register any Protect tool modules or Protect MCP resources.

This is not just a cleanliness issue: the Protect tool/resource modules currently fail to import because they do `from ..api import ProtectClient`, and the package export is missing.

### 2) Settings/runtime support is missing
The Protect code calls `settings.get_protect_integration_path(...)`, but `src/config/config.py` does not define that method.

That means the current Protect client/tool/resource code is only usable in tests that monkeypatch the method. It is not yet a real runtime capability.

### 3) The Phase 3 endpoint surface is far larger than the scaffold
The plan and TODOs describe much more than camera/NVR list/get.

Still missing from the repo:
- `src/tools/protect_devices.py`
- `src/tools/protect_views.py`
- `src/tools/protect_events.py`
- any Protect write/update operations
- camera snapshot/stream/talkback/PTZ operations
- device asset and update-message operations
- live views / viewer settings
- Protect event and webhook handling
- additional Protect models beyond camera and NVR

### 4) Integration tests are still absent
The roadmap calls for mocked integration tests with Protect NVR responses, but the current test set is still unit-level.

There are unit tests for:
- client pathing and authenticate behavior
- camera tool happy path / input validation
- NVR tool happy path / input validation
- resource happy path

There is not yet a real integration-style suite that exercises the full Protect surface end to end through the repo’s normal bootstrapping path.

### 5) User-facing profile story is not implemented
The repo’s README advertises a `protect` tool profile, but `src/main.py` currently defines profiles for:
- `network`
- `devices`
- `security`
- `system`
- `minimal`

There is no `protect` profile entry, so the README claim is ahead of the actual tool-registration code.

## Verification findings

I ran targeted tests in the repo:

### Passed
- `pytest -q tests/unit/api/test_protect_client.py`
  - result: **6 passed**

### Failed during collection
- `pytest -q tests/unit/api/test_protect_client.py tests/unit/tools/test_protect_cameras.py tests/unit/tools/test_protect_nvr.py tests/unit/resources/test_protect_resource.py`
  - result: import collection failed for the Protect tool/resource tests
  - root cause: `from ..api import ProtectClient` cannot resolve because `src/api/__init__.py` does not export `ProtectClient`

That failure is a strong signal that the scaffold is not yet wired into the package correctly.

## Readiness assessment by work package

### A. Foundation / runtime enablement: **Not ready**
Dependencies still missing:
- config helper for Protect integration paths
- package exports
- registration in `main.py`
- `protect` profile support

### B. Read-only camera/NVR MVP: **Partially implemented, not operable end-to-end**
Code exists, but it is not reachable through the normal repo entrypoints yet.

### C. Broader Phase 3 scope: **Not started**
Still absent:
- views
- events
- device tooling
- most camera operations beyond list/get
- mocked integration coverage

### D. Documentation alignment: **Mixed**
- The high-level docs already describe Phase 3 Protect as the active target.
- The README also advertises a `protect` profile.
- But the implementation does not yet support that story operationally.

## Recommended next work packages

### Work package 1: Make the scaffold importable and bootable
Priority: highest

Deliverables:
- export `ProtectClient` from `src/api/__init__.py`
- export `ProtectCamera` / `ProtectNVR` from `src/models/__init__.py`
- export `ProtectResource` from `src/resources/__init__.py`
- import/register Protect tools in `src/tools/__init__.py`
- register Protect tools/resources in `src/main.py`
- add or validate a `protect` profile entry so the README claim matches behavior

### Work package 2: Add config support for Protect integration paths
Priority: highest

Deliverables:
- implement `Settings.get_protect_integration_path(...)`
- ensure local vs cloud pathing is correct
- validate the path builder against existing network integration conventions

### Work package 3: Expand the Protect domain surface
Priority: high

Deliverables:
- `protect_devices.py`
- `protect_views.py`
- `protect_events.py`
- additional camera operations: snapshot, stream, talkback, PTZ
- device asset/update-message support
- richer models for events, views, devices, and camera substructures

### Work package 4: Add mocked integration tests
Priority: high

Deliverables:
- import/registration tests for the boot path
- mocked Protect responses for camera/NVR list/get
- tests for new path builder behavior
- response-shape tests for the expanded models
- at least one test that proves the `protect` profile is selected correctly

### Work package 5: Doc sync after code wiring
Priority: medium

Deliverables:
- update README / API docs / `docs/UNIFI_API.md` so the implemented Protect surface is clearly separated from the planned surface
- remove any wording that implies Protect is already fully integrated if only the scaffold exists

## Blockers

1. **Missing package exports** prevent the Protect tool/resource modules from importing normally.
2. **Missing `get_protect_integration_path()`** means the runtime Protect client cannot work against the real `Settings` object.
3. **No Protect registration in `main.py`** means the MCP server does not expose Protect capability even though the scaffolding files exist.
4. **The implemented scope is too small** relative to the plan: only camera/NVR list/get exists.

## Bottom line

Phase 3 has the **beginning of an implementation**, not a shippable Protect feature set. The repository is best described as:

- scaffolded but not wired,
- unit-tested in isolation for the client,
- incomplete for the documented Phase 3 scope,
- and blocked on runtime integration before any real Protect readiness claim is credible.
