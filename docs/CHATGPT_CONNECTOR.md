# ChatGPT and Codex

There are two ways to use this server with ChatGPT and Codex, and they are different products.

- **Skills only** — the plugin package ships the operator skills. ChatGPT reads them, and the skills guide the agent on what to ask for. **No MCP server, no tools.** The agent cannot read or change anything until an MCP server is configured separately.
- **MCP enabled** — ChatGPT calls the UniFi tools directly. This needs a hosted HTTPS endpoint. **This project does not have one, so this variant is blocked.** The prerequisites are listed below.

## Variant A: skills-only, ready to submit

The skills-only package is built from the same `skills/` directory as the Claude plugin:

```bash
python scripts/build_plugin_packages.py
```

It produces `dist/chatgpt/unifi-mcp-server/` and `dist/chatgpt/unifi-mcp-server.zip`. The package holds:

- `plugin.json` — the portable manifest
- `.claude-plugin/plugin.json` — the same manifest, so the archive also qualifies for a direct Claude upload
- `skills/<name>/SKILL.md` — the 10 operator skills
- `LICENSE`, `README.md` and the icon

It deliberately carries **no** `.mcp.json` and **no** `.claude-plugin/marketplace.json`, because a skills-only upload excludes MCP server configuration.

The skills describe the tools and the safe way to use them. On their own they teach the agent the shape of the work; they do not give the agent a way to call the server. A user who wants the tools needs to add the MCP server separately, per [docs/PLUGINS.md](PLUGINS.md).

### Submit

The OpenAI guide for this exact case is "Submit your Claude Code plugin to OpenAI", at https://developers.openai.com/plugins/guides/submit-claude-plugin (retrieved 2026-11-25). Its direct-upload bar:

> "Confirm that the archive root, or its single top-level directory, includes `.claude-plugin/plugin.json` with a nonempty `description` and at least one valid skill at `skills/<skill-name>/SKILL.md`."

This package satisfies all three.

Before submitting:

1. Get **Apps Management** write access in the OpenAI organization that will own the plugin. The guide requires it.
2. Complete individual or business identity verification.
3. Open the portal at https://platform.openai.com/plugins, select **Create plugin**, choose **Skills only**, and upload `dist/chatgpt/unifi-mcp-server.zip`.
4. Review the generated `.codex-plugin/plugin.json`. The portal converts the manifest and adds missing interface defaults.
5. Test the imported skills in a clean environment: each skill must find its referenced files and must not depend on undeclared local packages, files or credentials.
6. Complete the listing and review fields, fix every scan result, and submit the draft.

The guide also says every plugin must complete OpenAI review.

### What the conversion drops

The guide is explicit that these Claude constructs are not carried over, and the portal either ignores or rejects them:

| Claude construct | Treatment |
|---|---|
| `.mcp.json`, `mcpServers` | Not carried over. A skills-only upload has no MCP server |
| `.claude-plugin/marketplace.json` | Not carried over |
| `commands/`, `agents/` | Converted to skills |
| `hooks/hooks.json` | Removed before public submission |
| `userConfig`, `${user_config.*}` | Not supported. OpenAI does not run Claude installation prompts |
| `outputStyles`, `lspServers`, `experimental.*`, `channels`, `dependencies` | Converted to skills or removed |

This package has none of those, so the conversion is a no-op. `TODO(verify)`: the guide says the portal "normalizes text fields during conversion"; check the generated manifest before submitting.

### For Codex

Codex reads the same `SKILL.md` format. The `skills/` directory in this repository already works with Codex through `.agents/skills/`. The plugin package adds nothing Codex-specific beyond the manifest.

## Variant B: MCP-enabled, blocked

**Status: blocked.** This variant needs infrastructure that does not exist yet. Nothing in this repository invents an endpoint or a URL.

### Prerequisites

Each item below is a requirement, not a suggestion. Every one of them must be true before a submission can be attempted.

**1. A public HTTPS Streamable HTTP endpoint**

- The server must answer on a public HTTPS URL that ends in `/mcp`.
- The endpoint must remain reachable for plugin review and for domain verification.
- The docs are explicit that a local endpoint, a temporary tunnel or Secure MCP Tunnel alone is not acceptable for a public submission.
- A tunnel that reaches a private controller is acceptable as a *transport*, but the endpoint the user and the reviewer connect to must still be a stable public HTTPS URL.

**2. Per-user authentication**

- OAuth 2.1, following the MCP authorization specification.
- PKCE with `S256` is mandatory.
- The server must publish protected-resource metadata.
- The authorization server must echo the `resource` parameter.
- The redirect URI is `https://chatgpt.com/connector/oauth/{callback_id}`, or the stable `https://chatgpt.com/connector_platform_oauth_redirect`.
- A shared static API key is not per-user authentication. The UniFi API key belongs to one controller and cannot be issued per ChatGPT user.

**3. A strategy for reaching private controllers**

A ChatGPT user has no route to a UniFi console on their own LAN. The server needs one of:

- **A relay** in a network that can reach the controller, holding the controller credentials, with the relay authenticating the ChatGPT user to it.
- **A per-user agent** running on the user's network, holding the user's own controller credentials, reachable over the tunnel.
- **A hosted multi-tenant gateway** that stores controller credentials and routes each call to the right controller.

Whichever is chosen, it decides the data-handling answers on the submission form, because the gateway holds controller credentials and possibly customer network data.

**4. A privacy policy URL**

- Must be `https://` and published.
- Must state at minimum the categories of personal data collected, the purposes of use, the categories of recipients, the data retention timelines, and any controls offered to users.
- Must match what the implementation actually does. If the relay stores controller credentials, the policy says so.

**5. A support contact**

- A `supportURL` and a contact email for review updates.
- The manifest field `supportURL` is required for MCP review.

**6. Test credentials**

- A dedicated test account, a login URL, workspace or tenant details, and sign-in instructions.
- It must work immediately, with no MFA, no email or SMS code, no magic link, and no private-network access.
- Use sample data, not a real user's account.
- The credentials must work from outside the company's networks, local area networks and other internal networks.

**7. Review guidelines**

- Every plugin must complete OpenAI review. The review may be automated scans or manual review.
- A rejection for the MCP server, its tools or its UI comes back with the failed checks named, and a resubmission is allowed.
- A connector with an MCP App UI must follow the documented screenshot specification: PNG, at least 1000 px wide, 3 to 5 images, cropped to the app response without the prompt in the image, with the paired prompt text supplied separately. Video and GIF are not accepted.
- The listing fields come from the manifest: `privacyPolicyURL`, `supportURL`, `websiteURL` and `termsOfServiceURL`, all HTTPS and at most 1024 characters each.
- EU data residency projects cannot submit plugins with MCP servers for review.

### What this project would need to change

The server today is a stdio process that reads `UNIFI_API_KEY` from its environment and talks to one controller. To serve this variant it would need:

- A network transport that speaks Streamable HTTP. The server already has `http`, `sse` and `streamable_http` transports, and refuses to start a network transport without authentication.
- An OAuth 2.1 provider, which the server has for fleet mode (`MCP_AUTH_TOKEN`) but not as a per-user OAuth 2.1 flow with PKCE.
- A credential store keyed by user, since each ChatGPT user brings their own controller.
- A tool allowlist per user, because the tool surface is 365 tools wide and a user's ChatGPT session should not see all of them.

None of that is in scope for this change, and none of it is stubbed in this repository.

## Plan gating

Custom MCP server connections and full MCP support are available for ChatGPT Business and Enterprise/Edu customers on ChatGPT web. Pro users can build apps with the Apps SDK and can connect custom MCP servers with read/fetch permissions. Custom MCP servers are web only.

In the current Plugins experience a user adds a custom MCP server directly from Plugins; Developer Mode does not have to be turned on first. The workspace permission is **Create plugins with MCPs**, and only admins and owners can create and publish plugins for custom MCP servers in a Business workspace.

## Sources

All URLs retrieved on 2026-11-25.

| Page | URL |
|---|---|
| Submit your Claude Code plugin to OpenAI | https://developers.openai.com/plugins/guides/submit-claude-plugin |
| Package your plugin | https://developers.openai.com/plugins/guides/package-your-plugin |
| Plugin manifest fields | https://developers.openai.com/plugins |
| Apps SDK: build an MCP server | https://developers.openai.com/apps-sdk/build/mcp-server |
| Remote MCP server review requirements | https://developers.openai.com/apps-sdk/build/mcp-server#remote-mcp-server-review-requirements |
| Add a custom MCP server | https://developers.openai.com/plugins |
| ChatGPT Help Center: custom MCP servers | https://help.openai.com/en/articles/11487765-connectors-in-chatgpt |
| Legacy ChatGPT plugin manifest | https://developers.openai.com/plugins/plugins-quickstart |
