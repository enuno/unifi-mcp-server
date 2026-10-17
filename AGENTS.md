# AI Agent Guidelines for UniFi MCP Server

Rules and workflows for every AI coding agent that contributes to the UniFi MCP Server. `CLAUDE.md` is the short version; the skills in `.claude/skills/` cover each tool set in detail.

## Table of Contents

- [Core Principles](#core-principles)
- [Project Layout](#project-layout)
- [Workflow](#workflow)
- [Writing a Tool](#writing-a-tool)
- [Testing Requirements](#testing-requirements)
- [Security Guardrails](#security-guardrails)
- [UniFi API Guidelines](#unifi-api-guidelines)
- [Code Quality Standards](#code-quality-standards)
- [Documentation Requirements](#documentation-requirements)
- [Approval and Merge Policies](#approval-and-merge-policies)
- [XERJ (code search)](#xerj-code-search)

## Core Principles

1. **Safety first.** No write operation runs without explicit confirmation, and every write supports a dry run. Validate inputs. Never commit or log secrets.
2. **Evidence over assumption.** Read the code before you describe it. UniFi endpoints differ between firmware versions, so a test against mocks proves the request shape, not that the endpoint exists. Say which one you verified.
3. **Consistency.** Copy the pattern of the nearest existing tool. Do not add a second way to do something the codebase already does.
4. **Small, reviewable changes.** One logical change per commit. Do not refactor code that the task does not need.

## Project Layout

```text
src/
├── main.py              # Entry point: tool module lists per API mode and profile, registration
├── tool_registry.py     # Tool wrapper: routing, risk tiers, read-only/dry-run, audit, cache
├── access.py            # Roles and the risk tiers each role may call
├── cache.py             # Redis read cache (optional)
├── memory.py            # Supermemory operator notes (optional)
├── config/config.py     # Settings (every environment variable) and URL path helpers
├── api/                 # UniFiClient, ProtectClient, SiteManagerClient, pool, rate limiter
├── tools/               # One module per feature area; every public async function is a tool
├── models/              # Pydantic models
├── resources/           # MCP resources
├── fleet/               # Multi-controller registry, router, tokens, fleet_* and admin tools
├── worker/              # Background health and sync workers
├── a2a/                 # A2A agent card and endpoints
└── utils/               # Validators, exceptions, audit log, metrics, SIEM export
tests/
├── conftest.py          # Clears UNIFI_* environment variables for every test
├── unit/                # Unit tests; tests/unit/tools/ holds the tool module tests
└── integration/         # Needs a real controller; marked with @pytest.mark.integration
```

Naming: modules and functions use snake_case, classes use PascalCase, and test files start with `test_`.

## Workflow

### Before you start

1. Read `README.md`, `API.md` and, for UniFi endpoint details, `docs/UNIFI_API.md`.
2. Load the skill for the tool set you will change (listed in `CLAUDE.md`).
3. Find the nearest existing tool and its test, and copy their pattern.
4. Create a feature branch. Never commit to `main`.

### While you work

1. Write the failing test first, and watch it fail for the reason you expect. Then write the code.
2. Keep each commit to one logical change.
3. Update `API.md` when you add or change a tool, and `CHANGELOG.md` under `[Unreleased]`.

### Before you open a pull request

1. `make test`, `make typecheck` and `make lint` pass. `make ci` runs every blocking CI check.
2. `pre-commit run --files <changed files>` passes, apart from the known problems listed in `CLAUDE.md`.
3. Review your own diff. State in the pull request what you verified against mocks only.

## Writing a Tool

Tools are plain async functions. `register_module_tools()` in `src/tool_registry.py` registers every public `async def` in a module that `src/main.py` lists. Each one carries `@read_tool` or `@write_tool` from `src/utils/tool_kind.py`, which declares whether it can change controller state; registration fails on a tool with neither. A leading `_` keeps a helper out of the tool list.

A write tool, shortened from `src/tools/protect_relays.py`:

```python
@write_tool
async def update_protect_relay(
    relay_id: str,
    settings: Settings,
    name: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect relay settings.

    Args:
        relay_id: Protect relay identifier
        settings: Application settings
        name: New display name
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect relay", dry_run)
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if not payload:
        raise ValidationError("No updates provided")

    if coerce_bool(dry_run):
        return {"dry_run": True, "operation": "update_protect_relay", "payload": payload}

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"relays/{relay_id}"),
            json_data=payload,
        )
    return ProtectRelay.model_validate(_extract_item(response)).model_dump(by_alias=True)
```

The rules this example follows:

- **Declare it.** `@write_tool` marks a tool that can change state, `@read_tool` one that cannot. `UNIFI_READ_ONLY` registers only `@read_tool` tools, and registration refuses a tool with no declaration, or a `@read_tool` that takes `confirm` or `dry_run`. `tests/unit/test_tool_declarations.py` walks every read tool's calls and fails if one reaches a `post`, `put`, `patch` or `delete`.
- **A write tool takes both `confirm` and `dry_run`.** `UNIFI_DRY_RUN` drops a write tool with no `dry_run`.
- **Check confirmation first.** `validate_confirmation(confirm, operation, dry_run)` raises `ValidationError` unless `confirm` is true or the call is a dry run.
- **Return the dry run before you open a client.** No request may reach the controller on a dry run.
- **Optional update fields default to `None`.** Send only the fields the caller set. Some UniFi endpoints need the whole object (read, merge, write); the network and security skills list which ones.
- **Do not audit in the tool.** The registry wrapper audits every mutating call. It also removes write tools under `UNIFI_READ_ONLY` and forces `dry_run` under `UNIFI_DRY_RUN`.
- **Register the module.** Add it to `_LOCAL_TOOL_MODULES` or `_CLOUD_TOOL_MODULES` in `src/main.py`, and to the `UNIFI_PROFILE` sets that should include it.
- **Update the tier snapshot.** Run `UPDATE_TOOL_TIERS=1 pytest tests/unit/fleet/test_tiers.py`. A destructive tool needs a `delete_`, `remove_` or `bulk_delete_` prefix, or an entry in `DESTRUCTIVE_TOOLS`. A write tool whose name has a risky word ("disable", "block", "reset" and others) must be in `DESTRUCTIVE_TOOLS` or in `RISKY_NAME_EXEMPTIONS` with a reason.

## Testing Requirements

- **Coverage.** The CI gate is 80% (`--cov-fail-under=80` in `pyproject.toml`). New code paths need tests; a bug fix needs a regression test that fails without the fix.
- **Async.** `asyncio_mode = auto` is set in `pytest.ini`. The only declared marker is `integration`, and `--strict-markers` rejects any other.
- **Environment.** `tests/conftest.py` clears every `UNIFI_*` variable. Set what a test needs with `monkeypatch.setenv`.
- **HTTP.** Tool tests patch the module's client class and assert the request path and body. Shortened from `tests/unit/tools/test_acls_tools.py`:

```python
@pytest.fixture
def local_settings(monkeypatch):
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    return Settings()


async def test_list_acl_rules_local_mode(local_settings):
    with patch("src.tools.acls.UniFiClient") as client_class:
        client = AsyncMock()
        client.resolve_site_id = AsyncMock(return_value=SITE_UUID)
        client.get = AsyncMock(return_value={"data": [rule]})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client_class.return_value = client

        result = await list_acl_rules("default", local_settings)

    assert client.get.await_args.args[0] == (
        f"/proxy/network/integration/v1/sites/{SITE_UUID}/acl-rules"
    )
```

- **Make `__aexit__` return `False`.** A bare `AsyncMock()` returns a truthy value, and the `async with` block then swallows every exception, so a broken tool returns `None` and the test can pass for the wrong reason.
- **Use a real `Settings` when the path matters.** A `MagicMock` path helper hides wrong prefixes.
- **Do not test only the mock.** Assert what reaches the boundary (path, method, body) and what the tool returns.

Commands:

```bash
make test                                      # all unit tests
make test-cov                                  # with the CI coverage gate
pytest tests/unit/tools/test_acls_tools.py     # one file
pytest -k local_mode                           # by name
pytest -m integration                          # needs a real controller
```

## Security Guardrails

- **Credentials.** Read keys only through `Settings` (`src/config/config.py`), which loads the environment and `.env`. `.env` is git-ignored; `.env.example` holds placeholders only. The detect-secrets pre-commit hook and the CI "Secret Scanning" job check every commit.
- **Logs and errors.** Never put an API key or token in a log line or an error message. Pass log text through `sanitize_log_message()`.
- **Inputs.** Validate with the helpers in `src/utils/validators.py` (`validate_site_id`, `validate_limit_offset` and others) or with Pydantic models.
- **Network transports.** The server refuses to start an HTTP transport without authentication. Callers authenticate with `MCP_AUTH_TOKEN` or with server-issued tokens (`src/fleet/tokens.py`), and `src/access.py` limits each role to its risk tiers.
- **Audit.** Every mutating call writes a hash-chained audit record. `UNIFI_AUDIT_FAIL_CLOSED` (on by default) refuses the call when the record cannot be written.

## UniFi API Guidelines

### Authentication

The server authenticates with an API key in the `X-API-KEY` header (`Settings.get_headers()`). There are no sessions or cookies.

### API modes

| `UNIFI_API_TYPE` | Base URL | Scope |
|------------------|----------|-------|
| `local` (recommended) | `https://{UNIFI_LOCAL_HOST}:{UNIFI_LOCAL_PORT}` | Full Network and Protect API, plus the Phase 6 cloud APIs |
| `cloud-v1` | `UNIFI_CLOUD_API_URL` (default `https://api.ui.com`) | Aggregate statistics, Site Manager, connector proxy |
| `cloud-ea` (the code default) | same | Early Access; same limits |

### URL spaces

Build paths with the helpers on `Settings`; never hardcode a prefix:

| Helper | Local result | Used for |
|--------|--------------|----------|
| `get_integration_path(ep)` | `/proxy/network/integration/v1/{ep}` | Network integration API (site IDs are UUIDs) |
| `get_protect_integration_path(ep)` | `/proxy/protect/integration/v1/{ep}` | Protect |
| `get_v2_api_path(site)` | `/proxy/network/v2/api/site/{site}` | v2 API (firewall policies, zones); local only |
| `get_site_api_path(site, ep)` | `/proxy/network/api/s/{site}/{ep}` | Legacy API |

Many tools write legacy calls as `/ea/sites/{site_id}/...`. `UniFiClient` translates those for local mode and converts between site names and site UUIDs. `UniFiClient.resolve_site_id()` returns the UUID that the integration API needs.

### Rate limits

`UNIFI_RATE_LIMIT_REQUESTS` (default 100) per `UNIFI_RATE_LIMIT_PERIOD` seconds (default 60) per controller. The limiter is in `src/api/rate_limit.py`; with Redis it is shared across replicas. Do not add another limiter in a tool.

### Errors

Use the exceptions in `src/utils/exceptions.py`. `UniFiClient` maps HTTP 404 to `ResourceNotFoundError`, 401 and 403 to `AuthenticationError`, and other errors to `APIError`. Tools raise `ValidationError` for bad input.

### API documentation

- Official docs: [developer.ui.com](https://developer.ui.com/site-manager-api/gettingstarted)
- Project notes: `docs/UNIFI_API.md`
- Spec snapshots: `scripts/` (Network, Protect, Mobility, InnerSpace, Carrier Fabric)

Before you implement an endpoint, find it in a spec snapshot or in `docs/UNIFI_API.md`. If it is in neither, say so in the pull request.

## Code Quality Standards

- **Type hints** on every function signature. `make typecheck` runs mypy over `src/`.
- **Docstrings** in Google style on every public function. Tool docstrings are the descriptions MCP clients see, so list every argument. The CI "Documentation Coverage" job checks them (`make docs-coverage`).
- **Formatting.** black, isort and ruff, run by `make format` and checked by `make lint`.
- **Errors.** Catch specific exceptions, never a bare `except:`.

## Documentation Requirements

- **`API.md`** for every new or changed tool: parameters, return value, and an example.
- **`README.md`** for user-facing features and settings. A docs test requires every setting to be listed in `API.md` and `.env.example`.
- **`CHANGELOG.md`** under `[Unreleased]`.
- **Skills.** When you change how a tool set works, update its skill in `skills/<name>/SKILL.md` and copy it to `.claude/skills/<name>/` and `.agents/skills/<name>/`; when you change what an operator can do, update the operator skill in `skills/`. `tests/unit/test_agent_docs.py` fails if a copy differs, and checks that `CLAUDE.md`, `AGENTS.md` and the tool-set skills cite only paths, links and names that exist.

## Approval and Merge Policies

AI agents must not:

- merge a pull request without a human's approval
- push directly to `main`
- bypass branch protection, skip CI, or disable pre-commit hooks

Every AI-assisted pull request needs:

- one human approval, passing CI, and no unresolved review comments
- a note that it was AI-assisted, and what was verified only against mocks

Changes to these areas need extra human review: authentication and authorization, audit logging, data deletion, the MCP tool contract (names, parameters, return shapes), and configuration that affects production.

## XERJ (code search)

This project uses XERJ for reference coding. Local setup for this checkout uses
`XERJ_URL=http://127.0.0.1:9300` and the project source prefix `unifi`. Before
writing code that touches unfamiliar territory, search this repo with explicit
URL and prefix so commands do not fall back to the default `localhost:9200`:

```bash
xerj def --url http://127.0.0.1:9300 --prefix unifi "<symbol>"
xerj search --url http://127.0.0.1:9300 --prefix unifi "<plain words>"
```

Before implementing a non-trivial change, search the reference corpus and cite
any borrowed pattern:

```bash
XERJ_URL=http://127.0.0.1:9300 xerj code unifi-mcp-reference "<problem or pattern>"
```

That corpus contains FastMCP, the MCP Python SDK, aiounifi, and pyunifiprotect.
Index or refresh a repo with `xerj autoindex <folder>`. Cite file:line for
anything you rely on.
