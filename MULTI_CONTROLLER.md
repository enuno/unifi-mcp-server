# MULTI_CONTROLLER

Operator runbook for multi-controller configuration and fleet routing.

## Purpose

Describe how a single MCP server instance should safely manage more than one UniFi controller without leaking controller context across sessions or requests.

## Core concepts

- named controller registry
- explicit default controller
- per-session active controller context
- fan-out read operations for fleet views
- controller comparison and drift review
- strict separation between read and write paths

## When to use this runbook

- you are adding a second or third controller to an existing deployment
- you need operators to switch controllers within a session
- you need fleet-wide read queries across controllers
- you need to compare configuration drift between sites or tenants

## Required inputs

- controller name, host, and site mapping
- API credentials or scoped access method for each controller
- routing policy for default controller selection
- approval boundary for write actions

## Configuration model

A safe registry should expose:

- a human-readable controller name
- endpoint information for each controller
- site or tenant identifiers
- credential reference, not plaintext secrets
- optional labels for environment, region, or business unit

Use environment variables or a dedicated YAML file, but keep secrets out of version control.

## Operational procedure

### 1. Register controllers

1. Define each controller entry with a unique name.
2. Confirm host, port, and site references are correct.
3. Store credentials in the approved secret store.
4. Set one controller as the default only if the deployment needs a default.

### 2. Verify session scoping

1. Open two independent sessions.
2. Select different controllers in each session.
3. Run read-only queries in both sessions.
4. Confirm the selected controller does not bleed across sessions.

### 3. Validate fan-out reads

1. Run a fleet query against the controller registry.
2. Confirm the query returns one result set per controller or one normalized merged result.
3. Confirm no write operation is triggered during fleet reads.

### 4. Review drift

1. Compare the same object class across controllers.
2. Look for mismatches in sites, VLANs, firewall rules, credentials, or device inventory.
3. Record intentional differences separately from accidental drift.

## Verification checklist

- Each controller can be reached independently.
- Default controller selection is explicit.
- Session-scoped controller selection does not leak.
- Read fan-out returns the intended fleet view.
- Write paths remain tied to one explicit controller target.
- Audit records show the active controller for each request.

## Rollback

If a controller registry change causes ambiguity or cross-target confusion:

- disable the new controller entry
- revert to the previous registry
- clear any session state associated with the bad mapping
- re-run isolation tests before re-enabling

## Common failure modes

- incorrect host or site mapping
- credential reuse across the wrong controller
- accidental cross-controller write when a controller selector is omitted
- stale session state after a controller swap
- controller-specific feature mismatches that need feature gating

## Operator notes

- Make the active controller visible in logs and audit entries.
- Prefer read-only fleet operations unless the action is explicitly targeted.
- Keep any comparison or diff output clearly labeled by controller.
- Re-run isolation checks after controller registry edits.

## Running several replicas

A stateful Streamable HTTP session exists only in the memory of the replica
that created it; any other replica answers `404 Session not found`. Choose one:

- **Sticky routing (recommended).** Send all of one client's requests to the
  same replica, using a key the client already has when it sends `initialize`.
  `select_controller` then works as on one server. If that replica dies, the
  client starts a new session and selects again. Do not hash on the
  `mcp-session-id` header alone: `initialize` carries none, and the next
  request (carrying the id the replica just issued) can hash to a different
  replica, which answers `404`. With nginx, hash on the client address and its
  bearer token:

  ```nginx
  upstream unifi_mcp {
      hash $remote_addr$http_authorization consistent;
      server mcp-1:3000;
      server mcp-2:3000;
      server mcp-3:3000;
  }
  ```

  Behind another proxy, use the original client address (e.g.
  `$http_x_forwarded_for` from a trusted proxy) instead of `$remote_addr`. A
  load-balancer cookie works too, if every client keeps cookies.

- **Stateless (`MCP_STATELESS_HTTP=true`).** No sessions, so any replica can
  answer any request and no affinity is needed. `select_controller` is refused;
  pass `controller=<name>` to each call (or rely on the registry default for
  reads).

With Redis configured (`REDIS_URL`), replicas also share each controller's
rate limit (one budget per controller, one per API key for api.ui.com) and
reload the controller registry as soon as any replica changes it.

If Redis goes down, nothing stops: reads bypass the cache, registry changes
reach other replicas at their next periodic refresh, and each replica falls
back to a local rate limit of `UNIFI_RATE_LIMIT_REQUESTS /
UNIFI_FLEET_EXPECTED_REPLICAS` (set it to your replica count plus workers;
`docker-compose.fleet-scale.yml` sets 5). Workers pause
until Redis is back, since none can know its share of the fleet without it.
If Postgres goes down, replicas keep routing with their last registry
snapshot, reads keep working, writes are refused (their audit record cannot
be stored), the `fleet_*` snapshot tools fail with an error, and issued tokens
are refused; `MCP_AUTH_TOKEN` keeps working.

## Fleet workers

`python -m src.worker` (same image, different command) keeps a snapshot of
the fleet in Postgres, so the snapshot tools below answer without the API
replicas polling every controller (other tools, and `fleet_fanout`, still
call controllers live):

- **Health** every `UNIFI_FLEET_WORKER_HEALTH_SECONDS` (60): the same
  authentication probe tools use, plus the Network application version on
  local controllers. Stored on `controllers` as `health` (`ok`; `degraded`
  after a failure; `down` after `UNIFI_FLEET_WORKER_DOWN_AFTER` in a row),
  `health_detail`, `last_seen_at` and `capabilities`.
- **Sites and devices** every `UNIFI_FLEET_WORKER_SYNC_SECONDS` (900): the
  `sites` table for every controller, and `device_inventory` per site for
  local controllers (the cloud APIs list devices per host, not per site).
  Each sync replaces the previous snapshot; a failed sync leaves it as it was.

With Redis configured, run as many workers as needed: they split the
controllers by rendezvous hashing and hold a lease on each, so a dead worker's
controllers move to the others within `UNIFI_FLEET_WORKER_LEASE_SECONDS` (30)
and a stopped one hands them over at once. Without Redis, run exactly one.
First runs are spread over each interval by a hash of the controller name and
later ones jittered by ±10%, so a large fleet is not polled all at once.

## Fleet-wide questions

- `fleet_health`, `fleet_sites` and `fleet_inventory` answer from the worker's
  snapshots: "which controllers are down", "which gateways run firmware older
  than 4.1" across a thousand controllers is one database query and no
  controller calls. Each entry says how old it is.
- `fleet_fanout` runs any read tool live on many controllers (bounded
  concurrency, a per-controller timeout and an overall deadline) and returns
  one result per controller, so a few unreachable ones never fail the call.

All four see only the controllers in the caller's `controller_labels` scope;
API.md has the parameters.

## Example deployment

`docker-compose.fleet-scale.yml`, layered on `docker-compose.fleet.yml`, runs
Redis, three replicas behind nginx (sticky on client address and token) and two
workers:

```bash
docker compose -f docker-compose.fleet.yml -f docker-compose.fleet-scale.yml up -d
```

`make verify-fleet-scale` runs the same topology as local processes (Postgres
from pgserver, an in-process Redis, a mock controller fleet) and checks the
worker split and failover, registry pub/sub, the shared rate limit, fan-out
partial results and the snapshot tools.

## Status

Phase-5 documentation.
