---
name: unifi-network-config-tools
description: Use when adding, changing or testing a UniFi Network configuration MCP tool (networks, WiFi, WAN, DHCP, DNS, QoS, port profiles, switching, VPN) - covers URL spaces and site ID translation, read-modify-write updates, the write pattern, caching, test fixtures and firmware gotchas.
---

# UniFi Network Configuration Tools

These tools read and change network configuration on the local gateway. Most of them use the legacy Network API, and a few use the integration API. Read this before you change one. For the general add-a-tool workflow, see `unifi-mcp-tool-builder`.

## Module map

| Module | Tools | Examples |
|--------|-------|----------|
| `src/tools/networks.py` | 4 | `get_network_details`, `list_vlans`, `get_subnet_info` |
| `src/tools/network_config.py` | 3 | `create_network`, `update_network`, `delete_network` |
| `src/tools/wifi.py` | 5 | `list_wlans`, `update_wlan`, `get_wlan_statistics` |
| `src/tools/wans.py` | 6 | `list_wan_connections`, `create_dynamic_dns` |
| `src/tools/dhcp_reservations.py` | 5 | `create_dhcp_reservation`, `remove_dhcp_reservation` |
| `src/tools/dns_management.py` | 4 | `list_wan_dns`, `update_dns_filter` |
| `src/tools/qos.py` | 3 | `list_traffic_routes`, `configure_smart_queue` |
| `src/tools/port_profiles.py` | 8 | `update_port_profile`, `set_device_port_overrides` |
| `src/tools/switching.py` | 6 | `list_switch_stacks`, `get_lag_details` (reads only) |
| `src/tools/vpn.py` | 2 | `list_vpn_tunnels`, `list_vpn_servers` |
| `src/tools/site_vpn.py` | 3 | `get_site_to_site_vpn`, `update_site_to_site_vpn` |

## Registration and modes

- Every public `async def` is a tool (`register_module_tools()` in `src/tool_registry.py`). `port_profiles.get_device_by_mac` is public, so it is a tool too. Name helpers with a leading `_`.
- All 11 modules are in `_LOCAL_TOOL_MODULES` (`src/main.py`). None of them exists in cloud modes.
- Some tools also refuse non-local modes at run time with a `_ensure_local_api()` helper: DHCP, DNS, Dynamic DNS and traffic routes.
- `UNIFI_PROFILE` sets in `src/main.py`:

  | Profile | Modules |
  |---------|---------|
  | `network` | dhcp, dns, network_config, networks, wans, wifi |
  | `devices` | port_profiles, switching |
  | `security` | site_vpn, vpn |
  | `system` | qos |

  Add a new module to the right set.
- No module checks the Network version in code. When a feature needs Network 9.0+, say so in the tool docstring.

## URL spaces

| Space | How to build the path | Site ID |
|-------|-----------------------|---------|
| Legacy | Write `/ea/sites/{site_id}/<resource>`. `UniFiClient` rewrites it to `/proxy/network/api/s/{site_name}/<resource>` in local mode | UUID or name; the client maps a UUID to the site name |
| v2 | `settings.get_v2_api_path(site_id)` | the client maps a UUID to the site name |
| Integration | `settings.get_integration_path(f"sites/{site_id}/...")` | the client maps a name to the UUID; `client.resolve_site_id()` returns the UUID |

Legacy resources in use: `rest/networkconf`, `rest/wlanconf`, `rest/portconf`, `rest/user`, `rest/dynamicdns`, `get/setting/ips`. The client also rewrites `devices` to `stat/device` and `sta` to `stat/sta`.

Do not hardcode `/proxy/network/api/s/...`. The client passes such a path through unchanged, so a site UUID is never turned into a site name (see Known defects).

## Models

- Models: `src/models/network.py`, `src/models/wan.py`, `src/models/vpn.py`, `src/models/port_profile.py`, `src/models/switching.py`, `src/models/qos_profile.py`.
- Legacy records use `id` with `alias="_id"` and `populate_by_name=True`. Integration models use camelCase aliases.
- Only `WANConnection` and `TrafficRoute` set `extra="allow"`. The rest drop unknown keys.
- The legacy API calls the VLAN field `vlan`. `Network` aliases `vlan_id` to `vlan`, but `network_config` returns raw controller records, which contain `vlan`. The two modules return different shapes.

## Write tools

- Signature: `confirm: bool | str = False, dry_run: bool | str = False`. `test_every_mutating_tool_declares_dry_run` (`tests/unit/test_tool_registry.py`) requires `dry_run` on every write.
- Call `validate_confirmation(confirm, "<operation>", dry_run)` first. Return the dry run before you open a client.
- Do not add audit code; the registry wrapper audits every mutating call.

**Read-modify-write.** These tools GET the whole record, merge the changes and PUT the whole record back:

- `update_network`
- `update_wlan`
- `update_port_profile`
- `set_device_port_overrides` (PUTs the whole device)
- `update_site_to_site_vpn`

Rules for them:

- Optional update arguments must default to `None`. A default such as `False` overwrites the stored value on every update.
- Take a record from a list reply with `first_response_item()` (`src/utils/helpers.py`), never with `[0]`.
- The controller rewrites some fields on its own. `port_profiles` re-reads the record and reports the differences (`_stored_value_warnings`). Do the same when you add a read-modify-write tool.
- `set_device_port_overrides(merge=False)` replaces every override, and the `dns_filters` list in `update_dns_filter` replaces the whole list. Say so in the docstring of any argument that replaces a list.

**Partial updates.** `update_wan_dns` and `configure_smart_queue` send only the changed fields to `rest/networkconf`. DHCP sends partial fields to `rest/user`.

## Responses, errors and cache

- `UniFiClient` returns `{"data": ...}` for a reply that has a data key, and `{}` for an empty body. Handle a list or a dict.
- 404 raises `ResourceNotFoundError`, 401 and 403 raise `AuthenticationError`, and other errors raise `APIError`.
- The Redis read cache covers only the `networks` and `wifi` modules (`CACHED_MODULES` in `src/cache.py`). Tool names containing "statistics" are never cached.
- Any write that is not a dry run clears every cached read for that controller. A write tool needs no cache code of its own.
- `src/tools/wifi.py` passes WLAN output through `_redact_wlan()`. Keep that for any tool that returns WLAN records, because they contain passphrases.

## Tests

- Files: `tests/unit/tools/test_<module>_tools.py`. Switching tests are in `tests/unit/test_switching.py`. Representative: `tests/unit/tools/test_network_config_tools.py`.
- Patch the module's client name: `patch.object(nc_module, "UniFiClient", ...)`. Use a `MagicMock` client with `AsyncMock` methods, and make `__aexit__` return `False`, or exceptions inside the tool are swallowed.
- Assert the request body: `client.put.call_args[1]["json_data"]`.
- When a tool checks the API mode, set `settings.api_type = APIType.LOCAL` on the settings fixture.

## Firmware gotchas

- Mock-only tests once passed for endpoints that do not exist (`rest/qosprofile`, `rest/wanconf`). Before you add an endpoint, find it in `docs/UNIFI_API.md` or a spec snapshot in `scripts/`, and say if it is not verified on hardware.
- Smart Queue rates are stored in kbps; the UI shows Mbps.
- DNS-over-TLS has no REST field on firmware 10.2.x.
- POSTing a MAC the controller already knows fails with `api.err.MacUsed`, so DHCP looks the client up first. Setting `fixed_ip` without `use_fixedip` does nothing.
- A network's `purpose` cannot change after creation.
- The integration API WAN list returns only `id` and `name`.

## Known defects (not fixed)

- `src/tools/site_vpn.py` hardcodes `/proxy/network/api/s/{site_id}`, so a site UUID is passed to the legacy API unchanged. A site name works.
- The confirmation checks are not the same everywhere. `site_vpn` returns `{"error": ...}` where other modules raise, and the DHCP and DNS modules raise `ValueError` where others raise `ValidationError`.
- Dry-run replies differ between modules: `{"dry_run": True, "would_create": ...}` in `network_config` and `{"status": "dry_run", ...}` in `dhcp_reservations`.
- `qos.py` maps site UUIDs to names by hand through `client._site_uuid_to_name`, which the client now does for v2 paths anyway.
