---
name: unifi-fleet-operations
description: >
  Operate a multi-controller UniFi deployment behind one MCP server. Use
  when there is more than one controller, when a task must run against a
  specific controller, when a controller is unreachable, or when a
  controller's credentials need to be managed.
---

# UniFi Fleet Operations

Fleet mode puts many controllers behind a single MCP endpoint. The server
holds the controller registry, routes each call to the right controller and
records who did what.

## Prerequisites

Fleet mode needs more than the single-controller setup:

| Requirement | Setting | Consequence when missing |
|---|---|---|
| Postgres | `DATABASE_URL` | The server runs as a single controller. No fleet tools, no registry. |
| Redis | `REDIS_URL` | The shared read cache is disabled. Slower, not broken. |
| A credential key | `UNIFI_CREDENTIAL_KEY` | Controller credentials cannot be encrypted at rest. The server refuses to start. |

The `fleet_*` and registry tools are registered **only** when
`DATABASE_URL` is set. In a single-controller deployment they are absent,
and a call naming one is refused.

## How a call reaches a controller

Every controller-bound tool takes an optional `controller` argument. Without
it, the server uses the selected controller, and failing that the default
one.

```python
# Explicit: this call goes to the named controller
await client.call_tool("list_sites", {"controller": "edge-paris"})

# Implicit: the selected controller, else the default
await client.call_tool("list_sites", {})
```

To choose the controller for subsequent calls:

```python
await client.call_tool("select_controller", {"name": "edge-paris"})
```

`select_controller` sets the selection **for the session**. It is refused
in stateless HTTP mode (`MCP_STATELESS_HTTP=true`), because there is no
session to hold the selection. In that mode, pass `controller` on every
call instead.

## Finding out what is there

| Tool | Answers |
|---|---|
| `list_controllers` | Which controllers the registry holds, and their labels |
| `get_active_controller` | Which controller a call without `controller` would reach |
| `fleet_health` | Per-controller health, capabilities and snapshot age |
| `fleet_sites` | Which sites each controller holds |
| `fleet_inventory` | Device inventory across the fleet, with firmware and state |
| `fleet_fanout` | Runs one read tool across a bounded set of controllers |

### `fleet_health` is a snapshot, not a live read

`fleet_health` answers from the worker's last check. It does not contact a
controller. That makes it cheap and safe to call across the whole fleet.

A **stale** snapshot means the evidence is missing, not that the controller
is healthy. The tool reports the snapshot's age; read it before you
conclude anything.

### `fleet_fanout` contacts controllers

`fleet_fanout` runs a read tool live on many controllers at once. It is
the expensive call, and it is bounded:

- The tool must be a **read**-tier tool. A write-tier tool, or another
  fleet tool, is refused.
- The controller list must be explicit. Do not fan out over the whole
  fleet to chase one detail.
- The fan-out has its own concurrency and deadline limits.

Reach for `fleet_health` first. Use `fleet_fanout` only when the snapshot
cannot answer the question, and say which controllers you contacted and
why.

## Reading across the fleet

The right order for a general question:

1. `list_controllers` — how many controllers are in scope.
2. `fleet_health` — which are up, which are degraded, which are stale.
3. `fleet_sites` — how the sites are distributed.
4. `fleet_inventory` — device state and firmware, when the focus is
   devices.

Report partial coverage explicitly. A summary of three of twenty
controllers is a partial summary, and it must say so.

## Roles and scope

The fleet server issues its own tokens, each with a role and optional
filters:

| Role | May run |
|---|---|
| `viewer` | Read tools only |
| `operator` | Read and write tools |
| `admin` | Read, write and destructive tools |
| `fleet-admin` | Everything, including the registry and token tools |

A token can also carry:

| Filter | Effect |
|---|---|
| `allow_modules` | Only tools from matching tool modules are reachable |
| `deny_modules` | Tools from matching modules are refused |
| `controller_labels` | Only controllers carrying every listed label are reachable |

A call to a controller outside the caller's label scope is **refused with a
permission error**, and the refusal is audited. A caller cannot reach a
controller it was not scoped for by naming it.

## Managing the registry

These are `fleet-admin` tools, and they change the registry rather than a
controller.

| Tool | Does |
|---|---|
| `register_controller` | Register a controller with its credentials |
| `update_controller` | Change a controller's settings or labels |
| `register_cloud_account` | Register a cloud account for the fleet |
| `rotate_fleet_credentials` | Replace a controller's stored credentials |
| `list_api_tokens` | List the issued tokens |
| `create_api_token` | Issue a token with a role and filters |
| `revoke_api_token` | Revoke an issued token |
| `update_api_token_role` | Change an issued token's role or filters |
| `export_audit_log` | Export the audit records |
| `search_audit_log` | Search the audit records |
| `verify_audit_chain` | Verify the audit hash chain |

Registering a controller stores its credentials **encrypted**, keyed by
`UNIFI_CREDENTIAL_KEY`. The server refuses to start without that key when
`DATABASE_URL` is set. Changing the key makes every stored credential
unreadable, so treat it as a rotation that requires re-entering the
credentials.

**Never pass a controller's API key in a prompt, a report or a log line.**
The registry tools take the credential as an argument; that is the only
place it belongs.

## Failures

| Symptom | Cause | What to do |
|---|---|---|
| A `fleet_*` tool is missing | `DATABASE_URL` is not set | Fleet mode is off; the server is a single controller |
| `select_controller` is refused | Stateless HTTP mode | Pass `controller` on every call |
| A controller is unreachable | The console is down or the network path is wrong | `fleet_health` shows the state; check from the server host |
| A snapshot is stale | The worker has not checked recently | Check the worker's health; `fleet_fanout` gives a live answer |
| Permission denied on a controller | The caller's labels do not match | The scope is working as configured |
| Credentials fail to decrypt | `UNIFI_CREDENTIAL_KEY` changed | Re-enter the credentials for that controller |
| A fan-out is refused | The tool is write-tier, or is itself a fleet tool | Use a read tool; `fleet_fanout` cannot fan out over itself |

## Safety

- A `fleet_fanout` runs on many controllers at once. A wrong argument is a
  wrong argument on every controller in the list.
- Changing or rotating a controller's credentials is not reversible by
  putting the old one back, and it cuts every client off that controller
  until they re-authenticate.
- Revoking a token cuts off every client using it, including one you are
  talking to.
- Prefer `fleet_health` and the snapshot tools for inspection. Reserve
  `fleet_fanout` for the questions the snapshots cannot answer.
- Read [unifi-safe-changes](unifi-safe-changes/SKILL.md) before making any
  change through this surface.
