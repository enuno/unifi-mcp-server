# Plugins

This repository ships the UniFi MCP Server as a Claude Code plugin and as a ChatGPT/Codex plugin. The skills in `skills/` are the single source of truth for both: the packages are assembled from them, and no skill content is duplicated in the repository.

- **Claude plugin** — the repository is the plugin and a self-hosted marketplace. It ships the MCP server over stdio and the operator skills.
- **ChatGPT/Codex plugin** — a skills-only package. The skills are portable; an MCP server needs a hosted endpoint, and this project does not have one yet.

## Layout

| Path | What it is |
|---|---|
| `.claude-plugin/plugin.json` | Claude plugin manifest |
| `.claude-plugin/marketplace.json` | Self-hosted marketplace manifest |
| `.claude-plugin/icon.png` | Listing icon, 1024x1024 PNG |
| `.mcp.json` | MCP server definition, stdio over `uvx` |
| `skills/` | The skills. The source of truth for both platforms |
| `skills/manifest.json` | Machine-readable index of the skills. Generated |
| `scripts/generate_skills_manifest.py` | Regenerates `skills/manifest.json` |
| `scripts/build_plugin_packages.py` | Builds the distributable packages into `dist/` |
| `scripts/validate_plugins.py` | Validates the manifests. Runs in CI |

## Skill audiences

`skills/manifest.json` records the audience of every skill:

- **operator** — helps an operator run a network through a running MCP server. These ship in the packages.
- **developer** — helps a coding agent change this codebase. These stay in the repository.

The split matches `docs/SKILLS.md`. The operator skills are `unifi-network`, `unifi-devices`, `unifi-security`, `unifi-system`, `unifi-protect`, `unifi-fleet-operations`, `unifi-channel-planning`, `unifi-discovery`, `unifi-safe-changes` and `unifi-mcp-setup`.

### Two installs, two skill sets

| Install | Skills loaded |
|---|---|
| `dist/claude/unifi-mcp-server.zip`, `dist/chatgpt/unifi-mcp-server.zip` | The 10 operator skills |
| The repository, as a marketplace | All 16 skills |

The packages ship the operator skills only. A marketplace install of the
repository loads all 16, because Claude Code always scans the plugin root's
`skills/` directory and the manifest's `skills` field only adds directories
to that scan; it cannot replace it. There is no manifest field that removes
a skill from the default scan, so the repository's `skills/` directory is
what a marketplace install loads.

Keeping the repository's `skills/` directory whole matters because it is the
source of truth for every consumer: the packages are built from it, the
Mintlify site serves it through symlinks, and the repository's own tests
read it. The alternative, moving the developer skills one directory deeper
so the default scan skips them, would change the paths that those tests,
those symlinks and the documentation all use.

The distributable packages are the artifacts whose skill set is a decision
rather than a consequence of the repository layout, so the boundary is
enforced there: `scripts/validate_plugins.py` fails the build if a package
ships a developer skill or omits an operator skill.

## Build the packages

```bash
python scripts/generate_skills_manifest.py   # refresh skills/manifest.json
python scripts/build_plugin_packages.py      # write dist/
```

The build writes:

- `dist/claude/unifi-mcp-server/` and `dist/claude/unifi-mcp-server.zip`
- `dist/chatgpt/unifi-mcp-server/` and `dist/chatgpt/unifi-mcp-server.zip`

`dist/` is a build artefact and is not tracked by git.

## Install the Claude plugin

From this repository, as a local marketplace:

```bash
claude plugin marketplace add /path/to/unifi-mcp-server
claude plugin install unifi-mcp-server --marketplace unifi-mcp-server
```

From GitHub, once the branch is merged:

```bash
/plugin marketplace add enuno/unifi-mcp-server
/plugin install unifi-mcp-server --marketplace enuno/unifi-mcp-server
```

## Configure the MCP server

The plugin starts the server read-only and with a small tool profile. Set the credential in your environment before installing:

```bash
export UNIFI_API_KEY="<your UniFi API key>"
```

`.mcp.json` refers to `${UNIFI_API_KEY}` and to `${UNIFI_LOCAL_HOST}` and the other settings with `${VAR:-default}` placeholders. Claude Code expands them from your environment and warns when a variable is unset. No credential is stored in the repository.

### Cloud API (the default)

```bash
export UNIFI_API_KEY="<your Site Manager API key>"
export UNIFI_API_TYPE=cloud-ea
```

### A local console

```bash
export UNIFI_API_KEY="<your local console API key>"
export UNIFI_API_TYPE=local
export UNIFI_LOCAL_HOST=192.168.1.1
export UNIFI_LOCAL_VERIFY_SSL=true
```

### Opt in to write operations

The plugin defaults to `UNIFI_READ_ONLY=true`, which does not register any mutating tool, and to `UNIFI_PROFILE=minimal`, which registers only the site, client and device tools.

To let the agent change controller state:

```bash
export UNIFI_READ_ONLY=false
```

To widen the tool surface, set `UNIFI_PROFILE` to one of the profiles the server defines: `network`, `devices`, `security`, `system`, `minimal`, `protect`, `mobility`, `innerspace`, `carrier`.

An unset `UNIFI_PROFILE` does **not** load every tool. The plugin sets the
default to `minimal`, so a variable that is not set selects the minimal
profile, which registers only the site, client and device tools. Set
`UNIFI_PROFILE=all` for the full surface:

```bash
export UNIFI_PROFILE=all
```

`all` is the value the server recognises for the whole tool surface.

The server classifies every tool as a read, a write or a destructive change. The destructive tools, which include the firewall, device and network changes, need `confirm=True` and are refused entirely in a read-only session.

| Mode | Tools registered | What it can do |
|---|---|---|
| `UNIFI_READ_ONLY=true` | 219 | Observe only |
| `UNIFI_READ_ONLY=true`, `UNIFI_PROFILE=minimal` | 17 | Observe sites, clients and devices |
| `UNIFI_READ_ONLY=false` | 365 | Everything, with `confirm=True` on every write |

## Validate

```bash
claude plugin validate . --strict
claude plugin validate dist/claude/unifi-mcp-server --strict --profile directory
python scripts/validate_plugins.py
```

`claude plugin validate` needs Claude Code v2.1.326 or later.

## Publish to the Anthropic directory

The directory takes a plugin bundle. The steps below come from the pages listed in "Sources" below, retrieved on 2026-11-25.

1. Open the developer portal and select **Submit new**, then **Plugin bundle**.
2. On the **Source** step, fill in **Repository** (`enuno/unifi-mcp-server`), **Plugin path** (leave empty; the plugin is at the repository root) and **Branch or tag** (`main`).
3. On the **Listing details** step, the portal reads the listing from `plugin.json` and the README. It shows them for review rather than asking for them. To change a field, edit `plugin.json` or the README in the repository.
4. On the **Data handling** step, answer whether the plugin reads or stores personal data, whether it sends data to services other than its declared connectors, how long it keeps data, and whether it is intended for people under 18.
5. On the **Compliance** step, confirm the contact email and select all four acknowledgements.
6. On the **Review and submit** step, choose how new versions reach the directory, select **Submit for review**, and decide whether passing versions publish automatically.

The listing needs, in `plugin.json` or the plugin folder:

| Requirement | Where it comes from |
|---|---|
| A description | `plugin.json` `description`, and the README |
| A README of at least 40 words | The README |
| A license | `plugin.json` `license`, and the `LICENSE` file |
| An icon | `plugin.json` `icon`, and `.claude-plugin/icon.png` |
| At least three example prompts | `docs/submission/example-prompts.md` |

The directory also reads `documentationUrl`, `supportUrl`, `privacyPolicyUrl` and `termsOfServiceUrl` from `plugin.json` for the listing. `TODO(verify)`: this plugin does not set those four yet, because it has no public privacy policy or terms page. Add them before submitting, or state that no data is collected.

### Before you submit

- `TODO(verify)`: the directory's example-prompt field for a plugin bundle is not documented. The three prompts in `docs/submission/example-prompts.md` satisfy the policy requirement of "at least three working examples of prompts or use cases". Confirm where the portal expects them.
- `TODO(verify)`: the directory's icon dimension rules are not documented. The validator asks for a square PNG of 512 to 2048 pixels on each side under 2 MB, and this plugin uses a 1024x1024 PNG of 0.80 MB.
- `TODO(verify)`: no listing fee and no review-time SLA are documented on any of the pages retrieved on 2026-11-25.

## Publish to ChatGPT and Codex

See [docs/CHATGPT_CONNECTOR.md](CHATGPT_CONNECTOR.md).

## Grok

Grok has no plugin catalog that a developer publishes into. A Grok user adds a remote MCP server by URL. See [GROK.md](GROK.md).

## Sources

All URLs retrieved on 2026-11-25.

| Page | URL |
|---|---|
| Claude Code plugin reference | https://code.claude.com/docs/en/plugins/manifest-reference |
| Claude Code marketplace reference | https://code.claude.com/docs/en/plugins/marketplace-reference |
| Claude Code CLI reference | https://code.claude.com/docs/en/plugins/cli-reference |
| Claude Code plugin components | https://code.claude.com/docs/en/plugins/components |
| Claude Code publish and distribute | https://code.claude.com/docs/en/plugins/publish |
| Claude Code MCP reference | https://code.claude.com/docs/en/mcp |
| Claude Code skills | https://code.claude.com/docs/en/skills |
| Submit your plugin to the Anthropic directory | https://claude.com/docs/plugins/submit |
| Plugin pre-submission checklist | https://claude.com/docs/plugins/pre-submission-checklist |
| Publish to the directory | https://claude.com/docs/directory/publish |
| Submit a connector to the directory | https://claude.com/docs/connectors/building/submission |
| Connector review criteria | https://claude.com/docs/connectors/building/review-criteria |
| Anthropic Software Directory Policy | https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy |
| Submit your Claude Code plugin to OpenAI | https://developers.openai.com/plugins/guides/submit-claude-plugin |
| Package your plugin (OpenAI) | https://developers.openai.com/plugins/guides/package-your-plugin |
| OpenAI plugin manifest fields | https://developers.openai.com/plugins |
| OpenAI Apps SDK MCP servers | https://developers.openai.com/apps-sdk/build/mcp-server |
| OpenAI remote MCP server review requirements | https://developers.openai.com/apps-sdk/build/mcp-server#remote-mcp-server-review-requirements |
| xAI Remote MCP Tools | https://docs.x.ai/developers/tools/remote-mcp |
| xAI Grok connectors | https://docs.x.ai/grok/connectors |
| xAI custom MCP tunneling | https://docs.x.ai/grok/connectors/custom-mcp-tunneling |
