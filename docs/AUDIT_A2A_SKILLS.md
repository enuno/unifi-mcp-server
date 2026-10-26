# A2A and skills audit — implementation baseline

Audit date: 2026-10-26. Branch `feature/native-mcp-prompts`, base `origin/main`
(commit `b9f65dd`).

Every finding below was confirmed with executable probes against the working
tree, not read from documentation.

## 1. Method

The tool inventory is the ground truth. It was read from the live FastMCP
component store, which is what the server actually exposes:

```bash
unset PYTHONPATH; cd /home/elvis/projects/unifi-mcp-server-prompts
UNIFI_API_KEY=*** UNIFI_API_TYPE=local UNIFI_LOCAL_HOST=192.0.2.1 \
AGNOST_ENABLED=false ./.venv/bin/python -c "
import src.main as M
print(len([k for k in M.mcp._local_provider._components if k.startswith('tool:')]))"
```

Local mode registers 343 tools from 60 modules; cloud mode registers 71. The
tier of every tool is in `src/tool_registry.py:TOOL_TIERS`, which is populated
at registration and is the same source the A2A safety layer and the tool
wrapper consult.

## 2. A2A baseline

### 2.1 What the project actually targets

**The project does not implement the A2A protocol.** There is no `a2a-sdk`
dependency in `pyproject.toml` or `uv.lock`, and the served endpoints are a
bespoke JSON-over-HTTP shape, not the A2A JSON-RPC binding:

| A2A operation (spec 0.3.0) | Present |
|---|---|
| `message/send` | No |
| `message/stream` | No |
| `tasks/get`, `tasks/cancel`, `tasks/resubscribe` | No |
| `tasks/pushNotificationConfig/*` | No |
| `GET /.well-known/agent-card.json` | No |
| `A2A-Version` header | No |
| Task/Message/Part/Artifact data model | No |

The surface is `GET /a2a/agent-card`, `POST /a2a/discover`, `POST /a2a/delegate`,
`POST /a2a/confirm`, `GET /a2a/audit` (`src/main.py:334-339`). It is a
capability-discovery and delegation facade, and the repository's own `A2A.md`
describes it that way. The A2A spec's `AgentCard` object shape (§5.5) is a
reasonable target for the *card document* even without the task protocol, so
this work aligns the card with the spec's field names while keeping the
existing transport and route names.

`SPEC.md:133-142` ("A2A discovery") requires a repository-root
`agent-card.json` and a `.well-known/agent-card.json` endpoint when HTTP
transport is enabled. The first exists; the second does not.

### 2.2 Implemented and tested

- The five `/a2a/*` routes are registered only on the network transports
  (`src/main.py:1037`), never on stdio.
- Every `/a2a/*` route is behind the same bearer token as `/mcp`
  (`src/main.py:289-311`). A missing or wrong token is answered `401` with a
  `WWW-Authenticate: Bearer` header.
- `build_agent_card()` (`src/a2a/agent_card.py:223`) builds skills, resources
  and safety requirements from the **live** component store, so it matches the
  tools this deployment registered. Confirmed: 343 skills in local mode.
- The tool tier used for authorization and safety comes from `TOOL_TIERS`, the
  same registry the tool wrapper uses (`src/a2a/auth.py:176`,
  `src/a2a/route_policy.py:140`).
- `src/a2a/route_policy.py` applies a per-tool rate limit, a risk
  classification and a confirmation requirement before a delegated call runs.
- `agent-card.json` at the repository root is checked against the served card
  by `tests/unit/a2a/test_agent_card.py:377`.

### 2.3 Implemented but insufficiently tested or documented

- **`GET /a2a/agent-card` and `POST /a2a/discover` return two unrelated
  documents.** `get_agent_card_handler()` (`src/a2a/http_handlers.py:85`)
  returns a hand-maintained summary with a static `capabilities` list; the
  richer `build_agent_card()` is never called by any route.
  `A2A.md:16` claims `/a2a/discover` returns "the full card from
  `build_agent_card()` ... built from the live tool registry". That is false
  today: `discover_handler()` (`src/a2a/http_handlers.py:111`) returns a
  hardcoded three-entry `skills` list (`read-network-state`,
  `mutate-network-state`, `destructive-operations`) that does not correspond
  to any registered tool, and contains no live tool names at all. Confirmed by
  probe: `"network_health_check" in str(manifest)` is `False`.
- **The summary card's `capabilities` list is static and not derived from the
  deployment.** It always advertises `network-management`, `multi-site`,
  `audit-log`, `safety-controls`, `multi-auth` regardless of the API mode,
  the profile, the read-only setting or the registered tool set.
- **The summary card advertises `authentication.modes` as all three API
  types** (`local`, `cloud-v1`, `cloud-ea`) regardless of the running mode.
- **`authenticationMode` is always `BOTH`**
  (`src/a2a/agent_card.py:191-199`): every branch returns `BOTH`.
- **`get_agent_card_handler()` exposes no `skills`, no `url` and no
  `securitySchemes`.** A client cannot learn the tool surface or the
  preferred endpoint from the card it is given.
- **The `protocol` field says `"MCP/1.0"`**, which is not an A2A protocol
  version and not the MCP protocol version either.
- **The A2A `AuthManager` and the server's real RBAC are two separate
  systems.** `src/a2a/auth.py` derives permissions from the `auth` block in
  the request body — a caller-asserted field — while the enforced boundary is
  `src/access.py`, which binds a `Principal` to the request and checks
  `ROLE_TIERS`. Confirmed by probe: a body carrying
  `{"permissions": ["destructive", "admin"]}` satisfies
  `AuthManager.validate_permissions` for a `create_` tool. The A2A layer
  therefore grants more than the server's role model would, and
  `/a2a/audit` is documented as `requiredAuth="admin"` in the route policy
  (`src/a2a/route_policy.py:117`) but the HTTP route never checks the
  role — a `viewer` token is answered `200` with the audit trail.
- **The `delegate` route cannot execute a tool.** `A2AState.tool_executor` is
  `None` in the `main.py` wiring (`src/main.py:1020-1026`), so
  `delegate_handler` returns `{"status": "accepted", "message": "no tool
  executor configured"}` for every call. A2A.md:17 advertises "Delegated tool
  calls".
- **`/a2a/confirm` cannot complete anything.** `confirm_handler`
  (`src/a2a/http_handlers.py:236`) verifies the token and expires it; it
  never executes the confirmed call, and the confirmation token stores only a
  `params_hash`, not the parameters (`src/a2a/route_policy.py:46-56`). A
  confirmed destructive call is therefore acknowledged and dropped.
- **The `delegate` confirmation path is unreachable.** `AuthManager` grants
  only `{"read"}` for a request with no credentials, so a mutating tool is
  refused with `insufficient permissions` before the safety check that would
  issue a confirmation token.
- **`/a2a/audit` has no role check** (see above).
- **`_is_destructive_tool` in the agent card is a heuristic**
  (`src/a2a/agent_card.py:126-152`) that scans names and descriptions, while
  the authoritative tier is `TOOL_TIERS`. The two can disagree, so the card's
  `safetyRequirements` need not match the tier the server enforces. The
  `_SENSITIVE_FIELD_NAMES` set also contains `ssid` and `description`, which
  are not secrets, and matches by substring, so `ssid_name` is reported as a
  sensitive field.

### 2.4 Documented but unimplemented (all resolved in this change)

| Claim | Where | Was | Now |
|---|---|---|---|
| `/a2a/discover` returns the live-registry card | `A2A.md:16` | Returned a hardcoded three-entry list with no real tool names | Returns the card plus the per-domain inventory and the tool counts, all derived from the live registry |
| `/a2a/delegate` performs delegated tool calls | `A2A.md:17` | No executor was wired; every call returned "no tool executor configured" | Runs the registered tool through its own wrapper, so the role check, `confirm` gate, dry-run and audit all apply |
| `/a2a/confirm` is the confirmation step | `A2A.md:17` | Verified and discarded the token; the confirmed call was never run | Runs the call the token authorises; the token is bound to a hash of its parameters and expires |
| `.well-known/agent-card.json` endpoint | `SPEC.md:140` | Not served | Served, behind the same bearer token as the other routes |
| `agent-card.json` matches the served card | `A2A.md:53` | True only because both were static; it could not detect tool-surface drift | The artifact is the reference card for a default deployment, checked against the builder; the served card legitimately varies with the configuration |

### What was changed, and why

- **`src/a2a/capabilities.py` (new).** The single source of truth. It reads
  the live FastMCP component store and `TOOL_TIERS` and derives the tool
  counts, the capability domains, the API mode, the read-only, dry-run and
  fleet flags, the advertised URL and the security schemes. The card, the
  discovery manifest and the repository artifact all come from it.
- **`src/a2a/agent_card.py` (rewritten).** Emits the A2A 0.3.0
  `AgentCard` shape. The safety requirements now come from the tool
  registry's tier, so the card cannot call a tool safe that the server
  would refuse. The card no longer carries the controller address, and a
  credential parameter's example is a redaction placeholder.
- **`src/a2a/executor.py` (new).** Runs a registered tool through its
  registered wrapper. That is what keeps the delegation path identical to
  the MCP path.
- **`src/a2a/auth.py`.** The permissions now come from the caller's
  authenticated role. The role table mirrors `src.access.ROLE_TIERS`.
- **`src/a2a/route_policy.py`.** `ConfirmationWorkflow` keeps the pending
  call, so an approved confirmation can execute it.
- **`src/a2a/http_handlers.py` (rewritten).** A delegation that cannot run
  answers `unavailable`, never `ok`.
- **`src/main.py`.** The A2A state carries the MCP server and the
  executor; the caller's role is resolved from the verified token and bound
  to the request; `/a2a/audit` requires the `admin` role.
- **`src/tool_registry.py`.** `_request_ids()` guarded the lookup of the
  request context but not the read of the session id, so a tool called
  outside an MCP session raised `RuntimeError`. Both ids are now optional.

### Security findings resolved

| Finding | Resolution |
|---|---|
| The A2A layer derived permissions from a permission list in the request body, so a caller could assert `destructive` access | The permissions come from the bearer token's role; a payload's `scopes` can only narrow them |
| `/a2a/audit` was documented as `requiredAuth="admin"` but had no role check | The route now requires the `admin` role and answers `403` otherwise |
| The card's safety requirements used a name heuristic, disagreeing with the registry's tier | The tier comes from `TOOL_TIERS` |
| The card listed `ssid` and `description` as sensitive fields | Only real credential parameter names are listed, matched on the whole name |
| The card carried the controller's address | The address is not in the card; a test enforces it |
| The card's examples contained password-looking values | A credential parameter's example is a redaction placeholder |

### 2.5 Proposed (not implemented, decided against in this change)

- A full A2A JSON-RPC task protocol (`message/send`, task lifecycle,
  streaming, push notifications) would require adopting the `a2a-sdk`
  dependency and reworking the delegation path around Task objects. That is a
  substantial architectural change with no direction in the repository, so it
  is **not** implemented and **not** advertised. The agent card declares
  `streaming: false` and `pushNotifications: false` to say so explicitly.
- Task cancellation and status reporting have no implementation and no
  advertised equivalent.

## 3. Skills baseline

Ten skills under `skills/`, each a `SKILL.md` with YAML frontmatter. Five are
operator-facing (`unifi-channel-planning`, `unifi-cloud-fleet-tools`,
`unifi-devices`, `unifi-network`, `unifi-security`, `unifi-system`) and
developer-facing for the tool-set mechanics (`unifi-mcp-tool-builder`,
`unifi-network-config-tools`, `unifi-protect-tools`, `unifi-security-tools`).

### 3.1 Inaccurate references (confirmed against the live registry)

| File | Line | Claim | Reality |
|---|---|---|---|
| `skills/unifi-security/SKILL.md` | 78-82 | `get_zbf_matrix`, `get_zone_policies`, `get_zone_matrix_policy`, `update_zbf_policy` | None exist. The real names are `get_zone_policy_matrix`, `get_firewall_policy`, `list_firewall_zones_v2`, `update_firewall_policy` |
| `skills/unifi-security-tools/SKILL.md` | 8 | "see `zbf-implementation-guide.md` **in this folder**" | The file is not in `skills/unifi-security-tools/`; it is in `.claude/skills/` |
| `skills/unifi-mcp-tool-builder/SKILL.md` | 13 | "extending the current 74-tool implementation" | The server registers 343 tools in local mode |
| `skills/unifi-system/SKILL.md` | 147 | `create_radius_profile` example implies a name only | `create_radius_profile` requires `name`, `auth_server` and `auth_secret`; the secret is mandatory |
| `skills/unifi-system/SKILL.md` | — | "Create traffic route" | No traffic-route creation tool exists; `src/tools/qos.py` exposes `list_traffic_routes` (read) and `configure_smart_queue` only |

### 3.2 Coverage

239 of 343 tools are named by at least one skill. 104 are not named by any.
The uncovered set is concentrated in the cloud-only modules
(`site_manager`, 40 tools), the Protect modules (40 of 71 Protect tools), and
the carrier/connector/mobility/innerspace cloud tools.

### 3.3 Missing high-value workflows (all closed in this change)

| Workflow | Before | Now |
|---|---|---|
| Discovery and inspection: what the server exposes, which mode, which profile | No skill; `health_check` named by none | `unifi-discovery` |
| Deployment-mode selection: local vs cloud vs fleet | Scattered across the operator skills | `unifi-discovery` |
| Authentication and connectivity diagnostics | Only the developer skills | `unifi-discovery`, `unifi-fleet-operations` |
| Safe handling of state-changing operations | The operator skills mark `(requires confirm=True)` inconsistently | `unifi-safe-changes` |
| Fleet operation from the operator's side | `unifi-cloud-fleet-tools` is developer-facing | `unifi-fleet-operations` |
| Protect operation for an operator | `unifi-protect-tools` is developer-facing | `unifi-protect` |
| Keeping MCP tools, A2A capabilities and skill docs synchronized | Nothing | `unifi-docs-sync` |

### 3.4 The coverage matrix

| Domain | Tools | Skill coverage | Audience | Gap found | Resolution |
|---|---|---|---|---|---|
| Network config | networks, VLANs, WiFi, WAN, DHCP, DNS, QoS, port profiles, switching, VPN | `unifi-network`, `unifi-network-config-tools` | Both | — | — |
| Clients | client management, clients, DHCP, vouchers | `unifi-network` | Ops | — | — |
| Devices | inventory, adoption, device control, diagnostics, switching, topology, port profiles | `unifi-devices` | Ops | — | — |
| Security | firewall, groups, ZBF, ACL, matching lists, content filtering, port forwarding, RADIUS, guest portal | `unifi-security`, `unifi-security-tools` | Both | **7 tool names did not exist**; a broken file reference | Corrected to the real names; reference repointed |
| System | sites, backups, QoS, traffic flows, DPI, reference data, site manager | `unifi-system` | Ops | A traffic-route creation tool was prescribed that does not exist; a RADIUS profile example omitted its mandatory `auth_secret` | Both corrected; the absent capability is now stated explicitly |
| Protect | 71 tools across 15 modules | `unifi-protect-tools` (dev only) | Dev | **40 of 71 Protect tools had no operator coverage** | `unifi-protect` added |
| Cloud | Site Manager, connector, Mobility, InnerSpace, Carrier Fabric (40 tools) | `unifi-cloud-fleet-tools` (dev only) | Dev | No operator coverage for the cloud-only domains | `unifi-discovery` covers mode selection; the per-tool cloud surface remains developer-facing |
| Wireless planning | channel planning | `unifi-channel-planning` | Ops | — | — |
| Fleet | registry, tokens, snapshot and fan-out tools | `unifi-cloud-fleet-tools` (dev only) | Dev | No operator view | `unifi-fleet-operations` added |
| Discovery / A2A | the agent card, the manifest, delegation | None | Dev | Nothing documented the A2A surface or how it relates to the tools | `unifi-discovery` (operator) and `unifi-docs-sync` (developer) |
| Prompt catalog | `src/prompts/catalog.py` | None | Dev | The catalog hardcodes tool names, so a rename silently breaks a workflow | `unifi-docs-sync` documents the coupling; `tests/unit/prompts/test_prompt_catalog.py` checks every name |

The cloud-only per-tool surface (40 Site Manager, connector, Mobility,
InnerSpace and Carrier Fabric tools) remains developer-facing. An operator
skill for it would need per-tool detail that the developer skill already
holds, and duplicating it would create a second copy to keep in sync — the
exact defect class this work removes. It is recorded here as a deliberate
decision rather than an oversight.

### 3.4 Skill conventions

- Frontmatter: `name` (kebab-case, equal to the directory name, `unifi-`
  prefix) and `description` (one sentence, capitalised, trailing period).
  Operator descriptions carry a "Use when …" trigger; developer descriptions
  carry "Use when adding, changing or testing …". Only
  `unifi-mcp-tool-builder` has `license`, `version` and `author`.
- Directory naming: `unifi-<domain>` for operator skills,
  `unifi-<domain>-tools` for developer skills.
- `AGENTS.md:240` requires a skill changed in `skills/<name>/` to be copied to
  `.claude/skills/<name>/` and `.agents/skills/<name>/`;
  `tests/unit/test_agent_docs.py:155` fails when a copy differs.
- `tests/unit/test_agent_docs.py:141` fails when a skill's frontmatter `name`
  does not equal its folder, and `:128` fails when a skill cites a path, link
  or tool name that does not exist.

## 4. Verification

Everything below was run in the working tree, with the project's own
tooling, against the mocked or local configuration. No live controller, no
production credential and no gateway change was involved.

| Check | Command | Result |
|---|---|---|
| Unit tests | `pytest tests/unit/ -q` | 7,184 passed, 0 failed |
| A2A suite | `pytest tests/unit/a2a/ -q` | 473 passed |
| Prompt suite | `pytest tests/unit/prompts/ -q` | 108 passed |
| Skill reference guards | `pytest tests/unit/test_skill_tool_references.py tests/unit/test_skill_parameter_references.py -q` | 85 passed |
| Documentation and skill copies | `pytest tests/unit/test_agent_docs.py -q` | 41 passed |
| Coverage gate | `pytest tests/unit/ --cov=src --cov-fail-under=80` | 94.27% against the 80% gate |
| Formatting | `black --check src/ tests/` | clean |
| Import order | `isort --check-only src/ tests/` | clean |
| Lint | `ruff check src/ tests/` | clean |
| Type check | `mypy src/` | clean, 194 source files |
| Security scan | `bandit -r src/ -ll -q` | no medium or high findings |
| Docstring coverage | `interrogate src/tools/ src/api/ --fail-under 80` | 98.4% |
| Pre-commit | `pre-commit run --files <changed>` | all hooks pass |

### Parameter-level skill defects, and the guard that now catches them

A second, independent audit cross-referenced every parameter name a skill
states against the tool's live input schema. A skill can name a tool that
exists and still get its arguments wrong; the operator then fails at the
controller rather than at the schema check. The following were confirmed by
reading the registered schema and are now corrected:

| Skill | Claimed | Actual schema |
|---|---|---|
| `unifi-network` | `create_vouchers` takes "duration" and "quota" | `time_limit_minutes` and `data_usage_limit_mb`; `name` and `time_limit_minutes` are required |
| `unifi-network` | `authorize_guest` by MAC, for hours, in GB | `client_id`; `duration` is **seconds**; `data_usage_limit_mbytes` is **MB** |
| `unifi-network` | `get_network_statistics` per network | takes `site_id` only |
| `unifi-devices` | port override takes "port" and "profile" | takes `device_id` and a `port_overrides` list |
| `unifi-devices` | `adopt_device` takes `device_mac` | takes `mac`; the other device tools use `device_mac` |
| `unifi-security` | port forward example omits the name | `name` is required alongside `dst_port`, `fwd_ip`, `fwd_port` |
| `unifi-system` | `block_flow_application` takes a category and a zone | takes `flow_id` and an optional duration; it blocks the destination of one flow |
| `unifi-mcp-tool-builder` | "74 MCP tools", "990 tests", 78.18% coverage | 343 tools; the test count and coverage now point at the command that reports them, because both change with every change |
| `unifi-mcp-tool-builder` | `tests/unit/test_devices.py` | `tests/unit/tools/test_devices_tools.py` |
| `unifi-protect-tools` | 72 functions, `protect_events` has 7 | 71 functions, `protect_events` registers 6 |

`tests/unit/test_skill_tool_references.py` also compares any tool count or
module count a skill or the README states with the live registry, so a
figure in prose cannot go stale silently. The tool builder skill's test
count and coverage now point at the command that reports them instead of
quoting a number that changes with every change.

`tests/unit/test_skill_parameter_references.py` now checks every skill
against the live schema. It reads an explicit argument list, so prose that
mentions a response field, a function name, or a contrasting spelling is not
mistaken for an argument claim. The guard was verified by injecting a wrong
parameter name into a skill and confirming the test failed on it.

### A pre-existing mypy failure in the skill copies

`pre-commit run mypy --all-files` fails with "Duplicate module named
`connections`" because `.claude/skills/mcp-builder/scripts/connections.py`
and `.agents/skills/mcp-builder/scripts/connections.py` are the same module
under two names. This is **pre-existing** and outside this work: it
reproduces with the skill copies reverted, and it is not in any file this
change touches.

It does not affect CI, because the CI lint job runs `mypy src/`, not
`mypy --all-files`. The full CI lint gate was run directly and passes:
`black --check src/ tests/`, `isort --check-only src/ tests/`,
`ruff check src/ tests/`, `mypy src/`, and `bandit -r src/ -ll`.

### A privilege escalation found in review, and closed

The A2A confirmation path had a real authorization gap, found by reviewing
the finished diff rather than by the tests that were already there.

`POST /a2a/confirm` executed the held call without re-checking who was
asking. The confirmation token was the only thing that had to be right, and
a token is a bearer capability: it can be handed to another caller, and the
role that requested the call may be the only reason the call was allowed at
all. A **viewer** could redeem an admin-issued token and run a destructive
tool, even though the same viewer's own delegation was correctly refused.

The handler's own docstring claimed the authorization and safety checks were
applied "again at that moment". They were not. The handler now derives the
confirming caller's role from the bearer token exactly as the delegation
path does, and refuses the confirmation when that role does not grant the
tool. The legitimate path is unchanged: the admin who requested a call can
still confirm it.

`tests/unit/a2a/test_a2a_http_endpoints.py::TestConfirmationReauthorizes`
covers both directions.

### A tool's tier must not depend on its name

The A2A layer resolved a tool's risk tier from `TOOL_TIERS`, with a
name-prefix heuristic for names the table does not hold. Four registered
tools are absent from that table, because the fleet tools and the health
check register by another path: `list_controllers`,
`select_controller`, `get_active_controller` and `health_check`. For those
the tier came from the name, so the same tool could be classified
differently depending on how it was spelled.

The A2A layer now resolves a tool's tier from the tool's own function,
classified with the registry's own classifier, which is the same thing the
MCP path does. The lookup is against the live server, so a tool registered
after startup is classified correctly too.

The result is that **all 343 registered tools carry the same tier in both
paths**; the mismatch count is zero. A tool's tier decides what role may
call it, so a difference between the paths would mean the same tool was
reachable over one interface by a weaker role than the other.
`tests/unit/a2a/test_a2a_authorization.py::TestTierParityWithTheRegistry`
fails if that ever stops being true.

### The card advertised a tier other than the enforced one

The same review found the card and the capability manifest resolving a
tool's tier separately from the authorization path. They could therefore
disagree, and they did: for the four tools the tier table does not cover,
the card said `destructive` while the server enforced `write`. A client
reading the card would have refused calls the server allows, and a client
trusting the card's "destructive" list would have over-protected itself
about four harmless tools.

Both now use one resolver, so the advertised tier is the enforced tier.
The counts move from 204 read / 86 write / 53 destructive to 204 / 90 / 49.
`tests/unit/a2a/test_agent_card_capabilities.py::test_the_advertised_tier_is_the_enforced_tier`
fails if they ever diverge again.

### Confirmation execution bypassed rate limits

The confirmation path executed the held call after checking only that the
confirming caller had permission for the tool. It did not re-apply the
per-tool rate limit that the delegation path enforces, so an unlimited
number of confirmed calls could run once a token had been issued.

The fix splits "safety constraints" (auth + rate limit + confirmation
requirement) from "execution constraints" (auth + rate limit). Delegation
checks whether confirmation is required without consuming rate-limit
quota; confirmation checks execution constraints, including the rate
limit, before running. `SafetyController` is now constructed with the
server settings so the configured limits are actually used.

### A pre-existing test-collection defect

While adding the new tests, a latent defect in the existing suite surfaced:
combining `tests/unit/a2a/test_discovery.py` with any test module at the
`tests/unit/` level and `tests/unit/a2a/test_agent_card.py` made the
`local_settings` and `cloud_settings` fixtures vanish, so nine tests errored
with "fixture not found". The a2a package conftest registers those fixtures,
and the combination caused pytest to register that conftest under a second
module name, so the plugin registration and the fixture registration went to
different objects.

This was **not** caused by the new work: it reproduces on the original
`test_discovery.py` with `tests/unit/test_access.py`. The fix was to define
the settings fixtures in `test_agent_card.py` itself, so the module does not
depend on how pytest registers the package conftest. A new test file at the
`tests/unit/` level merely made the defect visible, because nothing else
collected that combination.

### A note on the test that reads the live registry

Two tests compare a document against the live tool registry: the agent card
artifact test and the skill-reference test. Both have to import the server,
and that import is **order-dependent**: another test module may have
imported `src.main` first, under a different environment, so the module is
already cached with a different tool surface. The comparison then fails for
reasons unrelated to the change under test.

Both tests re-import `src.main` from scratch and build their `Settings`
from explicit values rather than from the environment, and both read the
reference environment from `scripts/generate_agent_card.py` so the artifact
and the test cannot drift apart. The `unifi-docs-sync` skill records the
pattern.

## 5. What is not implemented, and why

- **The A2A task protocol.** No `message/send`, no Task lifecycle, no
  streaming, no push notifications, no `A2A-Version` header. Implementing
  it means adopting the `a2a-sdk` dependency and rebuilding the delegation
  path around Task objects. The repository gives no direction for that
  shape, so the server keeps its request/response delegation and the card
  declares `streaming: false` and `pushNotifications: false`.
- **Task cancellation and status reporting.** No implementation, and no
  advertised equivalent.
- **The per-tool cloud surface.** 40 Site Manager, connector, Mobility,
  InnerSpace and Carrier Fabric tools remain developer-facing. An operator
  skill for them would duplicate the developer skill's detail, which is
  the drift this work removes.
- **A gateway acceptance test.** The MCPJungle gateway forwards the
  native prompt operations, and the CLI syntax is documented in
  `docs/PROMPTS.md` from a verified source. Running it against the
  registered `unifi` server needs a deployment that carries this change,
  which is outside the authorisation for this work.

## 6. MCPJungle

The gateway supports the native prompt operations and forwards
`prompts/list` and `prompts/get`. The verified CLI:

```bash
mcpjungle list prompts --server unifi
mcpjungle get prompt "unifi__network_health_check" --arg site_id=default
```

One caveat worth knowing: the gateway reads a server's prompts when the
server is **registered**, and there is no periodic resync. A prompt added
to a server after it was registered does not appear until the server is
re-registered (`mcpjungle register --name unifi --url <url> --force`).
The gateway also namespaces the prompts it exposes, so an upstream name
appears as `<server>__<prompt>`.
