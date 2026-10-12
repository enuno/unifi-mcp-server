# Prompt: a single-server fleet

Paste everything below the line into your agent.

---

Deploy the UniFi MCP server as a single-server fleet with the Ansible
playbook in `deploy/ansible/` of https://github.com/enuno/unifi-mcp-server:
the server, one worker, Redis and Postgres, all as containers on one Linux
host. Read `deploy/ansible/README.md` and the least-privilege and retention
parts of `SECURITY.md` first, and follow them.

Rules:

- Ask me for anything you need that you cannot find out yourself. Never guess
  addresses or credentials.
- Secrets go only in `inventories/single/group_vars/all/vault.yml`, encrypted
  with `ansible-vault`. Never print a secret, put one on a command line, or
  commit one. Generate every token, password and key yourself with the
  commands in `vault.yml.example`, and tell me where they are, not what they
  are. Tell me to back up the vault and its password: losing
  `vault_fleet_credential_key` makes the stored controller keys unreadable.
- Before you run the playbook, show me the inventory and
  `group_vars/all/main.yml` and wait for my approval.
- If a step fails, stop and tell me what failed and what you suggest. Do not
  disable TLS verification, the bearer token, least privilege, or any safety
  setting to get past an error.

Steps:

1. Ask me for: the host's SSH address and user, the UniFi API type, the
   controller's address and port if local, whether its certificate is
   self-signed, the UniFi API key, how many days of audit records to keep
   (default 365), and whether to send audit records to a SIEM (then its
   target URL).
2. Install `ansible-core` 2.15 or later if needed and the collections in
   `requirements.yml` into `deploy/ansible/collections`. Check SSH and sudo
   with `ansible -i inventories/single/hosts.yml all -m ping -b`.
3. Edit `inventories/single/hosts.yml` (keep the `mcp`, `redis` and
   `postgres` groups on the one host) and `group_vars/all/main.yml`.
4. Create and encrypt the vault with every value in `vault.yml.example`.
5. Run `ansible-playbook ... --syntax-check`, show me the plan, and after my
   approval run the playbook.
6. Verify on the host:
   - `curl -fsS http://127.0.0.1:3000/healthz` returns `{"status":"ok"}`;
   - the `initialize` request from the README, with the bearer token from
     the vault (read into a variable, never echoed), returns a `serverInfo`;
   - `docker ps` shows `unifi-mcp-0`, `unifi-mcp-worker-0`,
     `unifi-mcp-redis` and `unifi-mcp-postgres`, the server healthy;
   - `docker logs unifi-mcp-worker-0` shows health checks completing;
   - the server connects as `unifi_mcp_runtime`, not the owner:
     `docker exec unifi-mcp-postgres psql -U unifi_mcp -d unifi_mcp -c "select usename from pg_stat_activity where datname='unifi_mcp'"`;
   - `crontab -l` as root lists the audit retention job, and
     `/opt/unifi-mcp/audit-retention.sh` run once by hand exits 0.
7. Tell me how to connect my MCP client (URL through an SSH tunnel or a TLS
   proxy, the bearer header, and how to read the token with
   `ansible-vault view`), and how to issue per-person tokens with roles:
   `docker exec unifi-mcp-0 python -m src.fleet.cli tokens create --name <who> --role <role>`,
   with a role of `viewer`, `operator`, `admin` or `fleet-admin` (SECURITY.md).
