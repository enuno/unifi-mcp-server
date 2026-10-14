---
name: unifi-protect-tools
description: Use when adding, changing or testing a UniFi Protect MCP tool (any src/tools/protect_*.py module) - covers the Protect client and paths, v7 models, the confirm/dry_run write pattern, response shapes, test fixtures and known Protect API gaps.
---

# UniFi Protect Tools

Protect tools talk to the Protect integration API on the local console. Read this before you add or change a tool in any `src/tools/protect_*.py` module. For the general add-a-tool workflow, see `unifi-mcp-tool-builder`.

## Module map

15 modules, 72 functions, 71 registered tool names.

| Module | Tools | Examples |
|--------|-------|----------|
| `src/tools/protect_alarm.py` | 8 | `list_protect_arm_profiles`, `set_current_protect_arm_profile`, `disable_protect_alarm` |
| `src/tools/protect_alarm_hubs.py` | 4 | `list_protect_alarm_hubs`, `update_protect_alarm_hub` |
| `src/tools/protect_bridges.py` | 3 | `get_protect_bridge`, `update_protect_bridge` |
| `src/tools/protect_cameras.py` | 2 | `list_protect_cameras`, `get_protect_camera` |
| `src/tools/protect_devices.py` | 13 | `list_protect_devices`, `update_protect_light`, `get_protect_chime` |
| `src/tools/protect_events.py` | 7 | `list_protect_events`, `send_protect_alarm_webhook` |
| `src/tools/protect_fobs.py` | 3 | `update_protect_fob` |
| `src/tools/protect_link_stations.py` | 3 | `update_protect_link_station` |
| `src/tools/protect_nvr.py` | 2 | `list_protect_nvrs`, `get_protect_nvr` |
| `src/tools/protect_pos.py` | 1 | `ingest_pos_transaction` |
| `src/tools/protect_relays.py` | 4 | `update_protect_relay`, `activate_protect_relay_output` |
| `src/tools/protect_sirens.py` | 6 | `play_protect_siren`, `stop_protect_siren` |
| `src/tools/protect_speakers.py` | 4 | `update_protect_speaker` |
| `src/tools/protect_users.py` | 4 | `list_protect_users`, `list_protect_ulp_users` |
| `src/tools/protect_views.py` | 8 | `get_protect_meta_info`, `create_protect_live_view` |

MCP resources for Protect are in `src/resources/protect.py`. The raw `connector_protect_*` proxy tools are in `src/tools/connector.py` and belong to the cloud tool set.

## Registration

- Every public `async def` in the module is a tool (`register_module_tools()` in `src/tool_registry.py`). Name helpers with a leading `_`.
- Protect modules are in `_LOCAL_TOOL_MODULES` only (`src/main.py`). They do not exist in cloud modes.
- A new module goes into three places in `src/main.py`: `_LOCAL_TOOL_MODULES`, the `protect` profile and the `system` profile.
- Protect reads are not cached. Protect modules are not in `CACHED_MODULES` (`src/cache.py`).

## HTTP

- Use `ProtectClient` from `src/api/protect_client.py`, not `UniFiClient`.
- Build every path with `settings.get_protect_integration_path("<endpoint>")`. In local mode that gives `/proxy/protect/integration/v1/<endpoint>`.
- Call `await client.authenticate()` first; it checks access with a GET to `cameras`.
- Send bodies with `json_data=`, not `json=`.
- A status of 400 or more raises `APIError`.

```python
async with ProtectClient(settings) as client:
    await client.authenticate()
    response = await client.patch(
        settings.get_protect_integration_path(f"relays/{relay_id}"),
        json_data=payload,
    )
```

## Models

- v7 models are in `src/models/protect_v7.py` and inherit `_ProtectV7Base`, which sets `populate_by_name=True` and `extra="allow"`. Unknown fields from newer firmware must not break parsing.
- Fields are snake_case with a camelCase `alias=`. Dump with `model_dump(by_alias=True)`.
- Older models (`src/models/protect_camera.py`, `src/models/protect_nvr.py` and others) do not allow extra fields. Do not copy them for new work.
- Export new models from `src/models/__init__.py`.

## Write tools

Copy `update_protect_relay` in `src/tools/protect_relays.py`. The order is fixed:

1. `validate_confirmation(confirm, "<operation>", dry_run)`
2. validate IDs and arguments, and raise `ValidationError` on bad input
3. build the payload from the arguments that are not `None`; raise `ValidationError` if it is empty
4. `if coerce_bool(dry_run): return {"dry_run": True, "operation": "<tool name>", ..., "payload": payload}`
5. only then open `ProtectClient`

Do not write audit code; the registry wrapper audits every mutating call. A tool with a risky word in its name (`disable`, `reset` and others) must be in `DESTRUCTIVE_TOOLS` (`src/tool_registry.py`) or in `RISKY_NAME_EXEMPTIONS` (`tests/unit/fleet/test_tiers.py`).

## Response shapes

| Kind | Return |
|------|--------|
| List | `{"offset", "limit", "count", "totalCount", "data": [...]}`; use `validate_limit_offset()` (default 100, range 1 to 1000) |
| Get or update | `Model.model_validate(_extract_item(response)).model_dump(by_alias=True)` |
| Action | `{"success": True, <ids>, "response": ...}` |

`_extract_collection` and `_extract_item` accept a bare value or a `{"data": ...}` wrapper. Each module has its own copy. Log through `sanitize_log_message()`.

## Tests

- Files: `tests/unit/tools/test_protect_<module>.py`. Representative: `tests/unit/tools/test_protect_relays.py`.
- Patch the client: `patch("src.tools.protect_relays.ProtectClient", return_value=mock_client)`, where `mock_client` is an `AsyncMock` with `__aenter__` returning itself and `__aexit__` returning `False`.
- Assert the exact path and body: `mock_client.patch.assert_awaited_once_with(path, json_data=...)`.
- For every write, test refusal without `confirm` (and with `confirm="false"`), that the client is never created on refusal, and that a dry run makes no call.
- `tests/unit/tools/test_protect_write_gates.py` checks every Protect write for `confirm` and `dry_run`.
- After you add or rename a tool, run `UPDATE_TOOL_TIERS=1 pytest tests/unit/fleet/test_tiers.py`.

## Gotchas

- The spec baseline is Protect v7.3.68 (`scripts/protect-api-spec-v7.3.68.json`). Check an endpoint there before you call it.
- The Phase 5a write paths are tested against mocks only; nobody has verified them on hardware. Say so when you change one.
- `get_protect_arm_profile` calls a GET path that is not in the v7.3.68 spec, so it may return 404.
- `docs/UNIFI_API.md` still calls Protect v7 "planned" near its start, which contradicts its later Phase 5a section.

## Known defects (not fixed)

- `list_protect_device_updates` is defined twice, in `src/tools/protect_devices.py` and in `src/tools/protect_events.py`. Only the first registered copy (from `protect_devices`) is used.
- `MUTATING_TOOLS_WITHOUT_GATE` in `src/tool_registry.py` still lists Protect tools that now have gates. It is harmless.
