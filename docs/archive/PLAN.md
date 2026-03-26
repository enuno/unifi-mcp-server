# P1 API Development Plan

**Date:** 2026-02-18
**Scope:** Fix bugs, complete missing client methods, and ship P1 features (QoS, Backup, Site Manager, Topology, RADIUS)

---

## Phase 0: Discovery (COMPLETED — do not re-run)

All discovery was completed in the session that produced this plan. Key findings are embedded in each phase below.

### What Exists (All Already Implemented)

| Feature | Tool File | Model File | Tests | Coverage | Registered |
|---------|-----------|------------|-------|----------|------------|
| Advanced QoS & Traffic Routes | `src/tools/qos.py` (15 tools) | `src/models/qos_profile.py` | `tests/unit/tools/test_qos_tools.py` | 82.43% | ✅ main.py |
| Backup & Restore | `src/tools/backups.py` (8 tools) | `src/models/backup.py` | `tests/unit/tools/test_backups_tools.py` | 86.32% | ✅ main.py |
| Site Manager Foundation | `src/tools/site_manager.py` (13 tools) | `src/models/site_manager.py` | `tests/unit/tools/test_site_manager_tools.py` | 92.33% | ✅ main.py |
| Network Topology | `src/tools/topology.py` (3+ tools) | `src/models/topology.py` | `tests/unit/tools/test_topology_tools.py` | 81.18% | ✅ main.py |
| RADIUS Full CRUD | `src/tools/radius.py` (13 tools) | `src/models/radius.py` | `tests/unit/tools/test_radius_tools.py` | 93.46% | ✅ main.py |

**Current test baseline:** 1128 tests pass, 6 warnings, 0 failures.

### Known Bugs to Fix

1. **`src/tools/qos.py` — wrong `audit_action` keyword argument** (CRITICAL - runtime failure)
   - The `audit_action` function signature requires `action_type=` as the 2nd parameter.
   - Many calls in `qos.py` incorrectly use `action=` instead of `action_type=`.
   - This would cause `TypeError` at runtime when audit logging is enabled.
   - **Affected lines:** Grep `qos.py` for `action=` (not `action_type=`) in `audit_action` calls.
   - Pattern to copy from correct calls: `src/tools/qos.py:353` (delete_qos_profile uses correct `action_type=`)
   - **Source of truth for signature:** `src/utils/audit.py:176-183`

2. **`src/tools/site_manager.py:589` — double `@require_site_manager` decorator** (MINOR - redundant but harmless)
   - `get_sdwan_config_status` has `@require_site_manager` applied twice.
   - Remove one.

3. **`tests/unit/tools/test_topology_tools.py` — unawaited coroutine warnings** (TEST QUALITY)
   - 6 `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` warnings.
   - Root cause: some test mocks are not properly set up as async. The mock setup needs `AsyncMock` not `MagicMock` for async functions.
   - **Affected tests:** `TestGetNetworkTopology::test_get_network_topology_empty`, `TestExportTopology::test_export_topology_json/graphml/dot`, `TestGetTopologyStatistics::test_get_topology_statistics`, `test_get_topology_statistics_empty`.

### Missing API Client Methods (Backup scheduling/status)

The following methods are called in `src/tools/backups.py` but do NOT exist in `src/api/client.py` (currently handled via `AttributeError` fallback):

- `client.get_restore_status(operation_id)` (line ~829 in backups.py)
- `client.configure_backup_schedule(...)` (line ~1029 in backups.py)
- `client.get_backup_schedule(site_id)` (line ~1133 in backups.py)

**Source to copy from for client method pattern:** `src/api/client.py:545-676` (existing backup methods like `trigger_backup`, `list_backups`, `download_backup`)

---

## Phase 1: Fix audit_action Calls in qos.py

**Self-contained. No dependencies.**

### What to Do

1. Read `src/utils/audit.py:176-183` to confirm the function signature.
2. Read `src/tools/qos.py` fully.
3. Find all calls to `audit_action(` that use `action=` keyword instead of `action_type=`.
4. Change `action=` → `action_type=` in each affected call.
5. Do NOT change the `action_type=` calls (those in delete_qos_profile and delete_traffic_route are already correct).

### Documentation Reference

- Correct pattern (copy from): `src/tools/qos.py:353` — `action_type="delete_qos_profile"`
- Wrong pattern (search for): `action=` in audit_action calls within `src/tools/qos.py`
- Signature source: `src/utils/audit.py:176`

### Verification Checklist

- [ ] `grep -n 'action=' src/tools/qos.py` shows no remaining `action=` kwargs in audit_action calls
- [ ] All audit_action calls in qos.py use `action_type=`
- [ ] `.venv/bin/pytest tests/unit/tools/test_qos_tools.py -q` still passes (46 tests)

### Anti-Pattern Guards

- Do NOT change any `action_type=` that is already correct.
- Do NOT modify the `audit_action` function signature in `src/utils/audit.py`.
- Do NOT add or remove audit_action calls; only fix the keyword argument name.

---

## Phase 2: Fix double decorator in site_manager.py

**Self-contained. No dependencies.**

### What to Do

1. Read `src/tools/site_manager.py:585-610` to see the double decorator.
2. Remove the second `@require_site_manager` from `get_sdwan_config_status`.
3. Keep one `@require_site_manager` (the first occurrence at line 588 or wherever it appears).

### Documentation Reference

- Pattern to copy: Any other function in `src/tools/site_manager.py` that has a single `@require_site_manager` decorator (e.g., `get_isp_metrics` at line 490)

### Verification Checklist

- [ ] `grep -c '@require_site_manager' src/tools/site_manager.py | xargs` — count should equal number of functions that use it (one decorator each)
- [ ] `get_sdwan_config_status` has exactly one `@require_site_manager` decorator
- [ ] `.venv/bin/pytest tests/unit/tools/test_site_manager_tools.py -q` still passes (42 tests)

### Anti-Pattern Guards

- Do NOT remove the decorator entirely — `get_sdwan_config_status` does require site manager authentication.

---

## Phase 3: Fix topology test AsyncMock warnings

**Self-contained. No dependencies. Required for clean CI.**

### What to Do

1. Read `tests/unit/tools/test_topology_tools.py` fully.
2. Find the 6 tests that emit `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`.
3. For each affected test, identify the mock setup — it is likely setting up an `AsyncMock` that then isn't being used correctly, or a `MagicMock` being used for an async function.
4. Fix each test mock so that coroutines are properly awaited. The typical fix is:
   - Replace `MagicMock(return_value=...)` with `AsyncMock(return_value=...)` for mocked async functions.
   - Or ensure `patch` targets use `new_callable=AsyncMock`.
5. Pattern to copy from: Any properly-set-up test in `tests/unit/tools/test_qos_tools.py` that uses `AsyncMock` (e.g., line ~30-60 in that file).

### Documentation Reference

- Correct AsyncMock pattern: `tests/unit/tools/test_qos_tools.py` — look for `AsyncMock` usage with `patch`
- Python docs: `unittest.mock.AsyncMock` is required for async coroutines in Python 3.8+

### Verification Checklist

- [ ] `.venv/bin/pytest tests/unit/tools/test_topology_tools.py -q -W error::RuntimeWarning` passes with no errors (0 warnings)
- [ ] All 12 topology tests still pass

### Anti-Pattern Guards

- Do NOT change the `src/tools/topology.py` implementation — only fix the tests.
- Do NOT remove test cases to eliminate warnings; fix the mocks.

---

## Phase 4: Add Missing Backup Client Methods

**Self-contained. Depends on: Understanding of existing backup client methods (Phase 0 complete).**

### What to Do

1. Read `src/api/client.py:545-750` — study the existing backup methods (`trigger_backup`, `list_backups`, `download_backup`, `delete_backup`, `restore_backup`, `get_backup_status`).
2. Read `src/tools/backups.py` to understand exactly how these methods are called:
   - `client.get_restore_status(operation_id)` — called at backups.py line ~829
   - `client.configure_backup_schedule(site_id, backup_type, frequency, time_of_day, enabled, retention_days, max_backups, day_of_week, day_of_month, cloud_backup_enabled)` — called at backups.py line ~1029
   - `client.get_backup_schedule(site_id)` — called at backups.py line ~1133
3. Add stub implementations for these 3 methods to `src/api/client.py`, following the exact same pattern as the existing backup methods.
4. The implementations should call the appropriate UniFi API endpoints:
   - `get_restore_status`: GET `/api/cmd/backup/status/{operation_id}` (or similar — note: this endpoint may not exist in UniFi API, in which case return `{"status": "completed"}`)
   - `configure_backup_schedule`: PUT `/api/s/{site}/rest/backup/schedule`
   - `get_backup_schedule`: GET `/api/s/{site}/rest/backup/schedule`
5. **IMPORTANT**: If the UniFi API doesn't actually have these endpoints, implement stub methods that return sensible defaults (rather than relying on the AttributeError fallback). The `backups.py` already handles AttributeError gracefully, but having explicit methods is cleaner.

### Documentation Reference

- Pattern to copy from: `src/api/client.py:545-583` — the `trigger_backup` method implementation
- API endpoint reference: `docs/UNIFI_API.md` backup section (check if scheduling endpoints are documented)

### Verification Checklist

- [ ] `grep -n 'get_restore_status\|configure_backup_schedule\|get_backup_schedule' src/api/client.py` finds all 3 methods
- [ ] Each method follows the same pattern as existing backup methods
- [ ] `.venv/bin/pytest tests/unit/tools/test_backups_tools.py -q` still passes (37 tests)
- [ ] No new test failures introduced

### Anti-Pattern Guards

- Do NOT use AttributeError fallback as a substitute — implement real methods.
- Do NOT invent API endpoints that don't exist in UniFi docs; use documented endpoints or return sensible stubs.
- Copy the exact pattern from existing backup client methods, don't reinvent.

---

## Phase 5: Final Quality Gates and CI

**Depends on: Phases 1-4 complete.**

### What to Do

1. Run the full test suite and confirm 0 failures, 0 warnings:

   ```bash
   .venv/bin/pytest tests/unit/ -q -W error::RuntimeWarning 2>&1 | tail -5
   ```

2. Run pre-commit on all changed files:

   ```bash
   pre-commit run --all-files
   ```

3. Check coverage meets 80%+ on all P1 modules:

   ```bash
   .venv/bin/pytest tests/unit/tools/test_qos_tools.py tests/unit/tools/test_backups_tools.py \
     tests/unit/tools/test_site_manager_tools.py tests/unit/tools/test_topology_tools.py \
     tests/unit/tools/test_radius_tools.py \
     --cov=src/tools/qos --cov=src/tools/backups --cov=src/tools/site_manager \
     --cov=src/tools/topology --cov=src/tools/radius --cov-report=term-missing -q
   ```

   Expected minimums: qos ≥82%, backups ≥86%, site_manager ≥92%, topology ≥81%, radius ≥93%.
4. Fix any pre-commit failures before continuing.
5. Read and follow `finishing-a-development-branch` skill to create the PR.

### Verification Checklist

- [ ] 0 test failures
- [ ] 0 `RuntimeWarning` coroutine warnings
- [ ] Pre-commit passes on all files
- [ ] All P1 modules maintain ≥80% coverage
- [ ] PR created targeting `main` branch

### Anti-Pattern Guards

- Do NOT skip `--no-verify` on commits.
- Do NOT open a PR if tests are failing.
- Do NOT reduce test coverage to fix a coverage gap — add tests instead.

---

## Phase 6: Update Documentation (After PR Merged)

**Depends on: Phase 5 PR merged.**

Follow the `updating-noridocs` skill to update:

1. `CHANGELOG.md` — add v0.2.3 entry documenting P1 features shipped
2. `TODO.md` — mark P1 items as complete
3. `DEVELOPMENT_PLAN.md` — update status of Advanced QoS, Backup/Restore, Site Manager Foundation, Topology, RADIUS CRUD from "Not implemented" / "Roadmap" to "✅ FULLY IMPLEMENTED"

---

## Allowed APIs (Confirmed in Discovery)

| API | Source | Notes |
|-----|--------|-------|
| `audit_action(settings, action_type, resource_type, resource_id, site_id, details)` | `src/utils/audit.py:176` | `action_type` is 2nd positional, NOT `action` |
| `UniFiClient(settings)` as async context manager | `src/api/client.py` | Pattern: `async with UniFiClient(settings) as client:` |
| `client.authenticate()` before API calls | `src/api/client.py` | Check `if not client.is_authenticated` first |
| `settings.get_api_path(f"s/{site_id}/rest/...")` | `src/config.py` | For endpoint path construction |
| `validate_confirmation(confirm, "description", dry_run)` | `src/utils/` | Required for mutating operations |
| `AsyncMock` for async function mocks in tests | Python stdlib | Use instead of `MagicMock` for coroutines |
| `SiteManagerClient(settings)` | `src/api/site_manager_client.py` | For Site Manager API calls |

## Anti-Pattern Guards (Global)

- **DO NOT** use `action=` as keyword in `audit_action` calls — use `action_type=`
- **DO NOT** add `try/except AttributeError` fallbacks in tools — implement proper client methods instead
- **DO NOT** mock `audit_action` incorrectly in tests — it returns `None` (not awaited return value)
- **DO NOT** invent new API endpoints not in UNIFI_API.md
- **DO NOT** modify `audit_action` function signature to accept `action=` as alias

---

*Plan generated: 2026-02-18. Discovery session: unifi-mcp-server main branch, commit `1e99a6f`.*
