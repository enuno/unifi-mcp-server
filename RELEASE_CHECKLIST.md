# Release Checklist — UniFi MCP Server

## Operator release runbook

### Objective

Release only after the code, docs, tests, and operational guidance all agree.

### Prerequisites

- You know the target version and the release scope.
- CI is green or the blocking failure is understood and fixed.
- The current phase documentation is up to date.

### Procedure

1. Validate tests, lint, type checks, security scan, and docs sync.
2. Confirm the changelog and version metadata are aligned.
3. Verify the roadmap, development plan, and runbooks describe the same phase state.
4. Check that any new endpoints or behaviors have schema and integration coverage.
5. Confirm the post-release publication path before pushing the tag.

### Verification

- Every required gate is checked.
- The release notes describe only shipped behavior.
- The operational docs exist for every user-visible phase addition.

### Rollback

- If a gate fails, stop the release, fix the failure, and rerun the checklist from the start.

### Common failure modes

- Tagging before the docs and tests are synchronized.
- Missing a new runbook for a new operator-facing surface.
- Publishing release notes that describe future work as complete.

## Pre-release

- [ ] All CI gates pass: tests, lint, type check, security scan, docs sync.
- [ ] `CHANGELOG.md` updated with user-facing changes.
- [ ] Version bumped consistently in packaging and release metadata.
- [ ] `DEVELOPMENT_PLAN.md` and `ROADMAP.md` reflect the current phase.

## Coverage validation

- [ ] Coverage matrix regenerated when endpoint coverage changes.
- [ ] All implemented read-only endpoints have tests.
- [ ] All write endpoints have unit and integration coverage where practical.
- [ ] New Protect and Access endpoints have schema fixtures.

## Safety review

- [ ] No secrets in diff.
- [ ] Bandit passes.
- [ ] Safety passes.
- [ ] Dry-run and RBAC gates verified for write/destructive paths.
- [ ] Audit logging verified for mutation paths.

## Documentation

- [ ] `README.md` updated.
- [ ] `SPEC.md` updated.
- [ ] `API.md` updated.
- [ ] `docs/UNIFI_API.md` updated.
- [ ] New phase docs created or refreshed.

## Post-release

- [ ] Git tag pushed.
- [ ] PyPI publish successful.
- [ ] Release notes published.
- [ ] Operational docs for the new phase are available to contributors.
