# METRICS

Operator runbook for the Prometheus metrics surface.

## Purpose

Make the UniFi MCP Server observable as a production service so operators can measure usage, spot regressions, and alert on unhealthy controllers or tool behavior.

## Metrics goals

The metrics surface should answer these questions:

- Are tools being called normally?
- Which tools are slow or error-prone?
- Is the controller healthy?
- Are we caching effectively?
- Is the server under abnormal load?

## Planned metric families

- tool call counts
- tool execution duration
- API error totals
- cache hit and miss totals
- active session gauge
- controller health gauge

## Recommended exposure model

- expose a dedicated `/metrics` endpoint when metrics are enabled
- keep the endpoint read-only
- bind only to the intended interface
- protect it with network controls if it is reachable beyond localhost

## Baseline rollout procedure

1. Enable metrics in a non-production environment first.
2. Confirm the endpoint is reachable from the scrape target.
3. Verify labels are stable and low-cardinality.
4. Add dashboard panels for latency, errors, and traffic volume.
5. Add alert rules before enabling production-wide rollout.

## Operational checks

### Tool call health

Track:

- total calls per tool
- error rate per tool
- p95 or p99 execution duration
- changes in call volume after a deployment

### Cache behavior

Track:

- cache hits
- cache misses
- cache invalidations
- stale-read incidents if supported by the implementation

### Controller health

Track:

- controller reachability
- controller response latency
- controller authentication failures
- per-controller error spikes

## Dashboard guidance

A practical dashboard should include:

- overall request volume
- top slow tools
- top erroring tools
- controller health by site or instance
- cache effectiveness over time
- active session count

## Alerting guidance

Alert when:

- tool error rate spikes above the normal baseline
- controller health remains degraded beyond a short grace period
- latency increases sharply after a deployment
- metrics endpoint becomes unreachable

## Verification checklist

- Metrics endpoint responds with Prometheus text format.
- Scrape target can reach the endpoint.
- Tool labels are stable and predictable.
- Grafana panels render the expected series.
- Alerts trigger in a controlled test.

## Common failure modes

- metrics endpoint disabled in the wrong environment
- unstable labels that explode cardinality
- scrape access blocked by network policy
- dashboards built before metric names are finalized
- alerting tuned so tightly it pages on normal load

## Status

Phase-5 documentation.