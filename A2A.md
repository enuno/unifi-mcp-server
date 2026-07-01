# A2A Integration

Operator runbook for agent-to-agent capability discovery.

## Purpose

Advertise the UniFi MCP Server in a machine-readable way so orchestration systems and peer agents can discover its capabilities, auth model, and tool surface without manual inspection.

## Planned artifacts

- `agent-card.json` at the repository root
- `/.well-known/agent-card.json` when HTTP transport is enabled
- capability and auth metadata
- a stable tool-manifest reference

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

### 1. Author the manifest

1. Add or update `agent-card.json` in the repository.
2. Keep the file concise and deterministic.
3. Use stable field names and avoid free-form text where structured fields exist.

### 2. Publish over HTTP when enabled

1. Serve the manifest at `/.well-known/agent-card.json`.
2. Ensure the response is cacheable but not stale beyond your release cadence.
3. Confirm the endpoint returns the same content as the repository file.

### 3. Verify discovery

1. Fetch the manifest from the HTTP endpoint.
2. Validate that it parses as JSON.
3. Confirm the capability list matches the current deployment mode.
4. Confirm the auth metadata matches the production policy.

## Validation checklist

- JSON parses without errors.
- Capability list matches the server configuration.
- HTTP-served manifest matches the repository source of truth.
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

Phase-5 documentation.