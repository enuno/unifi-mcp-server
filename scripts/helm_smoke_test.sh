#!/usr/bin/env bash
# Smoke test for deploy/helm/unifi-mcp on a kind cluster (CI's helm job).
#
#   scripts/helm_smoke_test.sh IMAGE KIND_CLUSTER
#
# Loads IMAGE (built with EXTRAS=fleet) into the cluster, runs a throwaway
# Postgres, installs the chart in fleet mode, and checks that /healthz
# answers without a token, /mcp refuses a request without one and answers
# `initialize` with one, and the retention job completes. Never point this
# at a real cluster: it creates and deletes the unifi-mcp-smoke namespace.
set -euo pipefail

image="$1"
cluster="$2"
ns=unifi-mcp-smoke
release=smoke
chart="$(dirname "$0")/../deploy/helm/unifi-mcp"

dump() {
  echo "--- diagnostics"
  kubectl -n "$ns" get all,pvc,jobs || true
  kubectl -n "$ns" describe pods || true
  for pod in $(kubectl -n "$ns" get pods -o name); do
    echo "--- logs $pod"
    kubectl -n "$ns" logs "$pod" --all-containers --tail=100 || true
  done
}
forward=""
finish() {
  local status=$?
  [ "$status" -eq 0 ] || dump
  [ -z "$forward" ] || kill "$forward" 2>/dev/null || true
  exit "$status"
}
trap finish EXIT

kind load docker-image "$image" --name "$cluster"
kubectl create namespace "$ns"

# A throwaway Postgres (the chart takes database URLs from its Secret).
pg_password="$(openssl rand -hex 16)"
kubectl -n "$ns" create secret generic postgres --from-literal=POSTGRES_PASSWORD="$pg_password"
kubectl -n "$ns" apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  selector:
    matchLabels: {app: postgres}
  template:
    metadata:
      labels: {app: postgres}
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          env:
            - {name: POSTGRES_DB, value: unifi_mcp}
            - {name: POSTGRES_USER, value: unifi_mcp}
          envFrom:
            - secretRef: {name: postgres}
          ports:
            - containerPort: 5432
          readinessProbe:
            exec:
              command: [pg_isready, -U, unifi_mcp, -d, unifi_mcp]
            periodSeconds: 2
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  selector: {app: postgres}
  ports:
    - port: 5432
EOF
kubectl -n "$ns" rollout status deployment/postgres --timeout=180s

token="$(openssl rand -hex 32)"
api_key="smoke-test-not-a-real-key"  # pragma: allowlist secret
url="postgresql://unifi_mcp:${pg_password}@postgres:5432/unifi_mcp"
kubectl -n "$ns" create secret generic unifi-mcp \
  --from-literal=UNIFI_API_KEY="$api_key" \
  --from-literal=MCP_AUTH_TOKEN="$token" \
  --from-literal=UNIFI_AUDIT_CHAIN_KEY="$(openssl rand -hex 32)" \
  --from-literal=UNIFI_FLEET_CREDENTIAL_KEY="$(openssl rand 32 | base64 | tr '+/' '-_')" \
  --from-literal=DATABASE_URL="$url" \
  --from-literal=MIGRATION_DATABASE_URL="$url"

# No --wait: the archive claim binds only when the retention job first runs
# (WaitForFirstConsumer), so wait on the Deployments instead. The migration
# hook still runs, and must succeed, before install returns.
helm install "$release" "$chart" --namespace "$ns" --timeout 5m \
  --set image.repository="${image%:*}" --set image.tag="${image##*:}" \
  --set image.pullPolicy=Never \
  --set existingSecret=unifi-mcp \
  --set controller.apiType=cloud-ea \
  --set server.replicas=2 \
  --set fleet.enabled=true \
  --set audit.retentionDays=30
kubectl -n "$ns" rollout status "deployment/${release}-unifi-mcp" --timeout=300s

kubectl -n "$ns" port-forward "svc/${release}-unifi-mcp" 3000:3000 >/dev/null &
forward=$!
for _ in $(seq 30); do curl -fsS http://127.0.0.1:3000/healthz >/dev/null 2>&1 && break; sleep 1; done

echo "--- /healthz without a token"
test "$(curl -fsS http://127.0.0.1:3000/healthz)" = '{"status":"ok"}'

init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
headers=(-H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')

echo "--- /mcp without a token is refused"
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:3000/mcp "${headers[@]}" -d "$init")"
test "$code" = 401

echo "--- /mcp initialize with the token"
curl -fsS -X POST http://127.0.0.1:3000/mcp "${headers[@]}" \
  -H "Authorization: Bearer $token" -d "$init" | grep -q serverInfo

echo "--- the worker is running"
kubectl -n "$ns" rollout status "deployment/${release}-unifi-mcp-worker" --timeout=60s

echo "--- one audit retention run"
kubectl -n "$ns" create job retention-now --from="cronjob/${release}-unifi-mcp-audit-retention"
kubectl -n "$ns" wait --for=condition=complete job/retention-now --timeout=180s
kubectl -n "$ns" logs job/retention-now
test "$(kubectl -n "$ns" get pvc "${release}-unifi-mcp-archive" -o jsonpath='{.status.phase}')" = Bound

echo "smoke test passed"
