# UniFi MCP Server - Claude Instructions

---

## ⚡ Fork Context — Read This First

This is **Aaron's fork** (`The-Early-risers/unifi-mcp-server`) of `enuno/unifi-mcp-server`.
The goal is to fix real bugs discovered during home network segmentation work, then
contribute them back upstream as PRs.

### Completed work

| # | Issue | Branch | Status |
|---|-------|--------|--------|
| 1 | `assign_network_to_zone` sends `networks` but API expects `networkIds` | upstream PR #54 | DONE ✅ |
| 2 | `list_firewall_policies` has no pagination | upstream PR #55 | DONE ✅ |
| 3 | Full ZBF management — dead zbf_matrix removal, zone filtering, `get_zone_policy_matrix` | `feat/zbf-management` → main | DONE ✅ |
| 4 | CI/CD hardening — real enforcement gates, security scanning, docstring coverage | `feat/ci-hardening` → main (PR #1) | DONE ✅ |

### Current work — next priorities

| # | Task | Notes |
|---|------|-------|
| 5 | Full-field `update_firewall_policy` | BLOCKED — API research gate (see `docs/research/firewall/FIREWALL_POLICIES_V2.md`) |
| 6 | VPN Management (`site_vpn.py`) | 0% test coverage |
| 7 | WAN Management (`wans.py`) | 0% test coverage |

### How we work

**Always start a session with `/dev-workflow start <branch-name>`** — this syncs
upstream, creates the feature branch, activates the venv, and checks the live controller.

Full rules in `.claude/skills/dev-workflow/SKILL.md`. Short version:

- Never commit to `main` — always a `fix/` or `feat/` branch
- **API research gate must pass before implementation** — see below
- Unit tests first, then validate against the live controller before marking done
- All quality gates must pass: `pre-commit run --all-files`
- Conventional commits enforced by pre-commit hook

### API Research Gate

Before implementing any new tool or modifying an existing one that touches a UniFi API endpoint, a research doc **must exist and be marked `VERIFIED`** in `docs/research/`. No exceptions.

**Required steps in order:**

| Step | Action | Output |
|------|--------|--------|
| 1 | Fetch portal docs (`developer.ui.com`) | Note path, schema, version |
| 2 | Check existing `docs/research/` for prior findings | Reuse or update if found |
| 3 | Live `GET` probe on target controller | Actual response shape |
| 4 | Live mutating probe (`PUT`/`POST`/`PATCH`) | Confirm partial vs full-object, accepted fields, error shapes |
| 5 | Save to `docs/research/<area>/<ENDPOINT>.md` | Use `ENDPOINT_RESEARCH_TEMPLATE.md` |
| 6 | Mark doc `VERIFIED` with firmware version + date | Gate is now clear |

**Version discrepancy rule:** If portal docs describe a different API path than what the code uses (e.g. `/integration/v1/` vs `/v2/api/`), call it out explicitly in the research doc and resolve which path is correct before writing any code.

**If live access is unavailable:** Stop. State the blocker. Do not implement based on docs alone.

### Live controller

| Setting | Value |
|---------|-------|
| Host | `192.168.100.1` (UDM-Pro-Max) |
| API type | `local` |
| Site ID | `default` |
| SSL verify | `false` |
| `.env` | Pre-configured — just add your `UNIFI_API_KEY` |

Get the API key from: UniFi UI → Settings → Control Plane → Integrations → Create API Key

### Git remotes

| Remote | URL |
|--------|-----|
| `origin` | `git@github.com:The-Early-risers/unifi-mcp-server.git` (fork) |
| `upstream` | `https://github.com/enuno/unifi-mcp-server.git` (source) |

### Key source files

| File | What it does |
|------|-------------|
| `src/tools/firewall_zones.py` | Zone management (list, create, update, delete, assign/unassign networks) |
| `src/tools/firewall_policies.py` | Firewall policy CRUD — primary file for ZBF work |
| `src/models/firewall_policy.py` | Pydantic models for policy API |
| `ZBF_STATUS.md` | Detailed status of what works vs what doesn't |
| `docs/research/firewall/FIREWALL_POLICIES_V2.md` | API research doc — must be VERIFIED before implementing update changes |
| `docs/research/ENDPOINT_RESEARCH_TEMPLATE.md` | Template for new endpoint research docs |
| `tests/unit/` | Unit tests — follow existing patterns here |

### CI/CD pipeline (as of PR #1)

All checks are enforced on every PR — no `continue-on-error` except where noted.

| Check | Tool | Gate |
|-------|------|------|
| Lint | black, isort, ruff (incl. Google D rules) | Hard block |
| Type check | mypy | Non-blocking (147 pre-existing errors) |
| Tests | pytest 3.10 / 3.11 / 3.12, coverage ≥80% | Hard block |
| Docstring coverage | interrogate ≥80% | Hard block |
| SAST | bandit (`-ll` medium+) | Hard block |
| Dependency review | GitHub dependency-review-action | `continue-on-error` — needs Dependency Graph enabled in repo settings |
| Secret scanning | detect-secrets v1.5.0 | Hard block (via pre-commit) |
| Pre-commit | all hooks | Hard block |
| Release | Docker → Trivy scan → push (blocks on HIGH/CRITICAL) | Hard block |
| Release | SBOM (CycloneDX JSON) attached to GitHub Release | Informational |

**Known quirks:**

- `Security Scanning` workflow is `disabled_fork` — GitHub disables it for forks. Security scanning runs via bandit/dependency-review in ci.yml instead.
- `safety check` is deprecated in safety ≥3.0; replaced by bandit + pip-audit.
- mypy has 147 pre-existing type errors from upstream — `continue-on-error: true` until fixed incrementally.
- ruff excludes `.claude/` — pre-commit hook runs on all files but `.claude/skills/` scripts aren't part of the package.

---

This file provides project-specific instructions for AI coding assistants working on the UniFi MCP Server.

## Project Overview

The UniFi MCP Server is a Model Context Protocol (MCP) server that exposes the UniFi Network Controller API, enabling AI agents and applications to interact with UniFi network infrastructure in a standardized way.

**Current Version**: v0.2.3
**Python Version**: 3.10+
**Framework**: FastMCP

## Quick Start for AI Assistants

### Before Starting Work

1. **Read Key Documentation**:
   - `README.md` - Project overview and features
   - `AGENTS.md` - Universal AI agent guidelines
   - `DEVELOPMENT_PLAN.md` - Roadmap and priorities
   - `TODO.md` - Current tasks and phase breakdown
   - `API.md` - Complete MCP tool documentation

2. **Understand the Architecture**:
   - `src/main.py` - MCP server entry point
   - `src/api/` - UniFi API client
   - `src/models/` - Pydantic data models
   - `src/tools/` - MCP tool implementations
   - `tests/unit/` - Unit tests (1,156 tests passing)

### Development Workflow

1. **Feature Development**:
   - Create feature branch: `git checkout -b feature/your-feature`
   - Follow TDD: Write tests first, then implementation
   - Maintain 80% minimum test coverage for new code
   - Use Pydantic models for all data structures
   - Add comprehensive docstrings (Google style)

2. **Code Quality**:
   - Run tests: `pytest tests/unit/`
   - Format: `black src/ tests/` and `isort src/ tests/`
   - Lint: `ruff check src/ tests/ --fix`
   - Type check: `mypy src/`
   - Pre-commit: `pre-commit run --all-files`

3. **Safety Mechanisms**:
   - All mutating operations require `confirm=True`
   - Implement dry-run mode for preview
   - Add audit logging for operations
   - Validate all user inputs
   - Never commit secrets or credentials

### Technology Stack

- **Language**: Python 3.10+
- **Framework**: FastMCP (MCP server framework)
- **API Client**: httpx (async HTTP)
- **Data Validation**: Pydantic v2
- **Testing**: pytest with asyncio support
- **Caching**: Redis (optional)
- **Monitoring**: agnost.ai (optional)

### API Modes

The server supports three UniFi API access modes:

1. **Local Gateway API** (Recommended): Full feature support
   - `UNIFI_API_TYPE=local`
   - `UNIFI_LOCAL_HOST=192.168.2.1`

2. **Cloud V1 API**: Stable, aggregate statistics only
   - `UNIFI_API_TYPE=cloud-v1`

3. **Cloud EA API**: Early Access, aggregate statistics only
   - `UNIFI_API_TYPE=cloud-ea`

### Current Development Focus

**Version 0.2.3** (Current):

- ✅ P1 API bug fixes (QoS audit_action, Site Manager decorator, Topology warnings, Backup client methods)
- ✅ P2 RADIUS & Guest Portal — Complete CRUD (get/update for RADIUS accounts and hotspot packages)

**Version 0.2.2** (Complete ✅):

- ✅ Port Profile & Switch Port Management (8 tools)
- ✅ Security hardening (dependency updates, PII removal)
- ✅ API endpoint fixes (RADIUS, firewall, WLAN, network)
- ✅ Bug fixes (dry_run, list handling, type hints)

**Version 0.2.0** (Complete ✅):

- ✅ Zone-Based Firewall (7 working tools)
- ✅ Traffic Flow Monitoring (15 tools)
- ✅ Advanced QoS (11 tools)
- ✅ Backup & Restore (8 tools)
- ✅ Multi-Site Aggregation (4 tools)
- ✅ ACL & Traffic Filtering (7 tools)
- ✅ Site Management (9 tools)
- ✅ RADIUS & Guest Portal (10 tools — full CRUD)
- ✅ Network Topology (5 tools)

**Total**: 86+ MCP tools, 1,156 tests passing

### Important Constraints

1. **UniFi Network 9.0+ Required**: Some features require Network 9.0+
2. **Local API Recommended**: Cloud APIs have limited functionality
3. **Endpoint Verification**: Some documented API endpoints may not exist in all versions
4. **Testing**: Integration tests require real UniFi hardware

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/The-Early-risers/unifi-mcp-server/issues)
- **Documentation**: See `API.md` for complete tool reference
- **Examples**: Check `docs/examples/` for AI assistant prompts

## Key Principles

1. **Safety First**: Never perform destructive operations without confirmation
2. **Quality Over Speed**: Maintain high test coverage and code quality
3. **Clarity**: Write self-documenting code with clear docstrings
4. **Consistency**: Follow existing patterns and conventions
5. **Security**: Never commit credentials, validate all inputs

## Additional Resources

- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [SECURITY.md](SECURITY.md) - Security policy and best practices
- [AGENTS.md](AGENTS.md) - Detailed AI agent guidelines
- [TESTING_PLAN.md](docs/archive/TESTING_PLAN.md) - Testing strategy
- [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) - Complete roadmap

---

**Last Updated**: 2026-05-15
**Maintained By**: Aaron Walker
