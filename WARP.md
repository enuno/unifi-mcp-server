# WARP.md

## Purpose

This document defines recommended practices, configuration parameters, and integration strategies for using the warp.dev AI coding agent with this repository. It ensures that the agent’s outputs align with the UniFi MCP Server’s technical requirements, coding standards, and quality/safety mandate.

***

## Agent Role \& Scope

- **Primary Role:** The WARP agent acts as an autonomous assistant for code generation, refactoring, documentation, testing, and DevOps operations in this repository.
- **Integration Points:** Use WARP for high-velocity coding (Python), Dockerfile editing, CI/CD script generation, and rapid scaffolding of new MCP tools, but restrict architectural decisions to human experts or architect agents.
- **Boundaries:** Do not assign WARP production deployments or security policy changes unless results are peer reviewed and approved.

***

## Setup \& Configuration

- **Initialization:** Confirm the agent has full access to the working tree, context from `README.md`, `API.md`, `.env.example`, and all source files in `src/` and `tests/`.
- **Environment:** Default context includes Python 3.10+ standards, Pydantic data models, async/await patterns, and Docker-based deployment flows. Reference `.env` and Docker Compose files for accurate environment variables.
- **Activation:** Agent usage should be recorded in commit messages (e.g., `warp: added client management tool`) and flagged in pull requests for review.

***

## Usage Guidelines

- **Prompt Design:** Provide WARP with context-rich, explicit prompts—include function signatures, endpoint names, error-handling expectations, and reference files.
- **Code Standards:** Enforce Black, Ruff, and MyPy checks on all WARP-edited code; auto-fix style violations.
- **Test Coverage:** Require code fixes and new features from WARP to include or update associated unit tests in `tests/unit/`. Aim for increased coverage beyond 37% (current baseline).
- **Documentation:** Ensure that all functional updates/additions by WARP update relevant docs in `README.md`, `API.md`, or tool-specific Markdown files.

***

## Safety, Validation, and Human-AI Review

- **Dry-run Mode:** When invoking mutating MCP tools, use `dry_run=True` before confirmation.
- **Audit Logging:** All WARP-driven changes should be verifiable via commit history and logs.
- **Validation:** New code must pass CI, static analysis, and review checks automatically triggered on pull request creation.
- **Peer Review:** Human review is mandatory for changes that affect API security, authentication, device control, or firewall logic.

***

## Recommended Workflow

1. **Define Task:** Specify required endpoint/tool, input/output, and any error-handling policies.
2. **Engage Agent:** Pass complete context and all relevant files/folder paths in prompt.
3. **Review Output:** Run tests, examine commit diffs, and validate updated docs.
4. **Human Review:** Request peer/maintainer review per CONTRIBUTING.md.
5. **Merge with Caution:** Require at least one successful CI run and code owner approval for production code.

***

## Example Prompt

```markdown
warp: add async API tool for listing all VLANs in a site
Context: See `src/tools/networks.py` for patterns, `API.md` for endpoint spec. Output should include Pydantic typing, validation, and audit logging. Add/update test in `tests/unit/test_networks.py`.
```


***

## Security \& Permissions

- **Restrict Privileges:** Assign only minimum necessary permissions for editing, CI/CD, and tool operation.
- **Credential Handling:** Never provide WARP access to production or secret credentials.
- **Sensitive Actions:** For device reboots, firewall rules, or user blocking, require dual confirmation from agent and human.

***

## References

- See [README.md](https://github.com/enuno/unifi-mcp-server/blob/main/README.md) for setup
- See [API.md](https://github.com/enuno/unifi-mcp-server/blob/main/API.md) for supported endpoints and formats
- See [CONTRIBUTING.md](https://github.com/enuno/unifi-mcp-server/blob/main/CONTRIBUTING.md) for collaboration practices
- Follow general agent/AI usage guidance in AGENTS.md

***

## Maintenance

Update this file anytime project workflows or agent integrations change, or when warp.dev agent capabilities are updated. Always version and date documentation changes for traceability.

