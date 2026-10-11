# unifi-mcp Helm chart

Runs the UniFi MCP server on Kubernetes over Streamable HTTP with a bearer
token. It can run the server alone, or in fleet mode with workers, the
Postgres controller registry and audit store, and an optional Redis. The
chart creates no database or cache. It takes their URLs from a Secret you
provide, so you can use managed services or your own operators (CloudNativePG,
a Redis operator) for high availability.

## Install

1. Create the Secret. The chart never templates secret values: every key in
   this Secret becomes an environment variable of the server.

   ```bash
   kubectl create namespace unifi-mcp
   kubectl -n unifi-mcp create secret generic unifi-mcp \
     --from-literal=UNIFI_API_KEY='<controller API key>' \
     --from-literal=MCP_AUTH_TOKEN="$(openssl rand -hex 32)" \
     --from-literal=UNIFI_AUDIT_CHAIN_KEY="$(openssl rand -hex 32)"
   ```

   For fleet mode, also add:

   | Key | What |
   | --- | --- |
   | `DATABASE_URL` | Postgres as the least-privilege role (SECURITY.md has the grants) |
   | `MIGRATION_DATABASE_URL` | Postgres as the schema owner, for migrations and retention |
   | `UNIFI_FLEET_CREDENTIAL_KEY` | Fernet key encrypting stored controller keys; back it up |
   | `REDIS_URL` | Optional: shares rate limits, registry changes and worker leases across pods |

   Optional keys: `UNIFI_AUDIT_LOG_KEY`, `UNIFI_AUDIT_SIEM_WEBHOOK_SECRET`,
   `UNIFI_AUDIT_SIEM_OTLP_HEADERS`. External Secrets or Sealed Secrets can
   produce the same Secret.

2. Install:

   ```bash
   helm install unifi-mcp deploy/helm/unifi-mcp -n unifi-mcp \
     --set existingSecret=unifi-mcp \
     --set controller.localHost=192.168.1.1
   ```

   Fleet mode, three replicas, two workers, a year of audit records:

   ```bash
   helm install unifi-mcp deploy/helm/unifi-mcp -n unifi-mcp \
     --set existingSecret=unifi-mcp --set controller.localHost=192.168.1.1 \
     --set fleet.enabled=true --set server.replicas=3 \
     --set fleet.workers.replicas=2 --set audit.retentionDays=365
   ```

3. Check:

   ```bash
   kubectl -n unifi-mcp port-forward svc/unifi-mcp 3000:3000
   curl -fsS http://127.0.0.1:3000/healthz       # {"status":"ok"}, no token
   ```

   MCP clients connect to `http(s)://<host>/mcp` with
   `Authorization: Bearer <MCP_AUTH_TOKEN>`.

## What it creates

- **Server Deployment.** Runs as uid 1000 with a read-only root filesystem,
  every capability dropped, and no service account token. The startup,
  liveness and readiness probes use `GET /healthz`, which needs no token
  and reveals nothing. A change to the non-secret settings restarts the
  pods. After changing the Secret, run `kubectl rollout restart`.
- **Worker Deployment** (fleet). Runs `python -m src.worker` for health
  checks and snapshots. Without `REDIS_URL`, keep one worker.
- **Migration Job** (fleet). A pre-install and pre-upgrade hook that runs
  `python -m src.fleet.cli migrate`. The servers refuse to start on an old
  schema.
- **Retention CronJob** (fleet, with `audit.retentionDays`). Archives
  expired audit records to a PersistentVolumeClaim, then deletes them. Only
  one run happens at a time.
- **Service, plus optional Ingress, ServiceMonitor, PodDisruptionBudget and
  NetworkPolicy.** The ServiceMonitor reads the bearer token for
  `/metrics` from the Secret.

## Several replicas

An MCP session lives in one pod's memory (MULTI_CONTROLLER.md). You have
three ways to handle that:

- Keep each client on one pod. With more than one replica the Service sets
  `sessionAffinity: ClientIP`. Behind ingress-nginx, hash on the client and
  its token:

  ```yaml
  ingress:
    enabled: true
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/upstream-hash-by: "$remote_addr$http_authorization"
      nginx.ingress.kubernetes.io/proxy-buffering: "off"
      nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
  ```

- Set `server.statelessHttp=true`. Any pod then answers any request, and
  calls name their controller with `controller=<name>`.
- Run one replica.

## The audit log

In fleet mode audit records go to Postgres, and the pod's log volume
(an emptyDir) holds only the SIEM buffer. Without fleet, the JSON-lines
file is the only copy. Set `persistence.enabled` to keep it on a volume
(one replica), or set `audit.siemTargets` to copy every record off the pod.
Rotation (`audit.rotateMb`) applies to the file either way.

## Values

See `values.yaml`. Any non-secret setting from [API.md](../../../API.md) goes
in `server.extraEnv`. The chart refuses to put a secret there.

## Image

The default image is `ghcr.io/enuno/unifi-mcp-server:<appVersion>`. With
`fleet.enabled` it is `...:<appVersion>-fleet`, the image built with the
Redis and Postgres extras that the release workflow publishes. To build
your own, run `docker build --build-arg EXTRAS=fleet .` and set
`image.repository` and `image.tag`.

## Tests

CI lints and renders the chart with each file in `ci/`, validates the
output with kubeconform, and runs `scripts/helm_smoke_test.sh` on a kind
cluster. That test installs the chart in fleet mode against a throwaway
Postgres, checks `/healthz`, checks that `/mcp` refuses requests without a
token and answers with one, and runs the retention job once.
