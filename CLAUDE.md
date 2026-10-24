# UniFi MCP Server - Claude Instructions

Project-specific instructions for AI coding assistants working on the UniFi MCP Server. `AGENTS.md` has the full rules for all agents; this file is the short version plus what Claude needs to start.

## Project Overview

The UniFi MCP Server is a Model Context Protocol (MCP) server that exposes the UniFi Network, Protect and Site Manager APIs as MCP tools, so AI agents can read and change UniFi infrastructure through one standard interface.

- **Version**: v0.6.1 (`pyproject.toml`; see `DEVELOPMENT_PLAN.md` §5 for release-versioning notes)
- **Python**: 3.11+
- **Framework**: FastMCP, with httpx for HTTP and Pydantic v2 for models
- **Size**: 343 tools in local mode and 71 in cloud mode, from 60 tool modules in `src/tools/`. Over 3,500 unit tests; the CI coverage gate is 80% (`pyproject.toml`), and total coverage is about 94%.

## Before Starting Work

1. Read the documentation that applies to the task:
   - `README.md` - features and configuration
   - `AGENTS.md` - rules for all AI agents
   - `API.md` - reference for every MCP tool
   - `DEVELOPMENT_PLAN.md` and `TODO.md` - roadmap and live status
   - `docs/UNIFI_API.md` - UniFi API notes, including endpoints that do not exist on some firmware
2. Load the skill for the tool set you will change (see [Skills](#skills)).
3. Work on a feature branch. Never commit to `main`.

## Architecture

| Path | What it holds |
|------|---------------|
| `src/main.py` | Server entry point. Builds the tool module lists per API mode and profile, and registers them |
| `src/tool_registry.py` | Wraps every tool: routing, risk tier, read-only and dry-run modes, audit, cache |
| `src/config/config.py` | `Settings` (all environment variables) and the URL path helpers |
| `src/api/` | `UniFiClient` (Network), `ProtectClient`, `SiteManagerClient`, the connection pool and the rate limiter |
| `src/tools/` | One module per feature area. Every public async function is a tool |
| `src/models/` | Pydantic models |
| `src/resources/` | MCP resources |
| `src/fleet/`, `src/worker/` | Multi-controller fleet: registry, router, tokens, `fleet_*` tools, background workers |
| `src/a2a/` | A2A agent card and endpoints |
| `src/utils/` | Validators, exceptions, the hash-chained audit log, metrics |
| `tests/unit/` | Unit tests (`tests/unit/tools/` for tool modules) |

## How Tools Work

- **Registration.** There is no `@mcp.tool()` decorator. `register_module_tools()` in `src/tool_registry.py` registers every public `async def` in a module that `src/main.py` lists. A leading `_` keeps a function private. The wrapper hides the `settings` argument and adds a keyword-only `controller` argument.
- **Modes and profiles.** `_CLOUD_TOOL_MODULES` and `_LOCAL_TOOL_MODULES` in `src/main.py` decide which modules load for `UNIFI_API_TYPE`, and `UNIFI_PROFILE` narrows the set. A new module must be added to the right list and to the matching profile.
- **Read or write.** Every tool carries `@read_tool` or `@write_tool` (`src/utils/tool_kind.py`). Registration fails on a tool with neither, and `UNIFI_READ_ONLY` registers only `@read_tool` tools. `tests/unit/test_tool_declarations.py` fails if a `@read_tool` reaches a controller write.
- **Write tools.** Declare them `@write_tool`. Use `confirm: bool | str = False, dry_run: bool | str = False`, and call `validate_confirmation(confirm, "<operation>", dry_run)` (`src/utils/validators.py`) before any request. On a dry run, return the planned payload without calling the API.
- **Risk tiers.** `tool_tier()` gives each tool `read`, `write` or `destructive`. Names that start with `delete_`, `remove_` or `bulk_delete_`, and names in `DESTRUCTIVE_TOOLS`, are destructive. Roles map to tiers in `src/access.py`.
- **When you add or rename a tool**, regenerate the tier snapshot: `UPDATE_TOOL_TIERS=1 pytest tests/unit/fleet/test_tiers.py`. A mutating tool whose name has a risky word ("disable", "block", "reset" and others) must be in `DESTRUCTIVE_TOOLS` or in `RISKY_NAME_EXEMPTIONS` with a reason.
- **Audit.** The registry wrapper audits every mutating call. Do not add a second audit path to a new tool.

## Commands

`make help` lists every target. The main ones:

| Command | Does |
|---------|------|
| `make test` | Unit tests |
| `make test-cov` | Tests with the CI coverage gate |
| `make typecheck` | mypy over `src/` |
| `make lint` | black, isort and ruff checks |
| `make ci` | Every blocking CI check |
| `make run` | Start the server from `.env` |

**Known local problems** (not caused by your change; report them, do not fix them in a feature branch):

- The pre-commit mypy hook fails with "Duplicate module named src" when you pass file names. It passes `src` in `args` and pre-commit also adds the file names. Use `make typecheck`.
- `.git/hooks/pre-commit` may not be installed (`make hooks` installs it), so `git commit` can run no hooks. Run `pre-commit run --files <changed files>` yourself.
- markdownlint reports MD024 (duplicate heading) on `CHANGELOG.md`. That error is already on `main`.

## API Modes

| `UNIFI_API_TYPE` | Tools | Notes |
|------------------|-------|-------|
| `local` (recommended) | 343 | Gateway at `UNIFI_LOCAL_HOST`. Network, Protect, and the Phase 6 cloud APIs |
| `cloud-v1` | 71 | `https://api.ui.com`. Aggregate statistics, Site Manager, connector proxy, Mobility, InnerSpace, Carrier |
| `cloud-ea` (the code default) | 71 | Early Access cloud API, same limits |

`UNIFI_READ_ONLY` removes every write tool, and `UNIFI_DRY_RUN` forces `dry_run` on. Some features need UniFi Network 9.0+, and some documented endpoints do not exist on all firmware. Check `docs/UNIFI_API.md` before you rely on one.

## Skills

Project skills are in `.claude/skills/` (Claude Code loads them here). Their source is `skills/<name>/SKILL.md`, which also holds the operator skills for using the server. Load the one that covers your change:

| Skill | Use it when you change |
|-------|------------------------|
| `unifi-protect-tools` | Any `src/tools/protect_*.py` module |
| `unifi-network-config-tools` | Networks, WiFi, WAN, DHCP, DNS, QoS, port profiles, switching, VPN |
| `unifi-security-tools` | Firewall rules and policies, zones, groups, ACLs, content filtering, port forwarding, RADIUS |
| `unifi-cloud-fleet-tools` | Site Manager, connector, integration API, Mobility, InnerSpace, Carrier, or the fleet stack |
| `unifi-mcp-tool-builder` | Adding a new tool in any area (the general workflow) |
| `mintlify-docs` | The Mintlify documentation site: `docs.json`, `.mintignore`, `.mintlify/`, a published page, or the `mintlify` MCP server |

To change a skill, edit `skills/<name>/SKILL.md` and copy it to `.claude/skills/<name>/` and `.agents/skills/<name>/`. The `mintlify-docs` skill is the exception: its source of truth is `.mintlify/skills/mintlify-docs/SKILL.md`, because Mintlify serves it from there. `tests/unit/test_agent_docs.py` fails if a copy differs, and checks that this file, `AGENTS.md` and the tool-set skills cite only paths, links and names that exist. Run it after you edit them.

## Current Development Focus

Phases 0–3, 5a (Protect v7) and 6 (Mobility, InnerSpace, Carrier Fabric) are complete. Phase 4 has no open items (v0.6.1 is released; v0.5.0 was tagged but not published, see `DEVELOPMENT_PLAN.md` §5). Phase 5 is partly in place: the A2A agent card, `UNIFI_PROFILE`, read-only and dry-run modes, bearer auth on network transports, roles over risk tiers with server-issued tokens, the hash-chained audit log, `/metrics`, and the fleet stack (Phases 0–4 of `docs/FLEET_SCALING_PLAN.md`). See `TODO.md` for the live status.

## Key Principles

1. **Safety first**: no write without `confirm=True`, and every write supports `dry_run`.
2. **Test first**: write the failing test, then the code. Integration tests need real UniFi hardware, so say when a change is verified only against mocks.
3. **Consistency**: copy the pattern of the nearest existing tool.
4. **Security**: never commit credentials, and never log an API key.

## Additional Resources

- [AGENTS.md](AGENTS.md) - rules for all AI agents
- [CONTRIBUTING.md](CONTRIBUTING.md) - contribution guidelines
- [SECURITY.md](SECURITY.md) - security policy
- [docs/archive/TESTING_PLAN.md](docs/archive/TESTING_PLAN.md) - testing strategy (archived)
- [Issues](https://github.com/enuno/unifi-mcp-server/issues)

---

**Last Updated**: 2026-10-13
