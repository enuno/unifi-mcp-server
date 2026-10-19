# A2A Integration

Operator runbook for agent-to-agent capability discovery.

## Purpose

Advertise the UniFi MCP Server in a machine-readable way so orchestration systems and peer agents can discover its capabilities, auth model, and tool surface without manual inspection.

## What is served

On the `http`, `sse` and `streamable_http` transports the server registers these routes, each behind the same bearer token as `/mcp` (`MCP_AUTH_TOKEN`, or a fleet token):

| Route | Returns |
|---|---|
| `GET /a2a/agent-card` | The summary card from `get_agent_card_handler()` in `src/a2a/http_handlers.py`: name, version, capabilities, auth schemes and modes, and the other `/a2a/*` URLs |
| `POST /a2a/discover` | The full card from `build_agent_card()` in `src/a2a/agent_card.py`, built from the live tool registry, so it matches the tools this deployment registered |
| `POST /a2a/delegate`, `POST /a2a/confirm` | Delegated tool calls and their confirmation step |
| `GET /a2a/audit` | A2A audit records |

`agent-card.json` at the repository root is a copy of the `/a2a/agent-card` response for the current release. A unit test (`tests/unit/a2a/test_agent_card.py`) fails when the two differ, so regenerate the file when the card or the package version changes. Nothing is served at `/.well-known/agent-card.json`, and stdio serves no HTTP at all.

## What the agent card should describe

At minimum, the manifest should include:

- server name and version
- transport mode(s)
- contact or ownership metadata
- supported UniFi domains
- auth requirements
- tool exposure profiles
- documentation URLs
- webhook or event capabilities if enabled

## Operational objectives

- Make the server discoverable to orchestration platforms.
- Keep the advertised capabilities synchronized with the real tool surface.
- Avoid exposing secrets or internal-only paths in the manifest.
- Keep the card valid JSON and easy to validate automatically.

## Publication procedure

1. Change the card in `get_agent_card_handler()`, not in the JSON file.
2. Regenerate the file: `python -c "import json; from src.a2a.http_handlers import get_agent_card_handler as c; print(json.dumps(c(), indent=2))" > agent-card.json`
3. Run `pytest tests/unit/a2a/test_agent_card.py`.
4. After a deploy, fetch `GET /a2a/agent-card` with a bearer token and confirm the version.

## Validation checklist

- JSON parses without errors.
- Capability list matches the server configuration.
- `agent-card.json` matches `GET /a2a/agent-card` (the unit test checks this).
- No secrets, tokens, or internal-only credentials appear in the file.

## Common failure modes

- agent card drifts from the actual tool surface
- HTTP endpoint serves stale content after a release
- discovery clients cache an outdated manifest
- manifest includes implementation details that should remain private

## Operator notes

- Treat the agent card as part of the public contract.
- Keep changes in sync with tool exposure profiles, controller capabilities, and auth policy.
- Re-validate after every release that changes the tool surface.

## Status

Implemented: the `/a2a/*` routes above ship in the server. The repository card tracks the served one.
