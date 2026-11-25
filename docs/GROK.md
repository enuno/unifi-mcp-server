# Grok

Grok has no plugin catalog that a developer publishes into. A Grok user adds a remote MCP server by URL, and that is the whole integration model. This project therefore has nothing to "publish" to Grok; what it has is an endpoint a user could point at.

**Status: blocked.** The blocker is the same as for ChatGPT: there is no public HTTPS endpoint. See the prerequisites below.

## What Grok does and does not have

The task brief said "Grok has no plugin catalog". That is mostly right, but it is worth being precise, because the difference matters for what a developer can do.

xAI has three surfaces:

| Surface | What it is | Can a developer publish into it? |
|---|---|---|
| The connector catalog at grok.com/connectors | Pre-configured OAuth connectors | No |
| The plugin Marketplace tab in Grok Build CLI | User-configured marketplace sources | No. It reads the user's own sources |
| The Grok Bot app catalog | Apps, hosted by Cursor | No |

There is no public third-party marketplace where a developer publishes a plugin and users install it. A custom MCP server is bring-your-own, not marketplace-published.

What Grok does have is the xAI API's `tools` array, which accepts a remote MCP server per request:

```json
{
  "tools": [
    {
      "type": "mcp",
      "server_url": "...",
      "server_label": "..."
    }
  ]
}
```

That is a per-request parameter, not a persistent registry. The Management API has no connectors resource, and xAI states that `connector_id` is not currently supported.

## Add a custom MCP connector

### grok.com, individual user

Verbatim from https://docs.x.ai/grok/connectors (retrieved 2026-11-25):

> "To add a custom MCP connector:
>
> 1. Go to [grok.com/connectors](https://grok.com/connectors).
> 2. Click **New Connector**, then select **Custom**.
> 3. Enter the MCP server URL and complete any required authentication."

An alternate entry path on the same site: sign in, click the **+** button, select **Connectors**, and click **+ Add connector**.

On mobile: **Settings → Connectors**.

Connectors are available to all Grok users.

### Grok Business and Enterprise, admin provisioning

On Business and Enterprise plans, a team admin must add the connector in the cloud console before members can use it.

Verbatim from https://docs.x.ai/grok/connector-management (retrieved 2026-11-25):

> "On Grok Business and Enterprise plans, a team admin must add a connector in the cloud console before team members can connect and use it."

The path: log in to console.x.ai, select your team, and go to **Grok Business → Connectors**. Then:

> "1. On the connectors page, click **+ Add Connector**.
> 2. Select **Other** and enter your MCP server URL.
> 3. Complete any required authentication."

Adding and removing connectors requires **Team Read-Write** permissions.

Note the label difference: the consumer UI says **"Custom"**, the admin console says **"Other"**. Both mean a third-party MCP server.

Once the admin adds the connector, "Team members can then connect their own accounts on grok.com/connectors", so the definition is provisioned once and the authorization is per member.

## What the user has to supply

| Field | grok.com "Custom" dialog | Documented? |
|---|---|---|
| Server URL | "Enter the MCP server URL" | Yes |
| Server label or name | — | `TODO(verify)`: not documented for the grok.com dialog |
| Transport type | — | `TODO(verify)`: not documented for the grok.com dialog |
| OAuth client id or secret | "complete any required authentication" | `TODO(verify)`: xAI documents none of the OAuth fields for the grok.com dialog |

The only fully documented custom-connector field set belongs to **Grok Bot**, which is a different product surface that runs in Cursor's cloud. It documents a **Name**, a **Type** of **Remote HTTPS** or **Command**, a **Server URL**, optional **HTTP headers**, and an OAuth **Client ID** with a **Client secret** field that appears once an id is entered. Do not read that dialog as the grok.com dialog.

## Requirements for the endpoint

**Public reachability is required.** Verbatim from https://docs.x.ai/grok/connectors (retrieved 2026-11-25):

> "Your MCP server must be reachable over the public internet. If it is running on your local machine, you will need a tunneling service to make it accessible."

And from https://docs.x.ai/grok/connectors/custom-mcp-tunneling (retrieved 2026-11-25):

> "Grok's servers need to reach your MCP server over the public internet. Servers running on `localhost` or a private network address (such as `127.0.0.1`, `10.x.x.x`, `172.16.x.x`, or `192.168.x.x`) are not directly reachable, and Grok will reject these URLs."

**Transport.** On the API path, the only supported transports are Streaming HTTP and SSE. stdio is not supported server-side, because Grok connects to a URL.

**The `/mcp` path suffix is not a documented requirement.** No official xAI page states that the URL must end in `/mcp`. The official examples use such URLs, but the requirement comes from third-party guides. `TODO(verify)`: treat it as your server's actual MCP endpoint path, not as a fixed suffix.

**HTTPS.** The API docs say "Always use HTTPS URLs and implement proper authentication mechanisms on your MCP server", and the Grok Bot connector type is literally "Remote HTTPS". `TODO(verify)`: whether the grok.com dialog rejects a plain `http://` URL.

**CORS is not mentioned** on any xAI page retrieved on 2026-11-25.

**Authentication.** Verbatim from the tunneling page:

> "Authentication still applies. If your MCP server requires OAuth or API keys, you will still complete that flow in Grok after providing the tunnel URL. The tunnel only handles network reachability."

For catalog and built-in connectors, each authenticates via OAuth. For a custom connector, xAI documents only "complete any required authentication", with no client-id or secret, no authorization URL, no token URL, no dynamic client registration and no PKCE details. `TODO(verify)`: all of those, confirmed against the live dialog by a logged-in operator.

## Prerequisites for this server to work with Grok

The same list as the ChatGPT connector, in [docs/CHATGPT_CONNECTOR.md](CHATGPT_CONNECTOR.md), applies. In short:

1. A public HTTPS Streamable HTTP endpoint that Grok's servers can reach.
2. Per-user authentication, because the UniFi API key belongs to one controller and cannot be issued per Grok user.
3. A strategy for reaching a private controller: a relay, a per-user agent, or a hosted gateway.
4. A privacy policy URL and a support contact.
5. Test credentials that work from outside a private network, with no MFA.

This project has none of these. The server is a stdio process that reads one API key from its environment.

## Tunneling

If a user runs the server on their own machine, they need a tunnel. The xAI docs cover this at https://docs.x.ai/grok/connectors/custom-mcp-tunneling (retrieved 2026-11-25). One transport caveat from that page:

> "SSE not supported: Cloudflare quick tunnels do not support Server-Sent Events (SSE). If your MCP server uses the SSE transport, use ngrok instead. Servers using the newer Streamable HTTP transport work fine with Cloudflare."

The server's Streamable HTTP transport is therefore the one that works with a Cloudflare quick tunnel.

## Sources

All URLs retrieved on 2026-11-25.

| Page | URL |
|---|---|
| Grok connectors | https://docs.x.ai/grok/connectors |
| Custom MCP tunneling | https://docs.x.ai/grok/connectors/custom-mcp-tunneling |
| Connector management (Business and Enterprise) | https://docs.x.ai/grok/connector-management |
| Remote MCP Tools | https://docs.x.ai/developers/tools/remote-mcp |
| xAI docs MCP server | https://docs.x.ai/developers/docs-mcp |
| Grok Bot custom connectors | https://docs.x.ai/grok-bot/computer-and-apps |
| Grok Build: skills, plugins and marketplaces | https://docs.x.ai/build/features/skills-plugins-marketplaces |
