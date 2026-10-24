# Agent setup prompts

Each file here is a prompt to paste into an AI coding agent (Claude Code, for
example) running on the machine you deploy from. The agent asks you for what
it cannot know, runs the Ansible playbook in
[deploy/ansible/](/deploy/ansible/overview), and checks the result.

| Prompt | Deploys |
| --- | --- |
| [mcp-only.md](/docs/deploy-prompts/mcp-only) | The MCP server alone on one host |
| [single-server-fleet.md](/docs/deploy-prompts/single-server-fleet) | The server, a worker, Redis and Postgres on one host |
| [cluster.md](/docs/deploy-prompts/cluster) | Replicas on several hosts behind nginx, with shared Redis and Postgres |

Every prompt tells the agent to:

- keep secrets in an encrypted Ansible vault and never print them or put
  them in a command line, a commit or a chat message;
- show you the inventory and settings and wait for your approval before it
  changes any host;
- stop and ask you when something fails, instead of working around it.

Read what the agent proposes before you approve it: the playbook installs
Docker and runs containers as root on the hosts you name.
