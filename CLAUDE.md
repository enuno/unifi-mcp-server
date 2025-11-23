Import command and agent standards from docs/claude/
feat: implement comprehensive UniFi MCP command and agent system
Add complete custom command and agent infrastructure for UniFi MCP Server
development with multi-agent orchestration, quality gates, and automation.

## Phase 1: Upgraded Existing Commands (10 files)
- Enhanced all existing slash commands with full YAML frontmatter
- Added explicit tool permissions (allowed-tools) for security
- Added author and version fields following docs/claude/ standards
- Upgraded: build-docker, check-deps, clean, docs, format, lint, pr, security, setup, test

## Phase 2: New UniFi-Specific Commands (5 files)
Created specialized commands with unifi-mcp- prefix:
- unifi-mcp-add-tool: Scaffold new MCP tools (model + function + tests + docs)
- unifi-mcp-test-coverage: Analyze coverage gaps and reach 80% target
- unifi-mcp-update-docs: Auto-generate API.md from tool docstrings
- unifi-mcp-release-prep: Comprehensive release preparation workflow
- unifi-mcp-inspect: Start MCP Inspector for interactive testing

## Phase 3: Specialized Agents (4 files)
Built multi-agent system in .claude/agents/:
- unifi-tool-developer: MCP tool development specialist (TDD, async, 80% coverage)
- unifi-test-coverage: Systematic coverage improvement following TESTING_PLAN.md
- unifi-documentation: Documentation maintenance and auto-generation
- unifi-release-manager: Multi-agent orchestrator for release coordination

## Phase 4: Multi-Agent Coordination (1 file)
- MULTI_AGENT_PLAN.md: Complete coordination framework
  - Workflow templates (release, coverage, tool development)
  - Communication protocols (status updates, handoffs, quality gates)
  - Coordination patterns (parallel gathering, sequential resolution)
  - Progress tracking and metrics

## Phase 5: Project Instructions (1 file)
- CLAUDE.md: Import directive for docs/claude/ standards

## Key Features
- Security-first design with explicit tool permissions
- 80% minimum test coverage enforcement
- Multi-agent orchestration (parallel + sequential)
- Auto-documentation generation from code
- TDD workflow with comprehensive testing
- Release automation with quality gates
- Comprehensive examples and templates

## Files
- New: 12 files (5 commands + 4 agents + 2 docs + 1 directory)
- Modified: 10 command files (YAML frontmatter upgrades)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
