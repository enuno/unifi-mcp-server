# Deploying with Ansible

This playbook installs Docker and runs the UniFi MCP server as containers,
from one host up to a small cluster. It deploys the same services as
`docker-compose.fleet.yml`, adds nginx for several hosts, and sets up the
least-privilege database role and the audit retention job that
[SECURITY.md](../../SECURITY.md) describes.

| Layout | Inventory | What runs |
| --- | --- | --- |
| MCP server only | `inventories/single`, with the `redis` and `postgres` groups deleted | The server on one host, its audit log in a file, the controller from `UNIFI_*` settings |
| Single-server fleet | `inventories/single` | The server, a worker, Redis and Postgres on one host |
| Cluster | `inventories/cluster` | Replicas and workers on each `mcp` host, Redis and Postgres on a data host, nginx on `lb` |

Every layout serves Streamable HTTP with a bearer token (`MCP_AUTH_TOKEN`).
To have an AI agent run all of this for you, start from a prompt in
[docs/deploy-prompts/](../../docs/deploy-prompts/README.md).

## Requirements

- On the machine you run Ansible from: `ansible-core` 2.15 or later, then
  `ansible-galaxy collection install -r requirements.yml -p ./collections`.
- Target hosts: Debian 12, Ubuntu 22.04/24.04, or RHEL/Rocky/Alma 9, with SSH
  access and sudo. The `docker` role installs Docker CE.
- Network access from the `mcp` hosts to the UniFi controller, and an API key
  created on it (Settings → Control Plane → Integrations).

## Steps

1. Choose an inventory and edit `hosts.yml` (addresses) and
   `group_vars/all/main.yml` (controller, replicas, ports).
2. Create the secrets:

   ```bash
   cd deploy/ansible
   cp inventories/single/group_vars/all/vault.yml.example \
      inventories/single/group_vars/all/vault.yml
   # fill it in (the file says how to generate each value), then:
   ansible-vault encrypt inventories/single/group_vars/all/vault.yml
   ```

   `vault.yml` is in `.gitignore`. Without Postgres only
   `vault_unifi_api_key`, `vault_mcp_auth_token` and `vault_audit_chain_key`
   are needed.
3. Check, then run:

   ```bash
   ansible-playbook -i inventories/single/hosts.yml site.yml --syntax-check
   ansible-playbook -i inventories/single/hosts.yml site.yml --check --diff --ask-vault-pass
   ansible-playbook -i inventories/single/hosts.yml site.yml --ask-vault-pass
   ```

4. Verify (from an `mcp` host, or through nginx for the cluster):

   ```bash
   curl -fsS http://127.0.0.1:3000/healthz          # {"status":"ok"}, no token
   curl -fsS -X POST http://127.0.0.1:3000/mcp \
     -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
     -H 'Content-Type: application/json' \
     -H 'Accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
   ```

   A `401` means the token is wrong. The second call returning a
   `serverInfo` shows the server is up and answering MCP.

Running the playbook again is safe: it changes only what differs. Change
`unifi_mcp_replicas` or `unifi_mcp_workers` and rerun to scale; containers
past the new count are removed.

## What it sets up

- **Image.** Built on each `mcp` host from `unifi_mcp_repo` at
  `unifi_mcp_version` with the `fleet` extras, which the base published image
  does not include. Set `unifi_mcp_image` to use a prebuilt image instead,
  such as the `ghcr.io/enuno/unifi-mcp-server:<version>-fleet` image a
  release publishes.
- **Migrations.** With Postgres, the first `mcp` host runs
  `python -m src.fleet.cli migrate` as the schema owner when `status` reports
  the schema behind.
- **Least privilege.** With `unifi_mcp_least_privilege` (the default) and a
  Postgres the playbook runs, the server and workers connect as
  `unifi_mcp_runtime` with the grants in SECURITY.md. Migrations and
  retention use the owner. The runtime password reaches `psql` through an
  environment variable, never a file or the command line.
- **Containers.** `unifi-mcp-0`, `unifi-mcp-1`, ... listen on
  `unifi_mcp_bind_address` at `unifi_mcp_port`, `unifi_mcp_port + 1`, ...
  Each has its own log directory under `/opt/unifi-mcp/logs/<n>`, because
  each audit log is its own hash chain. Docker checks `/healthz`.
  `unifi-mcp-worker-<n>` run health checks and snapshots (fleet only).
  Settings are in `/opt/unifi-mcp/server.env` (mode 0600).
- **Retention.** When `unifi_mcp_audit_retention_days` is set, cron runs
  `/opt/unifi-mcp/audit-retention.sh` daily. With Postgres, one host runs it,
  archiving to `/opt/unifi-mcp/archive`. Without Postgres, each replica's
  log is archived next to it. Logs rotate at `unifi_mcp_audit_log_rotate_mb`.
- **nginx (cluster).** Hashes each client address and token to one replica,
  so a session stays where it started (MULTI_CONTROLLER.md). Buffering is
  off and reads are long, for streaming. Set `lb_tls_certificate` and
  `lb_tls_certificate_key` (paths on the `lb` host) to serve TLS.

## Settings

The role defaults are in `roles/unifi_mcp/defaults/main.yml`. Any other server
setting from [API.md](../../API.md) goes in `unifi_mcp_env_extra`:

```yaml
unifi_mcp_env_extra:
  UNIFI_PROFILE: network
  UNIFI_READ_ONLY: "true"
```

For a managed Postgres or Redis, delete those groups and set
`unifi_mcp_database_url` (the role the server runs as),
`unifi_mcp_migration_database_url` (the owner, if different) and
`unifi_mcp_redis_url`. You then create the least-privilege role yourself,
following SECURITY.md.

## Security notes

- Replicas bind to `127.0.0.1` on a single host. In the cluster they bind to
  each host's `private_address`, and Redis and Postgres publish their ports
  there too. Keep that network private, or encrypted (WireGuard, for
  example), and firewall it to the cluster's hosts.
- Without TLS on nginx, bearer tokens cross the network in the clear. Serve
  TLS whenever clients are not on the same private network.
- The vault holds every secret. Rotate `vault_mcp_auth_token` by changing it
  and rerunning. Rotate the Fernet keys as SECURITY.md describes, not by
  replacing them.
