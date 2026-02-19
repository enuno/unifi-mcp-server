# Noridoc: tests/unit

Path: @/tests/unit

### Overview

- Contains the full unit test suite for the UniFi MCP Server, organized into subdirectories that mirror the `@/src/` package structure.
- All tests are offline — they mock `UniFiClient`, `httpx`, and other I/O boundaries so no real UniFi controller or network is needed.
- Test files at the root of `tests/unit/` cover cross-cutting concerns: server startup, security, caching, and model validation.

### How it fits into the larger codebase

- Subdirectories (`api/`, `tools/`, `models/`, `resources/`, `config/`, `utils/`, `webhooks/`) mirror `@/src/` and test each subsystem in isolation.
- Root-level test files test behavior that spans the entire server lifecycle (e.g., module import behavior, security headers, cache logic) rather than any single tool or API call.
- `conftest.py` files at each level provide shared fixtures (`mock_settings`, `mock_client`, etc.) used across test modules.

### Core Implementation

- **`test_main_agnost_import.py`**: Regression tests for issue #42. Verifies that `src.main` can be imported (i.e., the server starts) regardless of the state of the `agnost` package — whether it is missing, has a broken API, or has removed exports. Tests use `_reload_main()` which purges `src.main` from `sys.modules` and reimports it with controlled env vars and a patched `sys.modules["agnost"]`.
- **`test_security.py`**: Tests for PII handling, credential redaction, and input validation behaviors across the server.
- **`test_cache.py`**: Tests for the optional Redis caching layer in `@/src/cache.py`.
- **Tool subdirectory** (`@/tests/unit/tools/`): One test file per tool module, covering CRUD surface and edge cases for every `@mcp.tool()` registered in `main.py`.

### Things to Know

- The `_reload_main()` helper in `test_main_agnost_import.py` is necessary because Python caches module imports; without clearing `sys.modules["src.main"]`, changing `os.environ` or `sys.modules["agnost"]` between tests has no effect on the already-imported module.
- Tests that inject a broken `agnost` module do so by assigning directly to `sys.modules["agnost"]` before reimporting `src.main`, then restoring the original value in a `finally` block.

Created and maintained by Nori.
