# Noridoc: tests/unit/tools

Path: @/tests/unit/tools

### Overview

- Contains unit tests for every tool module in `@/src/tools/`, organized one test file per tool module.
- Tests use `unittest.mock.AsyncMock` and `patch("src.tools.<module>.UniFiClient")` to intercept HTTP calls, keeping tests fully offline.
- Each test file covers the full CRUD surface of its corresponding tool module, including success paths, error paths, dry-run behavior, and confirmation guards.

### How it fits into the larger codebase

- Test files import directly from `src.tools.<module>` (not through `main.py`), so they test tool business logic in isolation from MCP registration.
- `mock_settings` fixtures supply a `MagicMock` with `audit_log_enabled=False` so `audit_action` calls short-circuit without needing a real audit backend.
- `ValidationError` from `@/src/utils/exceptions` is asserted in tests that verify `confirm=False` is rejected; `ValueError` is asserted for tests that verify empty update payloads are rejected.
- Tests follow pytest-asyncio conventions: all async tests are decorated with `@pytest.mark.asyncio`.

### Core Implementation

- **Mock setup pattern**: Each test patches `UniFiClient` at the module level (`src.tools.<module>.UniFiClient`), configures `__aenter__`/`__aexit__` as `AsyncMock`, and sets `mock_client.get`/`.post`/`.put`/`.delete` return values before invoking the tool function.
- **Empty-payload tests**: Update functions are tested with a call that provides no optional fields; the test asserts a `ValueError` is raised. Because the guard is placed *before* the `async with` block, this raises correctly without needing the mock client to be entered.
- **Redaction verification**: Tests for RADIUS Account and RADIUS Profile functions assert that `x_password`, `auth_secret`, and similar fields are set to `"***REDACTED***"` in the returned dict.

### Things to Know

- The placement of `ValueError` guards in tool functions matters for testability: guards placed *inside* `async with UniFiClient(...) as client:` are swallowed by `AsyncMock.__aexit__`'s truthy return value. Tests that assert `ValueError` are only reliable when the guard is outside the context manager.
- `dry_run` tests for update functions verify that when `dry_run=True` and no fields are provided, an empty-payload dry-run response is returned (not a `ValueError`), because the `not dry_run` short-circuit allows an empty payload through in dry-run mode.

Created and maintained by Nori.
