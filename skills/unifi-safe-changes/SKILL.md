---
name: unifi-safe-changes
description: >
  Change UniFi state through the MCP server without losing the network, the
  audit trail or the operator's trust. Use when creating, updating or
  deleting anything, when a call is refused, when deciding whether a
  change is safe to make unattended, or when a change must be rolled back.
---

# Safe State Changes

Every write the server exposes is gated. This skill explains what each gate
does, which of them is enforced in code and which is a convention, and how
to make a change you can undo.

## The four gates

They are independent. A change passes all four or it does not happen.

| Gate | Where | Enforced by |
|---|---|---|
| Role | The caller's token role must grant the tool's tier | `src/access.py`, checked in the tool wrapper |
| `confirm=True` | The caller must pass it explicitly | The tool wrapper, for every tool that takes a `confirm` parameter |
| `dry_run=True` | The caller can ask for a preview | The tool wrapper, for every tool that takes a `dry_run` parameter |
| Server mode | `UNIFI_READ_ONLY` and `UNIFI_DRY_RUN` narrow what runs | The tool registry, at registration |

Only the first three are **runtime** controls. They are enforced in code
and a missing gate is a bug, not a style problem.

## `confirm` is enforced, not advisory

Every mutating tool takes a `confirm` parameter and the wrapper refuses the
call without it. The refusal is an error, not a warning, and it is written
to the audit log as `denied`.

```python
# Refused: the call raises and nothing changes
await client.call_tool("create_firewall_zone", {"site_id": "default", "name": "IoT"})

# Accepted
await client.call_tool(
    "create_firewall_zone",
    {"site_id": "default", "name": "IoT", "confirm": True},
)
```

A tool without a `confirm` parameter is a read tool. The server's own
registry decides which is which (`@read_tool` / `@write_tool` in
`src/utils/tool_kind.py`); the tier is what your role is checked against.

## `dry_run` is a real preview

`dry_run=True` returns what the change would do without doing it. It is
the correct first step for any change you have not performed before.

```python
preview = await client.call_tool(
    "create_firewall_zone",
    {"site_id": "default", "name": "IoT", "confirm": True, "dry_run": True},
)
```

A dry run proves the request shape and the server's validation. It does
**not** prove the change is safe, and it does not prove the controller
will accept it.

## Server modes narrow further

| Setting | Effect |
|---|---|
| `UNIFI_READ_ONLY=true` | No mutating tool is registered at all. A write tool is *absent*, so it cannot be called even by an admin. |
| `UNIFI_DRY_RUN=true` | Every write is forced into a preview. `dry_run` cannot be turned off by the caller. |

Both are deployment decisions, not per-call ones. A read-only deployment
is the safe default for a shared server.

## The workflow for a change

1. **Read the current state.** Use the read tools for the objects you are
   about to change. A change built on a guess is a change you cannot undo
   cleanly.
2. **Preview.** Call with `confirm=True, dry_run=True`. Read the preview
   and check it against what you expected.
3. **Apply.** Call with `confirm=True` and no `dry_run`.
4. **Verify.** Read the object back. For a network change, check that
   clients are still connected and that the expected behaviour changed.
5. **Record.** The audit log already has the attempt and the outcome.

## What can break the network

These are the changes where a mistake isolates someone. Treat them as
high-risk regardless of how small the edit looks.

| Change | What breaks | Reduce the risk |
|---|---|---|
| Disabling a LAN on the port you are connected through | You lose the session | Change it from the console UI, or from a different network path |
| Editing the WAN configuration | The site loses internet | Preview it; check the addresses in the preview |
| Removing a zone or a network from a zone | Devices in that zone lose their policy | Read the zone matrix first; check which devices are in the zone |
| Changing a VLAN's subnet | Every device on that VLAN loses its address | Read the DHCP reservations and the static leases first |
| Renaming or deleting an SSID | Clients on that SSID disconnect | Read the client list for the SSID first |
| Overwriting a firewall policy | Traffic starts flowing that should not | Read the current policy first; the update is a full-object PUT |
| Restarting a gateway or a switch | Everything behind it drops | Check what is behind it |

A full-object PUT is the trap in the list above. Several tools replace the
whole object rather than merging fields, so a partial argument set can
erase settings you did not mention. Read the object, change the field,
send the whole object back.

## Rolling back

The server has no undo. Rollback means running the inverse change, so you
need the previous value.

- **Read the current value before you change it.** That read is your undo.
- **Prefer a change you can invert** over one you cannot. Adding a rule is
  invertible; deleting one is not, unless you saved it.
- **A backup is not an undo.** `list_backups` shows what the controller
  saved; restoring one is a large, disruptive operation of its own, and
  the skill for backups says when it is appropriate.
- **For a policy edit**, the inverse is the policy as it was. Keep the
  read output.

## The audit trail

Every mutating call, every refusal and — with `UNIFI_AUDIT_READS=true` —
every read is recorded. The record carries the principal, the tool, the
tier, the controller, the redacted arguments and the outcome. The tool's
response is never recorded.

Read the trail when you need to know what happened:

```bash
# The A2A audit route lists delegated calls
curl -s -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  http://127.0.0.1:3000/a2a/audit
```

The route needs the `admin` role; a `viewer` or `operator` token is
refused with `403`.

## Failure modes

| Symptom | Cause | What to do |
|---|---|---|
| "requires confirm=True" | The gate worked | Add `confirm=True` deliberately, after reading the current state |
| "requires confirmation" from a delegated call | The A2A safety layer held a destructive call | Approve it through `/a2a/confirm`, or do not |
| The write tool is missing | `UNIFI_READ_ONLY=true` | The tool is not registered; there is nothing to call |
| The write returned a preview | `UNIFI_DRY_RUN=true` | Read the preview; nothing changed |
| Permission denied | The role does not grant the tier | `admin` for destructive, `operator` for write |
| The change applied but nothing happened | Wrong site or controller | Read the object back on the right scope |
| A client disconnected | Expected for some changes | Verify with `list_active_clients` before changing anything else |

## Rules

- Never make a change you cannot describe the inverse of.
- Never make a change from a value you have not read.
- Always preview a change you have not made before.
- Never pass `confirm=True` reflexively. It is the last step, not the
  first.
- Never report a change as done until you have read the object back.
