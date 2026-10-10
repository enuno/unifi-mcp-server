# UniFi MCP Server - Claude Instructions

This file provides project-specific instructions for AI coding assistants working on the UniFi MCP Server.

## Project Overview

The UniFi MCP Server is a Model Context Protocol (MCP) server that exposes the UniFi Network Controller API, enabling AI agents and applications to interact with UniFi network infrastructure in a standardized way.

**Current Version**: v0.5.0 (package version, tag pending; last tagged release is v0.2.5; see `DEVELOPMENT_PLAN.md` §5 for release-versioning notes)
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
   - `tests/unit/` - Unit tests (3,152 tests passing, 93% line coverage)

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
   - Or via `make`: `make lint`, `make test`, `make typecheck`, and `make ci` for every blocking CI check (`make help` lists all targets)

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

Phases 0–3, 5a (Protect v7) and 6 (Mobility, InnerSpace, Carrier Fabric) are complete. **Phase 4** (testing, polish, minor gaps, developer experience) is active, and Phase 5 is partially started. See `TODO.md` and `DEVELOPMENT_PLAN.md` for the live status of each item.

**Phase 4 open items**: release tag (v0.5.0, pending hardware verification).

**Phase 5 already in place**: A2A agent card and endpoints (behind bearer auth), `UNIFI_PROFILE` tool profiles, `UNIFI_READ_ONLY` and `UNIFI_DRY_RUN` modes, bearer auth on network transports, roles over risk tiers with server-issued tokens, hash-chained wrapper-level audit log, `/metrics`, and fleet routing (Phases 0–3 of `docs/FLEET_SCALING_PLAN.md`).

**Total**: 343 MCP tools registered in local mode across 60 tool modules, 3,152 unit tests passing

### Important Constraints

1. **UniFi Network 9.0+ Required**: Some features require Network 9.0+
2. **Local API Recommended**: Cloud APIs have limited functionality
3. **Endpoint Verification**: Some documented API endpoints may not exist in all versions
4. **Testing**: Integration tests require real UniFi hardware

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/enuno/unifi-mcp-server/issues)
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

**Last Updated**: 2026-10-10
**Maintained By**: Development Team
