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

## Status

Phase-5 documentation.