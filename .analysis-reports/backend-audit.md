# Protect API Scaffold Audit

Scope: `src/api/protect_client.py`, `src/models/protect_camera.py`, `src/models/protect_nvr.py`, `src/resources/protect.py`, `src/tools/protect_cameras.py`, `src/tools/protect_nvr.py`, and related tests, compared against `src/api/client.py`, `src/resources/*.py`, and `src/tools/{networks,network_config}.py`.

## Executive summary
The Protect scaffold is **not yet production-runnable**. The main problems are missing package/config wiring, import/export gaps, and test coverage that currently masks runtime failures.

## Findings

### 1) High: Protect modules depend on missing package API surface
- `src/resources/protect.py` imports `ProtectClient` via `from ..api import ProtectClient`, but `src/api/__init__.py` only exports `UniFiClient` and `RateLimiter`.
- `src/tools/protect_cameras.py` imports `ProtectCamera` via `from ..models import ProtectCamera`, but `src/models/__init__.py` does not export `ProtectCamera` or `ProtectNVR`.

**Impact:** importing the Protect resource/tools fails at runtime, which is already visible in targeted test collection (`ImportError: cannot import name 'ProtectClient' from 'src.api'`).

**Fix:** export the new Protect client/model symbols from the package `__init__.py` files or change the imports to direct module imports everywhere.

---

### 2) High: ProtectClient depends on a Settings helper that does not exist
- `src/api/protect_client.py` and all Protect tools/resources call `settings.get_protect_integration_path(...)`.
- That method is **not implemented** in `src/config/config.py` (no match in the config package).

**Impact:** once the import/export issue is fixed, every Protect call will raise `AttributeError` unless tests continue to monkeypatch a fake method.

**Testability concern:** the current tests patch `get_protect_integration_path` onto `MagicMock` settings, so they pass without proving the real config API exists.

**Fix:** add the helper to `Settings` and add tests that instantiate real `Settings` (or a thin test double) without monkeypatching this method.

---

### 3) High: Protect scaffold is not wired into the MCP server
- `src/main.py` imports and registers Network/Site/Client/Device modules, but there is **no import or registration path for Protect**.
- `ProtectResource` is defined, but nothing instantiates or exposes it in `main.py`.
- The Protect tools are not included in the tool-module lists or profile maps.

**Impact:** even if the imports/config were fixed, the Protect API would still be unreachable from the MCP server.

**Fix:** register Protect resources/tools in `main.py` and include them in the relevant export/registration paths and profiles.

---

### 4) Medium: ProtectClient is less consistent than the existing core client
Compared with `src/api/client.py`, `ProtectClient` is much thinner:
- no retry/backoff logic for transient network failures
- no differentiated handling for 401/403/404/429
- no response normalization beyond raw `response.json()`
- no logging/audit hook parity with the core client

**Impact:** behavior is less predictable and harder to test against the rest of the codebase’s patterns.

**Fix:** either align ProtectClient with the core client’s semantics or document that Protect intentionally uses a simpler transport/error model.

---

### 5) Medium: Response-shape handling is brittle and under-tested
- `list_protect_cameras()` / `list_protect_nvrs()` assume dict responses with a `data` array; list-shaped JSON would be treated as empty.
- `get_protect_camera()` / `get_protect_nvr()` assume a single object shape; there is no explicit empty-response/404 path.
- The tests only cover happy paths, plus auth/init, and do not exercise bad responses, missing fields, or envelope variants.

**Impact:** small API shape changes could silently break the feature.

**Fix:** add explicit response-shape tests, error-path tests, and one integration-style seam that proves the raw API contract for Protect.

## Verification performed
- Ran:
  - `pytest -q tests/unit/api/test_protect_client.py` → **passed** (`6 passed`)
  - `pytest -q tests/unit/api/test_protect_client.py tests/unit/resources/test_protect_resource.py tests/unit/tools/test_protect_cameras.py tests/unit/tools/test_protect_nvr.py` → **failed during collection** with import errors from `src.api`.

## Bottom line
The scaffold is a reasonable start, but it is currently blocked by missing wiring and missing config API. Fix the package exports and `Settings` helper first; then add registration in `main.py` and broaden the test matrix beyond happy-path mocks.
