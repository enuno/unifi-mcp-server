---
name: mintlify-docs
description: Use when maintaining, validating, updating or publishing this repository's Mintlify documentation site - docs.json, .mintignore, .mintlify/, the navigation tree, a published page, the agent skills the site serves, or the mintlify-docs and mintlify MCP servers - and for audit, update, verify, release-sync and publish runs against them.
license: Apache-2.0
metadata:
  author: UniFi MCP Server Team
  version: "1.0.0"
---

# Mintlify Documentation Maintenance

This repository publishes its documentation as a Mintlify site. The site is
built from the Git repository, so **Git is the source of truth**; the Mintlify
admin MCP is an editing and publishing surface over that same repository, not a
second copy of the content.

Two MCP servers are involved, and they are not interchangeable:

| Server | Purpose | Authority |
|---|---|---|
| `mintlify-docs` | Read-only. Mintlify's own documentation: file structure, `docs.json`, MDX, components, skills, the admin MCP. | Mintlify's product docs |
| `mintlify` | Read/write. The admin MCP for this project: pages, navigation, `docs.json`, branches, publication, deployments. | This project's site |

**The `mintlify` admin MCP is the primary tool for every site operation** —
reading pages, inspecting navigation, editing content, publishing, and
verifying a deployment. The `mint` CLI has no `publish` command at all;
publication is an admin-MCP-only action.

The skill directory `mintlify-docs` is a repository-local skill. It is **not**
the `mintlify-docs` MCP server, and it is not a page on the published site.

## When to use this skill

Use it when the request touches any of:

- `docs.json`, `.mintignore`, `.mintlify/`, or the navigation tree
- a documentation page: `index.mdx`, a root-level `*.md`, or anything under `docs/`
- the published site (`https://docs.hashgrid.net`) and the agent skills it serves
- the `mintlify-docs` or `mintlify` MCP servers
- a request to audit, update, verify, release-sync, or publish the documentation

Do not use it for server code, MCP tools, or controller behaviour. Those are
covered by `skills/unifi-mcp-tool-builder/SKILL.md` and the tool-set skills.

## Required access

| Need | How | If missing |
|---|---|---|
| Mintlify product guidance | The `mintlify-docs` MCP server | Fall back to `https://www.mintlify.com/docs`, clearly labelled as the web fallback. Never invent Mintlify behaviour. |
| Read, edit and publish this project | The `mintlify` admin MCP, with `subdomain` set to this project | Report the blocker. Do not edit Git and the dashboard independently. |
| Build and link validation | `mint validate` and `mint broken-links` | See *Validation* below — these have no admin-MCP equivalent. |

### Resolving the project

Do not assume a subdomain. Resolve it, then confirm it belongs to this
repository:

```
mintlify.list_deployments()      -> [{subdomain, name, projectType}]
mintlify.list_branches(subdomain) -> {branches, deployBranch}
```

The deploy branch is `main`. The branch list matches this repository's
branches, and the site's content matches the files in the working tree — that
pair of checks is what identifies the project, not the display name.

`get_deployment_settings` and `list_repos_and_prs` need the
`deployment:read` scope. A connection without it returns
`insufficient_scope`; that is a scope limitation on the OAuth grant, not a
missing project.

## Repository discovery

Run this first. Every later step depends on it.

```bash
cd /home/elvis/projects/unifi-mcp-server

git remote -v                       # origin must be enuno/unifi-mcp-server
git rev-parse --abbrev-ref HEAD     # current branch
git rev-parse HEAD                   # commit under audit
git status -sb                       # must be clean, or say why not
```

Then read the site configuration:

- `docs.json` — theme, brand colours, logo, the navigation tree, navbar,
  footer, redirects, SEO and integrations. This is the site's structure.
- `.mintignore` — gitignore-style. It decides what is *not* published.
- `.mintlify/skills/` — the agent skills the site serves. Five entries are
  symlinks into `skills/`; `.mintlify/skills/unifi/SKILL.md` is a symlink to
  the root `SKILL.md`; `.mintlify/skills/mintlify-docs/` is a real directory
  whose source of truth is its own `SKILL.md`.
- `index.mdx` — the landing page. The only `.mdx` page in the repository.
- Root-level `*.md` — `API.md`, `SPEC.md`, `SECURITY.md`, `ROADMAP.md`,
  `NETWORK_PLAYBOOK.md`, `METRICS.md`, `A2A.md`, `WEBHOOK_SETUP.md`,
  `MULTI_CONTROLLER.md`, `HARBOR_SETUP.md`, `MCP_TOOLBOX.md`,
  `TEST_STRATEGY.md`, `commands.md`, `SKILL.md`.
- `docs/` — `docs/SKILLS.md`, `docs/UNIFI_API.md`, `docs/DISASTER_RECOVERY.md`,
  `docs/FLEET_SCALING_PLAN.md`, `docs/RELEASE_PROCESS.md`,
  `docs/AI-Coding/*`, `docs/deploy-prompts/*`.

**The documentation root is the repository root, not `docs/`.** Most pages are
root-level Markdown files that are published as pages. `docs/` holds a minority.

### What is published

Mintlify auto-ignores the root `README.md`, `LICENSE.md`, `CHANGELOG.md` and
`CONTRIBUTING.md` at *every* level, and `.gitignore`, `.github`, `.claude`,
`.agents`, `.cursor`, `.idea`, `.vscode`, `node_modules`. `.mintignore` adds
the internal agent instructions (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`), the
working documents (`DEVELOPMENT_PLAN.md`, `GAP_REPORT.md`, `TODO.md`,
`MAINTENANCE_POLICY.md`, `RELEASE_CHECKLIST.md`, `RELEASE_NOTES_0.2.5.md`),
`docs/archive/`, `docs/research/`, `.serena/`, `.analysis-reports/`,
`scripts/`, the Helm chart templates and CI files, the compose files, and
`*.yaml` / `*.yml`.

Two consequences that bite:

- **A root file named `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md` or
  `LICENSE.md` is unreachable as a page**, even though it is on disk. That is
  why the deployment pages were renamed to `overview.md` —
  `deploy/ansible/overview.md`, `deploy/helm/unifi-mcp/overview.md` and
  `docs/deploy-prompts/overview.md`. `docs.json` carries redirects for the
  four root files to their GitHub URLs.
- **Published URLs drop the file extension.** An internal link written as
  `page.md` or `../other/page.md` resolves to a path the site does not serve.
  Use site-root-relative paths (`/docs/page`) between published pages.

### Navigation and orphans

`docs.json` currently holds 30 pages across three tabs. The *Guides* tab
carries the landing page, the skills guide, the commands reference, the
network playbook, the metrics runbook, the disaster-recovery runbook and nine
Deployment pages. The *API reference* tab carries the API catalogue, the
UniFi API notes, the toolbox reference, the A2A and webhook guides, and the
specification, test-strategy, security and roadmap pages. The *Contributing*
tab carries the five AI-coding pages and the release process.

The page paths in `docs.json` are site paths, not file paths: the entry
`/docs/SKILLS` resolves to the file `docs/SKILLS.md`, and `commands` resolves
to `commands.md`. The admin MCP's `read` takes the site path, with or without
a leading slash.

The admin MCP's `list_nodes` with `type: "page"` returns the same 30 paths.
That equality is the check: the local `docs.json` navigation and the deployed
navigation must agree exactly.

Every navigation path must resolve to a real file that survives the ignore
rules. A path that exists on disk but is excluded is a build failure that reads
like a missing file.

Adding a page means three coordinated edits, not one:

1. the page file itself,
2. its `docs.json` navigation entry,
3. any inbound links, using the published path form.

`status` on the admin MCP reports `orphanCount` (currently 7 on `main`).
Those are files the build publishes but navigation does not reach — mostly the
`docs.md` Noridoc stubs under `src/` and `tests/`, and the developer skills
under `skills/` that are not symlinked into `.mintlify/skills/`. A new page
that is not added to navigation increases that count.

### The skills the site serves

Mintlify serves every directory under `.mintlify/skills/` to agents as a
skill. The published slug is the **frontmatter `name`**, so it must match the
directory name, and it must be unique: if two directories resolve to the same
slug, Mintlify publishes only one and warns in the deployment log. Slugs use
lowercase letters, numbers and hyphens only.

Verify what is actually served with a plain HTTP request — no login, no MCP:

```bash
curl -sSL -o /dev/null -w "%{http_code}\n" \
  https://docs.hashgrid.net/.well-known/skills/<slug>/SKILL.md
```

The path form that works is `/.well-known/skills/<slug>/SKILL.md`. The
directory index forms — `/.well-known/skills/`, `/.well-known/skills/<slug>`
and `/.well-known/agent-skills/` — all return 404 on this site. A 404 on the
per-skill path means the skill is not deployed yet, which is the expected
answer for a skill that exists only on a branch.

This site currently serves six skills: `unifi`, `unifi-channel-planning`,
`unifi-devices`, `unifi-network`, `unifi-security` and `unifi-system`.

### Mintlify parses `.md` with the MDX parser

Valid Markdown can still break the build. Three constructs are hazards:

- Markdown autolinks: `<https://example.com>` — write a normal link instead
- HTML comments: `<!-- ... -->` — write `{/* ... */}`
- a bare `<` followed by a digit: `<300 Mbps` — write "under 300 Mbps"

Braces and angle brackets **inside backtick code spans** are literal and are
not hazards. The CLI reports only the first MDX error per file, so scan every
candidate page for all three up front rather than fixing one build at a time.

## Evidence requirements

A technical claim in the documentation must trace to implementation. Before
changing one, inspect the code it describes. For this project, that means:

- **Exact tool names, signatures, defaults and return shapes.** Tools are
  plain `async def` functions in `src/tools/*.py`; there is no `@mcp.tool()`
  decorator. Read the function, not a summary of it.
- **Registration and availability.** A module is registered in
  `_LOCAL_TOOL_MODULES` or `_CLOUD_TOOL_MODULES` in `src/main.py`.
  `UNIFI_PROFILE` narrows the set via `_PROFILE_MODULES`. An unknown profile
  logs a warning and loads everything.
- **Read vs write.** Every tool carries `@read_tool` or `@write_tool` from
  `src/utils/tool_kind.py`. `UNIFI_READ_ONLY` registers only read tools;
  `UNIFI_DRY_RUN` forces dry runs. Write tools take `confirm` and `dry_run`,
  and call `validate_confirmation()` before any request.
- **Risk tiers and audit.** `tool_tier()` in `src/tool_registry.py` returns
  `read`, `write` or `destructive`. `delete_`, `remove_` and `bulk_delete_`
  prefixes and the `DESTRUCTIVE_TOOLS` set are destructive. Every mutating
  call is audited by the registry wrapper. Roles in `src/access.py` are
  `viewer`, `operator`, `admin` and `fleet-admin`, mapped to tiers by
  `ROLE_TIERS`.
- **API modes.** `local`, `cloud-v1` and `cloud-ea` (`APIType` in
  `src/config/config.py`). Local is the only mode with the full surface.
  `CLOUD` is a legacy alias for `cloud-ea`.
- **Environment variables.** 65 `validation_alias` values are defined in
  `src/config/config.py`. Read them there; `.env.example` is the documented
  list. Never invent a key.
- **Deployment interfaces.** `docker-compose*.yml`, `deploy/ansible/` and
  `deploy/helm/unifi-mcp/`.

### Distinguish four levels of truth

Keep these apart in the documentation and in any audit report:

1. **Planned** — in `DEVELOPMENT_PLAN.md` or `TODO.md`, not implemented.
2. **Implemented** — the code exists.
3. **Mock-tested** — unit-tested against a mocked controller. This proves the
   request shape, not that the endpoint exists on real firmware.
4. **Verified against a controller** — exercised on real hardware.

Level 3 is the ceiling for most of this project. Say which level applies.

### Counting tools

Count from the running server, not from a grep:

```bash
.venv/bin/python - <<'PY'
import os, asyncio
os.environ.update(UNIFI_API_KEY="x", UNIFI_API_TYPE="local", UNIFI_LOCAL_HOST="192.0.2.1")
import src.main as M
async def go():
    print("tools:", len(await M.mcp.list_tools()))
asyncio.run(go())
PY
```

This reports **343 in local mode** and **71 in cloud mode** — the figures
`README.md` and `docs/SKILLS.md` carry. The per-profile counts in
`docs/SKILLS.md` include the four fleet tools each profile also gets
(`fleet_health`, `fleet_sites`, `fleet_inventory`, `fleet_fanout`), which is
why they run ahead of the module-only numbers. A profile's count is its module
tools plus those four.

## Modes

The mode is the shape of the task. When the intent is unclear, use **audit**.

### audit

Read-only. Review the documentation against the implementation and, where
accessible, against the remote Mintlify content. Make no changes.

Resolve and read the remote site with the admin MCP:

- `list_deployments` — resolve the project
- `list_branches` — confirm the deploy branch and that the branches match
  this repository
- `read` with `path` — remote page content
- `search` with `query` — where a term appears remotely
- `list_nodes` with `type: "page"` — the deployed navigation tree
- `diff` and `status` — unpublished remote changes and the orphan count
- `deployment_status` — what is live, and from which commit

Then compare against the implementation as described under *Evidence
requirements*.

Report per claim: the claim, the source path and lines, and the verification
level. "No confirmed drift within the inspected scope" is a valid result.

### update

Prepare and apply a bounded, explicitly authorized documentation change.

1. Establish the scope, the relevant diff or release, and the exact target
   page or file.
2. Consult `mintlify-docs` for current guidance on anything Mintlify-specific.
3. Inspect the implementation the change describes, and the affected
   documentation.
4. Present a concise page-level change plan, including the navigation and
   link changes the new content implies.
5. Prepare the focused content change.
6. Validate it — see *Validation* below.
7. Apply it through the verified workflow — see *Applying changes*.
8. Read the result back and compare it with what was approved.
9. Publish only after explicit publication approval.

### verify

Validate an existing change without rewriting anything. Run the checks, report
each as passed, failed, blocked or not run, and stop at the first real failure.

### release-sync

Reconcile the documentation against an explicitly selected release or commit
range. Do not infer the release version from a single metadata file — confirm
it from the tag and the diff:

```bash
git tag --list 'v*' --sort=-v:refname | head -5
git diff --stat v0.6.1..HEAD -- '*.md' '*.mdx' docs.json
```

Check, for every changed surface: whether `API.md` describes the change, whether
`README.md` and `.env.example` still agree with `src/config/config.py`, whether
`CHANGELOG.md` has the entry, whether the version and tool counts across
`README.md`, `CLAUDE.md`, `docs/SKILLS.md` and `index.mdx` still agree, and
whether the navigation still resolves.

### publish

Publish an approved revision and verify the deployment. See *Publishing* below
— publication carries its own approval.

## Applying changes

### Through the admin MCP

The admin MCP's content tools take a `branch` on every call, and the server
does not remember a branch between calls.

- On the deploy branch (`main`), an edit lands as an **unpublished change**,
  visible to collaborators in the dashboard editor but not on the site.
- On any other branch, the edit goes through a pull request.
- `publish` is the only thing that makes a change live.

Content tools: `edit_page` (targeted replacements; the default), `write_page`
(whole-file replacement; slow for large pages and it resends the entire page),
`create_node` (a new page, group, tab, anchor, version, language or product),
`update_node`, `move_node`, `delete_node`, `update_config` (for `docs.json`
except `navigation`), and `suggest_edit` (a tracked suggestion a human accepts
or rejects; the page does not change until they do).

`edit_page` returns `notRendered` when the edit adds markup the editor drops
(`<script>`, `<style>`, `on*` handlers, non-literal JS expressions). Style with
Tailwind classes or Mintlify components instead.

**Project-management tools are different.** `update_deployment_settings`,
`manage_custom_domain`, `manage_git_source`, `manage_access_auth`,
`manage_workflow`, `manage_members_sharing` and `update_config` for
site-wide settings act on the live project immediately. They do not create a
branch or open a pull request, and there is no undo through the content flow.
Confirm the exact target, the current value, and the full argument set before
calling one.

### Through Git

Editing the files in a working tree and opening a pull request is the normal
path for a documentation change in this repository. A push to `main`
triggers a Mintlify deployment — that makes the push a **publication action**,
not just a Git action.

This repository's policy, from `AGENTS.md` and `CONTRIBUTING.md`:

- work on a branch; never commit to `main`
- one logical change per commit
- Conventional Commits: `docs: ...`, `feat(scope): ...`, `fix(scope): ...`
- `pre-commit run --files <changed files>` must pass
- never bypass branch protection, skip CI, or disable a hook
- a pull request needs one human approval, passing CI, and no unresolved
  review comments

Because `docs.json` is the authority for the site, re-validate after any
change to it — including one that arrived through a pull or a rebase.

### Do not edit both surfaces

Do not independently edit Git and the dashboard. The admin MCP commits to the
same repository; a local edit plus a remote edit to the same page produces two
sources of truth for one file. Pick one surface for a given change.

## Approval boundaries

Administrative access is a capability, not an authorization. Two separate
approvals are required, and they are not interchangeable:

| Action | Approval needed |
|---|---|
| A content write (edit, create, delete, `docs.json` change) | Approval for that exact page, that exact content |
| A project-management write (settings, domain, git source, auth, automation) | Approval for that exact setting and its full argument set |
| `publish` | **Separate** publication approval, naming the revision |
| A Git push to `main` | Git approval — and it is also a publication, because it triggers a deploy |
| Any controller mutation | Out of scope. Never run one as a documentation test. |

Before a remote content write:

1. Resolve the exact account, project, environment, and page or file.
2. Read the current content and the revision.
3. Check for concurrent changes — `diff` and `status` on the branch.
4. Present the exact content or patch and the complete tool arguments.
5. State whether the action is draft-only or immediately public.
6. Obtain explicit approval for that action.

Use conditional or version-aware updates where the tool supports them. Do not
overwrite a concurrent edit silently.

After a write:

1. Read the content back.
2. Compare it with the approved content.
3. Record the returned revision or change identifier.
4. Verify Git synchronisation where applicable.
5. Report whether the result is a draft or publicly visible.

**If a content-update tool publishes automatically, that write is a publication
action** and needs publication approval before it is called.

## Publishing

Publication is a separate step with a separate approval. The `mint` CLI has no
`publish` command; `publish` on the admin MCP is the only way to make a change
live.

Before publishing:

1. Identify the exact target and the revision or content snapshot.
2. Present the validation results and any unresolved blockers.
3. Identify unrelated pending changes that the publication might include —
   `status` and `diff` on the branch.
4. Determine whether publication is site-wide or revision-scoped.
5. Record the current live revision and the recovery options. `discard` reverts
   your own unpublished changes on the deploy branch, and deletes a branch you
   created elsewhere. Anything else needs a human with dashboard access.
6. Present the exact publishing tool and its complete arguments.
7. Obtain explicit approval.

`publish` takes `branch` and `title`, and optionally `body` and `merge`. On the
deploy branch it commits your own unpublished changes. On another branch it
commits and opens or returns that branch's pull request; `merge: true` also
merges it when the deploy branch would accept direct edits, and otherwise
returns `merge_not_allowed` and leaves the pull request open. `publish` with
nothing to commit returns `no_pending_changes`.

**Do not publish unrelated unapproved content.** Stop if the intended revision
cannot be isolated, or if its contents cannot be established.

After publishing:

1. Capture the actual deployment and revision identifiers.
2. Poll `deployment_status` with the returned `commitSha`, about every 30
   seconds, until `live` is true — or stop on `failed`, `not_live` or
   `skipped` and report the `message`.
3. Distinguish "publication requested" from "deployment succeeded". A
   `commitSha` is not a live site.
4. Verify the changed public pages over HTTP at their real URLs, and re-read
   them with the admin MCP's `read` to confirm the published content.
5. Report failures and uncertainty accurately.

Do not invent deployment URLs, tool names, identifiers or successful outcomes.

## Validation

Discover the checks first; do not assume `package.json` defines them. It does
not — it carries only the `posthog-node` runtime dependency. The Python
project's tooling lives in the `Makefile` and `pyproject.toml`.

### Mintlify checks

**The admin MCP is the primary surface, including for validation.** Use it for
every site-state question: which pages are deployed, what the navigation
resolves to, whether unpublished changes exist, and whether a revision went
live. Where the MCP answers a question, prefer it over the CLI.

Two checks have **no admin-MCP equivalent** — Mintlify's build validator and
link checker exist only in the `mint` CLI. Use them for those two, and only
those two. They are local, read-only, and need no login, so they work when the
CLI is not authenticated. `mint` is at `/usr/local/bin/mint` (v4.2.1124).

```bash
cd /home/elvis/projects/unifi-mcp-server
mint validate        # strict build + schema; exits non-zero on warnings or errors
mint broken-links    # internal link graph
```

Both work **without** a login. `mint validate` also reports the OpenAPI
categorisation warning for the Helm templates — that warning is expected and
does not fail the build.

`mint broken-links` takes optional flags that are off by default and worth
knowing about:

| Flag | Effect |
|---|---|
| `--check-anchors` | also validate `#section` links against heading slugs |
| `--check-external` | also check external links for broken URLs |
| `--check-snippets` | also check links inside `<Snippet>` components |
| `--check-redirects` | also check that `docs.json` redirect destinations resolve |

`--check-external` sends requests to third-party hosts. Use it only against
approved public destinations, never a private host or a URL carrying
credentials. **Internal-link checks are not external-URL checks.**

`mint a11y` also runs without a login and checks MDX accessibility.
`mint score` needs a URL and, for this project, a login.

### Remote checks through the admin MCP

These are the site-state checks the CLI cannot make:

```text
mintlify.list_nodes(type="page")   -> deployed navigation paths
mintlify.read(path=...)             -> deployed page content
mintlify.search(query=...)         -> where a term appears on the site
mintlify.diff() / .status()         -> unpublished changes, orphan count
mintlify.deployment_status()        -> what is live, and from which commit
```

### Repository checks

```bash
make lint            # black --check, isort --check-only, ruff
make typecheck       # mypy over src/
make security        # bandit
make docs-coverage   # interrogate docstring coverage
make test            # pytest tests/unit/
make ci              # every blocking CI check
```

The environment is `uv`-managed:

```bash
uv sync --frozen --python 3.12 --extra dev --extra fleet
```

Use Python 3.12. `pgserver` (a dev dependency) has no cp313 or cp314 wheel, so
`uv sync` fails on a newer interpreter. CI itself runs 3.10, 3.11 and 3.12.

### Skill and agent-documentation checks

```bash
.venv/bin/pytest tests/unit/test_agent_docs.py -q
```

This checks that the agent-directory copies of the developer skills are
identical to `skills/<name>/SKILL.md`, that each `skills/<name>/SKILL.md` has
frontmatter naming its folder, and that `CLAUDE.md`, `AGENTS.md` and the
tool-set skills cite only paths, links and names that exist. Run it after
editing any skill or agent guidance file.

### Pre-commit

```bash
pre-commit run --files <changed files>
```

The repository's `.pre-commit-config.yaml` runs black, isort, ruff, mypy,
bandit, markdownlint, yamllint, `check-yaml`, `detect-secrets` and a
Conventional Commits `commit-msg` hook.

The mypy hook fails with "Duplicate module named src" when you pass file
names, because it passes `src` in `args` and pre-commit adds the file names
too. Use `make typecheck` instead of the mypy hook. `markdownlint` reports
MD024 on `CHANGELOG.md`; that error is already on `main`.

### Preview

```bash
mint dev --no-open
```

Bind the preview to loopback, and stop the process when you are done.

### Record the results

For every check, record: the command or MCP call verbatim, the exit status or
error, what the output said, and the scope it covered. Distinguish **passed**,
**failed**, **blocked**, **not run**, and **scenario-reviewed only**. Do not
claim a check passed unless it ran successfully.

## Failure handling

| Symptom | Meaning | Action |
|---|---|---|
| `mint status` says not logged in | The keyring holds no `mintlify` entry for the current OS user | Use the admin MCP, which is the primary surface. A CLI login elsewhere is invisible here. |
| Admin MCP returns `insufficient_scope` | The OAuth grant lacks a scope | Report it. Do not work around it with a Git-side edit. |
| Admin MCP `read` returns `read_failed` | No such page on that branch | The path does not resolve, or it resolves to a file the ignore rules exclude. Check the file exists *and* is not excluded. |
| `mint validate` reports a missing nav page | The path does not resolve, or resolves to an excluded file | Rename an auto-ignored `README.md` to `overview.md`. |
| `mint validate` reports an MDX error | The Markdown parser rejected a construct | Rewrite the autolink, the HTML comment, or the bare `<digit`. Check the file for the other two hazards too. |
| `mint broken-links` reports a broken link | An internal link points at a path the site does not serve | Use the published path form (`/docs/page`), not `page.md`. |
| `publish` returns `no_pending_changes` | Nothing was staged | Verify the edit landed with `diff` and `status`. |
| `publish` returns `branch_protected` | The deploy branch now requires a pull request | Open a branch with `create_branch` and work there. |
| `deployment_status` stays `pending` | The deploy has not started | Check again in about 30 seconds. Bounded polling, not a loop. |
| `deployment_status` returns `failed` or `not_live` | The deploy failed | Report the `message`. Do not retry indefinitely. |
| The remote `read` differs from the local file | Either a real drift, or a formatting difference | The admin MCP returns reflowed Markdown; the published `.md` export adds a banner and reflows headings. Compare meaning, not bytes. |

## What to preserve

- The current information architecture, brand colours, logo and theme in
  `docs.json`
- Stable routes: the `redirects` array is the contract for old paths
- GitHub compatibility for dual-purpose Markdown files — a root-level `.md`
  must still read correctly on GitHub
- The existing navigation and component conventions: `CodeGroup`, `Card`,
  `CardGroup`, `Note`, `Tip`, `Warning`, `Accordion`, `Tabs`
- The rule that Mintlify's auto-ignored names are never used for a published
  page

Update navigation, redirects, assets, snippets, configuration examples, API
documentation, changelog entries and related skills only as the actual change
requires, and only as repository policy requires.

**Update generators rather than hand-editing generated output.** In this
repository the generated artifacts are the API-spec snapshots under `scripts/`
(`scraped-api-spec-v10.6.106.json` and the Protect, Mobility, InnerSpace and
Carrier Fabric specs), produced by `scripts/fetch-specs.sh`. Edit the scraper,
not the JSON.

Examples in the documentation must use placeholders such as
`UNIFI_API_KEY=your-api-key`, and mutating operations must be labelled as
mutating. **Never execute a controller mutation as part of documentation
maintenance.**

## Sources consulted

Inspected 2026-10-24.

- **Mintlify product documentation**, via the `mintlify-docs` MCP server:
  `/ai/skillmd` (custom skill files, `.mintlify/skills/`, the symlink pattern,
  frontmatter fields, the discovery endpoints), `/ai/mintlify-mcp` (the admin
  MCP: read-only versus content tools versus project-management tools, the
  branch model, `publish`, `deployment_status`, credentials), `/ai/model-context-protocol`
  (the search MCP and skills as MCP resources), `/assistant/skills` (writing
  effective skills), `/editor/agent` (adding a skill), `/guides/codex` and
  `/guides/claude-code` (the CLI workflow, `mint validate` and
  `mint broken-links`).
- **This repository**: `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`,
  `docs.json`, `.mintignore`, `.mintlify/`, `index.mdx`, `docs/SKILLS.md`,
  `commands.md`, `Makefile`, `package.json`, `pyproject.toml`, `pytest.ini`,
  `.pre-commit-config.yaml`, `.github/workflows/`, `tests/unit/test_agent_docs.py`,
  `src/main.py`, `src/tool_registry.py`, `src/access.py`, `src/utils/tool_kind.py`,
  `src/config/config.py`, `src/fleet/fleet_tools.py`, `src/fleet/tools.py`,
  and the `skills/`, `.claude/skills/` and `.agents/skills/` trees.
- **The deployed site**, read-only: `https://docs.hashgrid.net`,
  `https://docs.hashgrid.net/skill.md`, `https://docs.hashgrid.net/llms.txt`,
  and `https://docs.hashgrid.net/.well-known/skills/<slug>/SKILL.md` for each
  of the six published skills. The `mintlify` admin MCP's
  `list_deployments`, `list_branches`, `read`, `search`, `list_nodes`,
  `diff`, `status` and `deployment_status`.

## Example invocations

- "Audit this project's Mintlify documentation against the current code."
- "Update the documentation for this diff, but do not publish."
- "Document this tool and its configuration."
- "Prepare documentation changes for release v0.6.1."
- "Publish the approved documentation revision."
- "Verify the published documentation matches the approved changes."
