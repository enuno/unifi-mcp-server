# Test Strategy — UniFi MCP Server

## Operator test runbook

### Objective

Validate the server surface in the same order operators will depend on it: core behavior, integration boundaries, safety gates, and observability.

### Prerequisites

- You know which phase or feature area changed.
- You know whether the change affects reads, writes, controller routing, or platform contracts.
- You have any required fixtures or controller recordings available.

### Procedure

1. Run unit tests for the touched tool or helper modules.
2. Run integration tests for the affected domain.
3. Validate schema and contract coverage for new endpoint families.
4. Run safety tests for dry-run, RBAC, and audit behavior if writes changed.
5. Run observability tests if metrics or webhooks changed.
6. Finish with the CI gate sequence used in the repo.

### Verification

- The test set covers the changed surface, not just adjacent helpers.
- Safety gates fail closed.
- Metrics and eventing assertions match the operator contract.

### Rollback

- If a test category fails, narrow the change set and rerun from the highest-risk layer down.

### Common failure modes

- Passing unit tests while integration or contract tests still fail.
- Skipping safety assertions on write-path changes.
- Leaving schema fixtures out of new endpoint coverage.

## 1. Unit tests

- Every tool function should have a unit test in `tests/unit/tools/test_<module>_tools.py`.
- Mock UniFi client responses with `pytest-mock`, `respx`, or equivalent HTTP fakes.
- Protect, orchestration, RBAC, audit, metrics, and webhook helpers need dedicated unit coverage.
- Target coverage: 85%+ overall, with write-path coverage preferred over simple read-path coverage.

## 2. Integration tests

- Maintain `tests/integration/test_<domain>_suite.py` per domain.
- Use real UniFi controller fixtures only where live validation is essential.
- Protect integration tests should use mocked or recorded NVR responses until the native client is stable.
- Multi-controller tests must verify active-controller isolation and fan-out behavior.

## 3. Contract and schema validation

- Record JSON response samples for every new endpoint family.
- Validate response structure against Pydantic models.
- For Protect and Access, validate against upstream OpenAPI specs where available.
- Add regression fixtures for any endpoint drift or schema breakage.

## 4. Safety tests

- All write tools must fail or preview without the required change-safe gate.
- Dry-run output must contain the target, method, and payload preview.
- RBAC tests must confirm tool denial by scope.
- Audit log assertions must verify every mutation is recorded.

## 5. Observability tests

- Metrics counters and histograms must increment on tool execution.
- Controller reachability gauges must reflect health-check results.
- Webhook event normalization must preserve source, event type, and site metadata.

## 6. CI gates

- `pytest --cov=src --cov-fail-under=85`
- `ruff check src/`
- `mypy src/`
- `bandit -r src/`
- `safety check`
- optional docs sync validation for `API.md`, `docs/UNIFI_API.md`, and `README.md`
