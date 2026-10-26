---
name: unifi-docs-sync
description: Use when adding, changing or removing an MCP tool, changing the A2A agent card or the native MCP prompt catalog, or changing what a deployment exposes - covers the tool registry, the agent card, the prompt catalog, API.md, the skills and the checks that fail when they drift.
---

# Keeping Tools, A2A, Prompts and Docs in Sync

The repository exposes the same capability surface in four places. They are
derived from the tool registry, but each one is a separate artifact, and
each can drift. This skill is the checklist for keeping them aligned.

## The four surfaces

| Surface | Source of truth | Artifact |
|---|---|---|
| MCP tools | `src/tool_registry.py` registration | Live at runtime |
| A2A agent card | `src/a2a/capabilities.py` (the live registry) | `agent-card.json` |
| Native MCP prompts | `src/prompts/catalog.py` | Live at runtime |
| Documentation | `API.md`, `README.md`, `skills/` | Files |

The rule that keeps them aligned: **never write a tool name into a
document from memory.** Read it from the registry.

## Read the real tool inventory

```bash
unset PYTHONPATH; cd /home/elvis/projects/unifi-mcp-server-prompts
UNIFI_API_KEY=*** UNIFI_API_TYPE=local UNIFI_LOCAL_HOST=192.0.2.1 \
AGNOST_ENABLED=false ./.venv/bin/python -c "
import src.main as M
tools = sorted(
    k[5:].split('@', 1)[0]
    for k in M.mcp._local_provider._components
    if k.startswith('tool:')
)
print(len(tools))
print('\n'.join(tools))"
```

The count differs by mode and profile. Local mode registers 343 tools; the
cloud modes register 71. Check the mode you are documenting.

The risk tier of each tool is in `src/tool_registry.py:TOOL_TIERS`, filled
at registration. It is what the server authorizes against, so a document
that calls a tool read-only when the registry says write is wrong.

## When you add a tool

1. **Implement it** in the right `src/tools/` module, with `@read_tool` or
   `@write_tool`. `register_module_tools` refuses a tool with no
   declaration, so this is not optional.
2. **Give a write tool a `confirm` parameter** and, where the operation can
   be previewed, a `dry_run` parameter. The wrapper enforces `confirm`; the
   `dry_run` gate is what makes a preview possible.
3. **Check the tests.** `tests/unit/test_tool_declarations.py` walks the
   call graph of every read tool and fails if one reaches a `post`, `put`,
   `patch` or `delete`.
4. **Add it to `API.md`** under the right category, with its parameters.
5. **Add it to the right skill** under `skills/`. The operator skills cover
   the tool surface; the developer skills cover the module mechanics.
6. **If it is a new module**, add it to the profile lists in
   `src/tool_registry.py` and to the module map in the developer skill.
7. **Regenerate the agent card** if the tool surface changed:

   ```bash
   python scripts/generate_agent_card.py
   ```

   `tests/unit/a2a/test_agent_card.py` fails when the artifact and the
   builder disagree.

## When you remove or rename a tool

A rename breaks every document that mentions the old name. Search the
whole repository:

```bash
grep -rn "old_tool_name" --include="*.md" --include="*.py" .
```

The places a tool name appears:

- `API.md` — the tool's entry.
- `skills/*/SKILL.md` — the operator and developer skills.
- `src/prompts/catalog.py` — the prompt catalog names the tools each
  workflow reads. **A prompt whose evidence tool is renamed must be
  updated too**, or the workflow silently loses its evidence.
- `src/a2a/capabilities.py` — the module-to-domain map, if the module
  changed.
- `src/a2a/agent_card.py` — the safety-requirement logic, if the tool's
  tier changed.

## The native prompt catalog

`src/prompts/catalog.py` names the tools each workflow reads, in two
places: the `evidence` list and the `requirements` groups.

A workflow is advertised only when the tools its requirements name are
registered. So:

- **Renaming a tool breaks a workflow's availability**, not just its text.
- **A workflow that loses its last requirement tool disappears** from
  `prompts/list` in that configuration.
- `tests/unit/prompts/test_prompt_catalog.py` checks every named tool
  against the live registry, so a stale name fails the test suite rather
  than producing a prompt that calls a tool that no longer exists.

The prompt text is guidance, not authorisation. It must never claim that a
check was performed, and it must not promise a tool the server does not
have.

## The A2A agent card

The card is built from the live registry, so it follows the tools
automatically. What it does **not** follow is anything you wrote by hand:

- `capabilities` in `src/a2a/capabilities.py` — the advertised capability
  names. A new domain needs a new entry there.
- `_MODULE_DOMAINS` in the same module — the tool-module-to-domain map. A
  new module must be placed, or it lands in `fleet` by default.
- The `skills` list in the card is the tool list, sorted by name. The
  artifact `agent-card.json` is the reference for a default local
  deployment.

The card is public metadata. It must not carry a credential, a controller
address or a filesystem path. `tests/unit/a2a/test_agent_card_capabilities.py`
asserts that.

## Tests that read the live registry

A test that compares a document against the live tool registry has to
import the server itself, and that import is **order-dependent**. Another
test module may have imported `src.main` first, under a different
environment, so the module is already in `sys.modules` with a different tool
surface. The comparison then fails, or passes, for reasons that have
nothing to do with the change under test.

Re-import the server instead of reusing the cached one:

```python
import os
import sys

os.environ.update(REFERENCE_ENV)
for module_name in list(sys.modules):
    if module_name == "src.main" or module_name.startswith("src.main."):
        del sys.modules[module_name]
sys.path.insert(0, str(ROOT))
import src.main as main
```

Build the `Settings` from explicit values rather than from the
environment, because the test session clears the `UNIFI_*` variables:

```python
settings = Settings.model_validate(REFERENCE_ENV)
```

Keep the reference environment in one place, and read it in both the test
and whatever generates the artifact, so the two cannot drift apart.

## The two guard tests

Two tests read the live registry and fail when a document drifts from it:

- `tests/unit/test_skill_tool_references.py` — a skill table must not name a
  tool the server does not register.
- `tests/unit/test_skill_parameter_references.py` — a skill must not state an
  argument the tool's schema does not have.

The second one reads an **explicit argument list**: a parenthesised or
bracketed group of backticked names following the tool name. Prose that
mentions a response field, a function name, or a contrasting spelling in the
same breath is not an argument claim. Writing an argument list is therefore
the way to state a parameter; writing it in prose does not get checked, and
does not mislead the reader either.

When a tool's schema changes, both guards fail until the skills are updated.
Run them before the full suite; they are the fastest signal that a
registration change needs a documentation change with it.

## The checks that catch drift

```bash
make test          # every unit test
make test-cov      # the same with the coverage gate
make lint          # formatting, import order, ruff
make typecheck     # mypy over src/
make security      # bandit
make docs-coverage # docstring coverage of tools and the API client
make pre-commit    # the hooks CI runs
```

Two of these are drift detectors in their own right:

- `tests/unit/test_agent_docs.py` fails when a skill's frontmatter `name`
  does not match its folder, when a developer skill's copy in
  `.claude/skills/` or `.agents/skills/` differs from `skills/`, and when
  a document cites a path, link or tool name that does not exist.
- `tests/unit/a2a/test_agent_card.py` fails when the card artifact and
  the builder disagree.

## Copying a skill to the agent directories

`skills/<name>/SKILL.md` is the source of truth for the developer skills.
After editing one, copy it:

```bash
for dir in .claude/skills .agents/skills; do
  cp skills/<name>/SKILL.md "$dir/<name>/SKILL.md"
done
```

Only the developer skills are copied. The operator skills live in
`skills/` alone.

## The order that works

1. Implement and register the tool.
2. Run the focused test: `pytest tests/unit/tools/test_<module>.py -q`.
3. Update `API.md`.
4. Update the skills, and copy the developer ones to both agent
   directories.
5. Update the prompt catalog if a workflow read the tool.
6. Regenerate the agent card.
7. Run `make test`, then `make lint typecheck`.

Doing 3-6 after 7 wastes a cycle: the drift tests will tell you what you
missed, but the fix is the same either way.
