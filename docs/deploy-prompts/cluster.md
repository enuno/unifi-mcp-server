# Prompt: a cluster behind nginx

Paste everything below the line into your agent.

---

Deploy the UniFi MCP server as a cluster with the Ansible playbook in
`deploy/ansible/` of https://github.com/enuno/unifi-mcp-server: MCP replicas
and workers on two or more hosts, Redis and Postgres on a data host, and
nginx in front. Read `deploy/ansible/README.md`, `MULTI_CONTROLLER.md` (how
sessions stick to a replica) and the least-privilege and retention parts of
`SECURITY.md` first, and follow them.

Rules:

- Ask me for anything you need that you cannot find out yourself. Never guess
  addresses or credentials.
- Secrets go only in `inventories/cluster/group_vars/all/vault.yml`,
  encrypted with `ansible-vault`. Never print a secret, put one on a command
  line, or commit one. Generate every token, password and key yourself with
  the commands in `vault.yml.example`, and tell me where they are, not what
  they are. Tell me to back up the vault and its password.
- Before you run the playbook, show me the inventory,
  `group_vars/all/main.yml` and the firewall rules you propose, and wait for
  my approval.
- If a step fails, stop and tell me what failed and what you suggest. Do not
  disable TLS verification, the bearer token, least privilege, or any safety
  setting to get past an error.

Steps:

1. Ask me for: each host's SSH address, its private address and its role
   (`lb`, `mcp`, data); the UniFi API type, controller address and port,
   whether its certificate is self-signed, and the API key; replicas and
   workers per `mcp` host (default 2 and 1); the TLS certificate and key
   paths on the `lb` host, or whether I want you to get one (ask how);
   audit retention days (default 365); and a SIEM target if any.
2. Check the private network: every `mcp` host must reach the data host on
   5432 and 6379, and the `lb` host must reach each `mcp` host's replica
   ports. Nothing else should. Propose firewall rules that allow only that
   (I approve them before you apply them). If the private network is not
   trusted, stop and tell me: Redis and Postgres traffic is not encrypted
   by this playbook.
3. Install `ansible-core` 2.15 or later if needed and the collections in
   `requirements.yml` into `deploy/ansible/collections`. Check SSH and sudo
   with `ansible -i inventories/cluster/hosts.yml all -m ping -b`.
4. Edit `inventories/cluster/hosts.yml` and `group_vars/all/main.yml`.
5. Create and encrypt the vault with every value in `vault.yml.example`.
6. Run `ansible-playbook ... --syntax-check`, show me the plan, and after my
   approval run the playbook.
7. Verify:
   - through nginx: `curl -fsS https://<lb>/healthz` returns
     `{"status":"ok"}`, and the `initialize` request from the README, with
     the bearer token from the vault (read into a variable, never echoed),
     returns a `serverInfo` and an `mcp-session-id` header;
   - the same session works for a second request (`tools/list` with that
     `mcp-session-id`), which shows nginx keeps a client on one replica;
   - on each `mcp` host, `docker ps` shows every replica healthy and the
     workers running;
   - the servers connect as `unifi_mcp_runtime`, and the retention cron job
     exists on the first `mcp` host only.
8. Tell me the client URL and header, how to read the token with
   `ansible-vault view`, how to issue per-person tokens
   (`python -m src.fleet.cli tokens create`, run in any replica), and how to
   scale (change `unifi_mcp_replicas` and rerun).
