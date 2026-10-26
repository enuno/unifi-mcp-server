# A2A Integration

Operator runbook for agent-to-agent capability discovery and delegation.

## Purpose

Advertise the UniFi MCP Server in a machine-readable way so orchestration
systems and peer agents can discover its capabilities, auth model and tool
surface without manual inspection, and let a peer agent delegate a tool call
to it.

## What this is, and what it is not

The A2A **specification** (a2a-protocol.org) defines a task-based protocol:
`message/send`, a Task lifecycle, streaming updates, push notifications and
an `A2A-Version` header. **This server does not implement that protocol.**
There is no `a2a-sdk` dependency, and no Task, Message, Part or Artifact
data model exists in the codebase.

What the server implements is a smaller surface that serves the same
purpose:

- **Discovery.** An Agent Card and a capability manifest, both built from
  the live tool registry.
- **Delegation.** A request/response endpoint that runs a registered tool,
  with the server's own confirmation, role and audit controls in force.

The Agent Card follows the **object shape** of the A2A specification
version 0.3.0 (section 5.5), so an A2A client can parse it. The card
declares `streaming: false` and `pushNotifications: false` because the
server implements neither. The card never claims a capability the server
does not have.

The gap and the decision behind it are recorded in
[docs/AUDIT_A2A_SKILLS.md](docs/AUDIT_A2A_SKILLS.md). Implementing the task
protocol would mean adopting the `a2a-sdk` dependency and rebuilding the
delegation path around Task objects — a substantial architectural change
that this repository gives no direction for, so it is not implemented and
not advertised.

## What is served

On the `http`, `sse` and `streamable_http` transports the server registers
these routes. Every one of them is behind the same bearer token as `/mcp`
(`MCP_AUTH_TOKEN`, or a fleet token). On stdio, no HTTP is served at all.

| Route | Method | Returns |
|---|---|---|
| `/a2a/agent-card` | GET | The Agent Card |
| `/.well-known/agent-card.json` | GET | The same Agent Card, at the path the A2A specification recommends |
| `/a2a/discover` | POST | The capability manifest: the card, the per-domain tool inventory and the tool counts |
| `/a2a/delegate` | POST | Runs a delegated tool call |
| `/a2a/confirm` | POST | Approves a held call and runs it |
| `/a2a/audit` | GET | The A2A audit trail. Requires the `admin` role |

`/a2a/audit` answers `403` to a `viewer` or `operator` token, and `401` to
a request with no valid token.

## The Agent Card

The card is built by `src/a2a/capabilities.py` and `src/a2a/agent_card.py`
from the **live tool registry**. A card therefore describes the tools this
deployment actually registered, and it changes when the tool surface or the
configuration changes.

| Field | Source |
|---|---|
| `protocolVersion` | The A2A specification version whose card shape is used: `0.3.0` |
| `name`, `description`, `version` | The server and its package version |
| `url` | The address a client should use, from `UNIFI_SERVER_HOST` and `UNIFI_SERVER_PORT` |
| `preferredTransport` | `HTTP+JSON` |
| `capabilities` | `streaming`, `pushNotifications`, `stateTransitionHistory` — all `false` |
| `securitySchemes`, `security` | The bearer-token scheme the server implements |
| `defaultInputModes`, `defaultOutputModes` | `application/json` |
| `skills` | One entry per registered tool, with its input and output schemas and an example |
| `metadata` | The deployment summary: tool counts by tier, the domains present, the API mode, the read-only and dry-run flags, the fleet flag, the safety requirements and the integration examples |

The `metadata` block is where the configuration shows through. A
read-only server reports `readOnly: true`; a server in `minimal` profile
reports only the domains that profile registers; a fleet server reports
`fleet: true`.

The card carries **no credential, no controller address and no filesystem
path**. It is public metadata, and a unit test enforces that.

### The repository artifact

`agent-card.json` at the repository root is the reference card for a
**default local deployment**. The served card legitimately differs between
configurations, so the artifact is a pinned reference rather than a
byte-for-byte copy of whatever a given server serves. Regenerate it after
changing the card, the tool surface or the package version:

```bash
python scripts/generate_agent_card.py
```

`tests/unit/a2a/test_agent_card.py` checks the artifact against the card
the builder produces for the reference configuration, so the two cannot
drift apart.

## The capability manifest

`POST /a2a/discover` returns the card plus the inventory an orchestrator
needs to choose a task:

```json
{
  "agent": { "...": "the agent card" },
  "transport": "streamable_http",
  "api_modes": ["local"],
  "capabilities": ["tool-delegation", "safety-controls", "audit-log", "network-management"],
  "domains": { "network": ["create_network", "..."], "protect": ["..."] },
  "tool_counts": { "total": 343, "read": 204, "write": 90, "destructive": 49 }
}
```

The optional sections appear on request: `include_audit` adds the audit
endpoint, and `include_rate_limits` adds the per-tier delegation limits.

The tier of a tool is the one the server enforces, derived from the tool's
own function rather than from its name. A client can therefore trust the
counts: a tool listed as `write` needs the operator role, and a tool listed
as `destructive` needs the admin role and a confirmation.

## Delegation

`POST /a2a/delegate` runs a registered tool on the caller's behalf.

```json
{ "tool_name": "list_sites", "params": {}, "agent_id": "orchestrator-1" }
```

The call goes through the tool's registered wrapper, so the server's
controls apply exactly as they do for an MCP client:

- the caller's **role** must grant the tool's tier,
- a mutating tool still needs its `confirm=True`,
- `UNIFI_DRY_RUN` still forces a preview,
- the call is **audited**.

The request body cannot widen the caller's access. The permissions come
from the bearer token that authenticated the request, resolved from the
token's role. A payload may name `scopes`, which narrow what the role
already grants; they cannot widen it. A `viewer` token asking for
`destructive` access in the payload is refused.

### The confirmation step

A destructive call, or a write that the safety policy holds, is not run
directly. The endpoint answers `confirmation_required` with a token and
the held call:

```json
{
  "status": "confirmation_required",
  "tool_name": "delete_firewall_zone",
  "confirmation_token": "...",
  "expires_at": "...",
  "reason": "destructive action requires confirmation"
}
```

Approve it through `POST /a2a/confirm` and the held call runs:

```json
{ "token": "...", "response": "approved" }
```

The token is bound to a hash of the parameters it was issued for, and it
expires. A rejected, expired or unknown token runs nothing.

### Outcomes

| `status` | Meaning |
|---|---|
| `ok` | The call ran; `result` holds the tool's result |
| `confirmation_required` | The call is held; approve it through `/a2a/confirm` |
| `denied` | The caller's role does not grant the tool's tier, or the safety policy refused it |
| `unavailable` | The deployment has no tool executor configured, so nothing ran |
| `error` | The request was malformed, or the tool call itself failed |

`unavailable` is deliberately distinct from `ok`: a delegation that cannot
run must not report success.

## Security

- Every route requires the bearer token. An unauthenticated request is
  answered `401` with a `WWW-Authenticate: Bearer` header.
- `/a2a/audit` additionally requires the `admin` role.
- The caller's role is resolved from the verified token and bound to the
  request, so the A2A layer cannot be talked into a wider access than the
  token carries.
- The card and the manifest carry no secret, no controller address and no
  private path.
- Delegated calls are audited with the principal, the tool, the tier and
  the redacted arguments. The tool's response is never recorded.

## Operational objectives

- Make the server discoverable to orchestration platforms.
- Keep the advertised capabilities synchronized with the real tool surface.
- Avoid exposing secrets or internal-only paths in the manifest.
- Keep the card valid JSON and easy to validate automatically.

## Validation checklist

- JSON parses without errors.
- The card's `skills` are the tools this deployment registered.
- The capability list follows the configuration.
- `agent-card.json` matches the reference card
  (`pytest tests/unit/a2a/test_agent_card.py`).
- No secret, controller address or internal path appears in the card.
- Every route refuses an unauthenticated request.

Run the A2A tests:

```bash
pytest tests/unit/a2a/ -q
```

## Common failure modes

- The agent card drifts from the actual tool surface — prevented by
  building the card from the live registry, and by regenerating
  `agent-card.json` when the tool surface changes.
- The HTTP endpoint serves stale content after a release — the card is
  built per request, so it cannot be stale; only the repository artifact
  can be, and a test fails when it is.
- Discovery clients cache an outdated manifest — the client should
  re-read the card after a version change.
- The manifest includes implementation details that should remain private —
  prevented by the card carrying no address, path or credential.

## Operator notes

- Treat the agent card as part of the public contract.
- Keep changes in sync with the tool exposure profiles, the controller
  capabilities and the auth policy.
- Re-validate after every release that changes the tool surface.
- The card describes what the server can do. It does not authorise
  anything: a delegated call is still subject to the role check, the
  confirmation gate and the audit trail.
