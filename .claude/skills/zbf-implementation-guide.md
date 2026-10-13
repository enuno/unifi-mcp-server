---
name: zbf-implementation-guide
description: Use when working on Zone-Based Firewall (ZBF) features for UniFi Network 9.0+ - explains which ZBF APIs exist (v2 policies and zones, integration zones), the two zone ID spaces, what the server implements, and what the UniFi API does not offer. Use unifi-security-tools for the coding rules.
---

# Zone-Based Firewall (ZBF) Guide

This guide describes what ZBF is in the UniFi API and what this server implements. For how to write and test a security tool, load the `unifi-security-tools` skill (`.claude/skills/unifi-security-tools/SKILL.md`).

## What ZBF is

UniFi Network 9.0 replaced per-network firewall rules with zones. Each network belongs to one zone (built-in zones include Internal, External, Gateway, VPN, Hotspot and DMZ), and policies allow or block traffic between zones. Legacy firewall rules still exist on older setups. No code in this server checks the Network version.

## What the server implements

All ZBF tools are local-mode only.

| Area | Module | Tools | API |
|------|--------|-------|-----|
| Policies | `src/tools/firewall_policies.py` | `list_firewall_policies`, `get_firewall_policy`, `create_firewall_policy`, `update_firewall_policy`, `delete_firewall_policy` | v2 `/firewall-policies` |
| Zones (v2 view) | `src/tools/firewall_policies.py` | `list_firewall_zones_v2` | v2 `/firewall/zone` |
| Policy overview | `src/tools/firewall_policies.py` | `get_zone_policy_matrix` | v2 policies plus integration zones, built locally |
| Zones | `src/tools/firewall_zones.py` | `list_firewall_zones`, `create_firewall_zone`, `update_firewall_zone`, `delete_firewall_zone` | integration `/firewall/zones` |
| Zone networks | `src/tools/firewall_zones.py` | `assign_network_to_zone`, `unassign_network_from_zone`, `get_zone_networks` | integration zone `networkIds` |

Paths: v2 calls use `settings.get_v2_api_path(site_id)`, and integration calls use `settings.get_integration_path(...)` with a site UUID.

## What the UniFi API does not offer

The UniFi API has no endpoint for a zone-to-zone policy matrix, for application blocking per zone, or for zone traffic statistics (`API.md`, "Zone-Based Firewall"). `src/tools/zbf_matrix.py` still holds stubs for those features. Every stub raises `NotImplementedError`, and `src/main.py` does not import the module, so none of them is registered. Do not register them. Users configure those features in the UniFi console.

## Facts to get right

- **Two zone ID spaces.** v2 uses MongoDB ObjectIds, and the integration API uses UUIDs. `_resolve_zone_id()` accepts either, or a zone name. `get_zone_policy_matrix` returns both kinds of ID, and they cannot be joined directly.
- **Zone networks.** A network joins a zone through the zone's `networkIds` list on the integration API, not through a field on the network. Every zone PUT must send `networkIds` and `name`.
- **Zone description.** The API rejects `description` (`api.request.unknown-property`), so `create_firewall_zone` accepts the argument and drops it.
- **Policy actions.** v2 policies use ALLOW and BLOCK. `create_firewall_policy` always sends an always-on schedule.
- **Policy updates.** The v2 PUT needs the whole policy. `update_firewall_policy` reads it, merges the changes, removes `_id` and `predefined`, and writes it back. Predefined policies cannot be updated or deleted.
- **Zone deletion.** `delete_firewall_zone` does not check whether a zone is still in use.
- **Empty zone list.** If the v2 zone list is empty, `list_firewall_zones_v2` raises `APIError`, because a ZBF site always has built-in zones.

## Before you add a ZBF tool

1. Find the endpoint in `scripts/scraped-api-spec-v10.6.106.json` or in `docs/UNIFI_API.md`. If it is in neither, do not build the tool on a guess.
2. Follow the write pattern and the risk-tier rules in `unifi-security-tools`.
3. Say in the pull request that the tool is verified against mocks only, unless you tested it on a controller.
