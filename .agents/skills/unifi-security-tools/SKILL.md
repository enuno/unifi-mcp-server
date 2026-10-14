---
name: unifi-security-tools
description: Use when adding, changing or testing a UniFi security MCP tool (legacy firewall rules, zone-based firewall policies and zones, firewall groups, ACL rules, traffic matching lists, content filtering, port forwarding, RADIUS and guest portal) - covers the three URL spaces, zone and network ID mapping, full-object policy updates, risk tiers, test fixtures and known gaps.
---

# UniFi Security Tools

These tools change who can reach what on the network, so a mistake can lock users or the operator out. Read this before you change one. For the general add-a-tool workflow, see `unifi-mcp-tool-builder`. For zone-based firewall (ZBF) background, see `zbf-implementation-guide.md` in this folder.

## Module map

| Module | Tools | API | Examples |
|--------|-------|-----|----------|
| `src/tools/firewall.py` | 4 | legacy | `list_firewall_rules`, `create_firewall_rule` |
| `src/tools/firewall_policies.py` | 7 | v2 and integration | `list_firewall_policies`, `create_firewall_policy`, `get_zone_policy_matrix` |
| `src/tools/firewall_zones.py` | 7 | integration | `assign_network_to_zone`, `unassign_network_from_zone` |
| `src/tools/firewall_groups.py` | 7 | legacy | `create_port_group`, `create_address_group`, `delete_firewall_group` |
| `src/tools/acls.py` | 5 | integration | `list_acl_rules`, `create_acl_rule` |
| `src/tools/traffic_matching_lists.py` | 5 | integration | `list_traffic_matching_lists`, `create_traffic_matching_list` |
| `src/tools/content_filtering.py` | 4 | v2 | `list_content_filters`, `update_content_filter` |
| `src/tools/port_forwarding.py` | 4 | legacy | `list_port_forwards`, `create_port_forward` |
| `src/tools/radius.py` | 17 | legacy | `list_radius_profiles`, `configure_guest_portal` |

`src/tools/zbf_matrix.py` holds 7 stubs that raise `NotImplementedError`. `src/main.py` does not import it, so none of them is registered. The UniFi API has no zone-matrix endpoint; `API.md` lists those tools as removed.

## Registration and modes

- Every public `async def` is a tool (`register_module_tools()` in `src/tool_registry.py`). Name helpers with a leading `_`.
- All these modules are in `_LOCAL_TOOL_MODULES` (`src/main.py`).
- The `security` profile covers `acls`, `content_filtering`, `firewall`, `firewall_groups`, `firewall_policies`, `firewall_zones` and `port_forwarding`, and also `site_vpn` and `vpn`. `radius` and `traffic_matching_lists` are in the `system` profile.
- Run-time checks: `firewall_policies`, `firewall_groups` and `content_filtering` refuse non-local modes with `_ensure_local_api()` (`NotImplementedError`). The `firewall_zones` version of that helper raises `ValidationError`.
- No code checks for Network 9.0+. If the v2 zone list is empty, `list_firewall_zones_v2` raises `APIError` with the message "ZBF does not appear to be configured".

## Legacy rules or zone-based policies

- Legacy rules (`rest/firewallrule`) are read and written by `src/tools/firewall.py`. In local mode, `list_firewall_rules` falls back to the v2 `firewall-policies` list when the legacy list is empty.
- Zone-based policies are read and written only by the `*_firewall_policy` tools. Nothing picks the right family for the caller, so a new tool must state in its docstring which family it changes.

## URL spaces

| Space | Path helper | Used by |
|-------|-------------|---------|
| Legacy | write `/ea/sites/{site}/rest/...`; `UniFiClient` rewrites it for local mode | firewall rules, groups, port forwards, RADIUS, guest portal |
| v2 | `settings.get_v2_api_path(site_id)` (local only) | firewall policies, the v2 zone list, content filtering |
| Integration | `settings.get_integration_path(f"sites/{site_uuid}/...")` | zones, ACL rules, traffic matching lists, `get_zone_policy_matrix` |

The integration API needs a site UUID; get it with `await client.resolve_site_id(site_id)`. The integration API is served both on the local console (`/proxy/network/integration/v1/`) and through the cloud connector; the spec snapshot `scripts/scraped-api-spec-v10.6.106.json` lists both servers.

## IDs

- There are two zone ID spaces. v2 uses MongoDB ObjectIds; the integration API uses UUIDs. `_resolve_zone_id()` in `src/tools/firewall_policies.py` accepts a name, a UUID or an ObjectId, and caches the zone index per site in the module-level `_zone_cache`.
- Network IDs are mapped from ObjectId to UUID by `_resolve_network_uuid()` in `src/tools/firewall_zones.py`.
- `get_zone_policy_matrix` returns v2 and integration zone IDs, which cannot be joined directly.

## Models

- Models: `src/models/firewall_policy.py`, `src/models/firewall_group.py`, `src/models/firewall_zone.py`, `src/models/acl.py`, `src/models/traffic_matching_list.py`, `src/models/radius.py`.
- Read models are permissive on purpose: string fields instead of enums, and `extra="allow"`. New firmware adds values, and a strict model would break reads.
- `ACLRule` requires `action` and maps `id` from `_id` (`populate_by_name=True`).

## Write tools

- Signature: `confirm: bool | str = False, dry_run: bool | str = False`. Call `validate_confirmation(confirm, "<operation>", dry_run)` first, and return the dry run before you open a client.
- The registry wrapper audits every mutating call, and with `UNIFI_AUDIT_FAIL_CLOSED` on (the default) it refuses the call if the audit record cannot be written. Some modules also call `log_audit()` or `audit_action()` themselves; do not add a third path.
- **Full-object policy updates.** The v2 policy PUT needs the whole object. `update_firewall_policy` GETs the policy, merges the changes, removes `_id` and `predefined`, then PUTs. `create_firewall_policy` always sends a schedule with mode `ALWAYS`.
- **Lockout protection is thin.** The only guard is that predefined policies cannot be updated or deleted. Nothing stops a rule that blocks management access. When you add a tool that can block traffic, make the dry run show exactly what will be blocked.
- **Zones.** The API rejects a zone `description` (`api.request.unknown-property`), so the tool drops it. Every zone PUT must include `networkIds` and `name`.
- In `update_firewall_policy`, `port` and `port_group_id` cannot both be set.
- Content filters cannot be created; the v2 endpoint returns 405 on POST.

## Risk tiers

- `tool_tier()` (`src/tool_registry.py`) makes a tool destructive when its name starts with `delete_`, `remove_` or `bulk_delete_`, or when it is in `DESTRUCTIVE_TOOLS`.
- Tools that change firewall policy are in `DESTRUCTIVE_TOOLS`, so only the admin role can call them: `create_firewall_policy`, `update_firewall_policy`, `update_zbf_policy`, `create_firewall_rule`, `update_firewall_rule`, `assign_network_to_zone` and `unassign_network_from_zone` (`test_firewall_policy_changes_need_admin`).
- Everything else that mutates is `write` tier, which the operator role can call. That includes ACL rules, port forwards, firewall groups and zones, traffic matching lists and the content filter.
- When a new tool can cut off traffic, decide with the owner whether it belongs in `DESTRUCTIVE_TOOLS`.
- A tool with a risky word in its name (`block`, `disable` and others) must be in `DESTRUCTIVE_TOOLS` or in `RISKY_NAME_EXEMPTIONS` (`tests/unit/fleet/test_tiers.py`).
- Regenerate the snapshot after any tool change: `UPDATE_TOOL_TIERS=1 pytest tests/unit/fleet/test_tiers.py`.

## Tests

- Files: `tests/unit/tools/test_<module>_tools.py`, plus `tests/unit/tools/test_firewall_policies.py` and `tests/unit/tools/test_firewall_policy_helpers.py`.
- Patch the client in the module: `patch("src.tools.firewall_policies.UniFiClient")`. Set `__aenter__` to return the client and `__aexit__` to return `False`. A bare `AsyncMock()` for `__aexit__` returns a truthy value, the `async with` block then swallows every exception, and the tool returns `None`.
- Build real settings with `monkeypatch.setenv("UNIFI_API_TYPE", "local")` and `Settings()` when the path matters. Mocked cloud-ea settings hid the local-mode ACL bug from April to October 2026: the tests ran in cloud-ea mode, but the tools were registered only in local mode.
- Tests that use `_zone_cache` seed it by hand and clear it afterwards.

## Known defects and gaps (not fixed)

- The confirmation checks are not the same everywhere. `firewall_policies`, `firewall_groups` and `content_filtering` raise `ValueError`, while modules that use `validate_confirmation()` raise `ValidationError`.
- Dry-run and delete replies have different shapes in different modules (`{"dry_run": True, ...}` or `{"status": "dry_run", ...}`).
- `update_firewall_policy` writes no audit entry of its own for dry runs or failures; the wrapper still audits the call.
- `delete_firewall_zone` authenticates before it checks `dry_run`, so a dry run still makes one request.
- The ACL and traffic-matching-list local-mode fix (commit `aaf3dd8`) is verified against mocks and the spec, not on hardware.
