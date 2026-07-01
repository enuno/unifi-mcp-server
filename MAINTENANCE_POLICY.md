# Maintenance Policy — UniFi MCP Server

## Operator maintenance runbook

### Objective

Keep the docs, dependencies, and operational guidance synchronized with the live server surface.

### Prerequisites

- You can identify the current stable release and active phase.
- You know which docs are canonical: `SPEC.md`, `DEVELOPMENT_PLAN.md`, `ROADMAP.md`, `API.md`, `docs/UNIFI_API.md`, and the phase runbooks.

### Procedure

1. Review upstream UniFi documentation on the stated cadence.
2. Reconcile any drift against the implementation and update the affected docs together.
3. Apply dependency changes with explicit review when auth, transport, or logging are involved.
4. Keep controller registry, profile registry, metrics, audit, and webhook contracts documented as versioned surface area.
5. Confirm the repo docs still match the release flow after each release.

### Verification

- The affected docs were updated in one change set.
- No maintenance note describes unsupported behavior as live.
- Docs and implementation still agree on the current surface.

### Rollback

- If a maintenance update introduces drift, revert the doc claim first and then restate the supported behavior.

### Common failure modes

- Updating one doc and leaving its sibling docs stale.
- Treating a new contract as stable before it is reflected in tests and release notes.
- Allowing silent behavior changes in write paths.

## Upstream tracking

1. Weekly: compare committed API and spec snapshots against the latest UniFi documentation.
2. On drift: open or update a tracking issue and schedule the impacted phase.
3. After major UniFi releases: re-check Protect, Access, and Site Manager endpoint assumptions.

## Documentation synchronization

When the implementation surface changes, update all relevant docs in the same change set:

- `SPEC.md`
- `DEVELOPMENT_PLAN.md`
- `ROADMAP.md`
- `API.md`
- `docs/UNIFI_API.md`
- `README.md`
- `GAP_REPORT.md`
- `TEST_STRATEGY.md`
- `RELEASE_CHECKLIST.md`
- `CHANGELOG.md`

## Dependency updates

1. Security patches are applied quickly.
2. Major upgrades are reviewed before adoption.
3. Any dependency that affects auth, transport, or logging gets explicit review.

## Operational maintenance

- Keep controller registry and profile registry documentation current.
- Treat new audit, metrics, and webhook contracts as versioned surface area.
- Avoid silent behavior changes in write paths.
- Preserve backward compatibility unless a phase explicitly requires a break.

## Review cadence

- Monthly: validate roadmap progress and outstanding gaps.
- Quarterly: review whether the spec still matches the actual tool surface.
- After each release: confirm docs, tests, and operational guidance are aligned.
