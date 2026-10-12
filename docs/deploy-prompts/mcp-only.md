# Prompt: the MCP server alone on one host

Paste everything below the line into your agent.

---

Deploy the UniFi MCP server to one Linux host with the Ansible playbook in
`deploy/ansible/` of https://github.com/enuno/unifi-mcp-server. Read
`deploy/ansible/README.md` first and follow it. This deployment has no Redis
and no Postgres: the server keeps its audit log as a file and reads the
controller from its `UNIFI_*` settings.

Rules:

- Ask me for anything you need that you cannot find out yourself. Never guess
  addresses or credentials.
- Secrets go only in `inventories/single/group_vars/all/vault.yml`, encrypted
  with `ansible-vault`. Never print a secret, put one on a command line, or
  commit one. Generate the bearer token and the chain key yourself, with the
  commands in `vault.yml.example`, and tell me where they are stored, not what
  they are.
- Before you run the playbook, show me the inventory and
  `group_vars/all/main.yml` and wait for my approval.
- If a step fails, stop and tell me what failed and what you suggest. Do not
  disable TLS verification, the bearer token, or any safety setting to get
  past an error.

Steps:

1. Ask me for: the host's SSH address and user, the UniFi API type (`local`,
   `cloud-v1` or `cloud-ea`), the controller's address and port if local,
   whether its certificate is self-signed, and the UniFi API key (I will
   paste it into the vault file myself if I prefer).
2. Install `ansible-core` 2.15 or later if needed and the collections in
   `requirements.yml` into `deploy/ansible/collections`. Check SSH and sudo
   with `ansible -i inventories/single/hosts.yml all -m ping -b`.
3. Edit `inventories/single/hosts.yml`: set the host and delete the `redis`
   and `postgres` groups. Edit `group_vars/all/main.yml` for the controller.
   Keep `unifi_mcp_bind_address: 127.0.0.1` unless I ask otherwise.
4. Create and encrypt the vault with `vault_unifi_api_key`,
   `vault_mcp_auth_token` and `vault_audit_chain_key`.
5. Run `ansible-playbook ... --syntax-check`, show me the plan, and after my
   approval run the playbook.
6. Verify on the host: `curl -fsS http://127.0.0.1:3000/healthz` returns
   `{"status":"ok"}`, and the `initialize` request from the README, sent with
   the bearer token from the vault (read it into a variable, do not echo
   it), returns a `serverInfo`. Then send `tools/list` the same way, with the
   `mcp-session-id` header the first response returned.
7. Tell me how to connect my MCP client: the URL (through an SSH tunnel or
   a TLS proxy, since it listens on loopback), the header
   `Authorization: Bearer <token from the vault>`, and how to read the token
   with `ansible-vault view`.
