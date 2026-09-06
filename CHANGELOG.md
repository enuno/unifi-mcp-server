# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- **`download_backup` could write anywhere and `backup_filename` could traverse the controller API**: the tool took `output_path` straight from the caller and did `Path(output_path).parent.mkdir(parents=True); write_bytes(...)`, so a malicious or prompt-injected call could create or overwrite any file the server process could write — with the umask-default `0644` permissions and no confirmation — and a symlink at the target was followed. Separately, `backup_filename` was interpolated unvalidated into `/proxy/network/data/backup/{filename}` (and the delete path); because httpx normalises `..` segments, a crafted filename turned the tool into an authenticated GET of any controller route. Now: `backup_filename` is validated to a single plain path component and URL-encoded before use (`download_backup` and `delete_backup`); and `download_backup` uses only the *filename* of `output_path`, writing it inside `UNIFI_BACKUP_DOWNLOAD_DIR` (new; default: current working directory) with `O_NOFOLLOW` and mode `0o600`. **Migration:** `output_path` is now a filename, not a full path — set `UNIFI_BACKUP_DOWNLOAD_DIR` to choose the destination directory.
- **Network transports now require authentication (breaking)**: the `http`, `sse`, and `streamable_http` transports expose every registered tool — including destructive ones — over a TCP listener, but the server started them with no authentication, no origin check, and (with the previous `MCP_SERVER_HOST=0.0.0.0` default) bound to all interfaces. Any host that could reach the port could call `delete_firewall_rule`, `restore_backup`, `execute_port_action`, and the rest with the server's own controller credentials; a foreign-`Origin` request from a LAN browser was accepted too (DNS-rebinding). The server now (a) builds a bearer-token auth provider from a new `MCP_AUTH_TOKEN` (comma-separate to issue several; clients send `Authorization: Bearer <token>`), (b) **refuses to start** any network transport when no token is configured, and (c) defaults `MCP_SERVER_HOST` to `127.0.0.1`, so exposing the port is now an explicit opt-in that must be paired with a token and, ideally, a TLS-terminating reverse proxy. `stdio` (the default transport) is unchanged and needs no token. `.env.example`, `docker-compose.yml`, and the README transport section are updated accordingly. **Migration:** operators running a network transport must set `MCP_AUTH_TOKEN` and configure their MCP client/gateway to send the bearer token; those relying on the implicit `0.0.0.0` bind must now set `MCP_SERVER_HOST=0.0.0.0` explicitly.

### Added

- **`update_dpi_settings`**: enable or disable DPI (traffic identification) on a site. DPI is the passive per-flow classifier behind the DPI statistics tools; with it off those counters stay empty, which reads exactly like "no traffic" and sends you looking for the wrong fault — verified live, where a site with empty counters turned out to have the feature already enabled and nothing exposed the flag either way. Read-modify-write of the `dpi` settings section (`get/setting/dpi`, then `set/setting/dpi/{_id}`) preserving every other key the section carries, with the stored state re-read afterwards and reported as unconfirmed rather than success when the controller does not echo the requested value. Requires `confirm`, supports `dry_run`.

- **`set_ap_min_rssi`**: set the minimum client RSSI on a single AP radio. Below the floor the AP refuses or evicts the association, so a client camped on a distant AP re-places itself onto a nearer one. This is the per-AP, per-radio counterpart to the WLAN-wide roaming assistant: the assistant cannot be scoped to one AP, so raising it to fix an indoor sticky-client problem also evicts the weak clients an outdoor AP exists to serve. `get_ap_radio_config` already reports `min_rssi`/`min_rssi_enabled`; this writes them, read-modify-write against the device config record with the stored radio table re-read and any divergence reported rather than assumed. Requires `confirm`, supports `dry_run`, and validates the controller-accepted -90..-60 dBm range before any network I/O.

- **`list_client_rf_health`**: per-client transmit retry percentages, worst first. Retries climb before latency degrades and before satisfaction drops, which makes them the leading indicator of airtime trouble; the `sta` route already carries `tx_packets`/`tx_retries` per association and no tool exposed them. Wireless clients only, with an optional `min_retry_pct` floor to show only the strugglers. The counters are lifetime-per-association, so one reading is a baseline and the signal is the change between readings — a client that reassociates resets its own history.

- **Read-only mode** (`UNIFI_READ_ONLY`): register only non-mutating tools, so state-changing tools never reach the MCP tool list and calling one fails with `Unknown tool` at the protocol layer. `confirm=True` is a parameter the model supplies — a good guard against accidents, but not a control against a model that decides to set it, and this server returns device names and DHCP hostnames verbatim into the context. Tools are classified by signature (`confirm`/`dry_run`), which stays correct as tools are added; a name-based heuristic would miss 21 of them, among them `adopt_device`, `upgrade_device`, `bulk_delete_vouchers`, `limit_bandwidth`, `start_spectrum_scan` and the eight `connector_*` passthroughs. Nine tools mutate without either marker (the Protect device/view writers, `run_speed_test`, `send_protect_alarm_webhook`) and are listed explicitly in `MUTATING_TOOLS_WITHOUT_GATE` — a classification hint only, their behaviour is unchanged. Verified live against Cloud V1: 43 tools by default, 35 read-only, with `list_sites` still answering and `connector_network_post` gone. Opt-in; the default is unchanged.
- **Historical time-series and RF scan trigger** (`get_historical_stats`, `start_spectrum_scan`): `get_historical_stats` reads the controller's rollup archives (`stat/report/{interval}.{subject}` for site/ap/user/gw at 5minutes/hourly/daily/monthly) — the only source of historical airtime, per-client signal, and client counts. Archive airtime attributes are band-prefixed (`ng-cu_total`, `na-cu_total`, ...); the bare `cu_total` family exists in live `stat/device` blobs but returns empty from `stat/report` (verified live on Network 10.5), so the per-AP defaults request the prefixed forms. `start_spectrum_scan` issues `cmd/devmgr` `spectrum-scan` to populate the tables `get_spectrum_scan` reads; it takes the AP's radios offline for several minutes and drops its clients, so it requires `confirm` and supports `dry_run`.

- **`force_provision_device`**: push the stored configuration to a device now (`cmd/devmgr` `force-provision`). A direct config write to `rest/device` is stored by the controller but not always provisioned to the device — observed live: a radio channel change that sat stored-but-not-applied for the better part of an hour. Force provision closes that gap without a reboot; accepts a device id or MAC, requires `confirm`, and supports `dry_run`.
- **Controller event, alarm, and neighbor-AP visibility** (`list_events`, `list_alarms`, `list_neighboring_aps`): the reliability instruments — client disconnects/roams, AP restarts, controller escalations, and every foreign BSSID the APs hear in background scans (`stat/rogueap`, strongest first with an optional RSSI floor). On Network 10.x the classic `stat/event` and `stat/alarm`/`list/alarm` routes are retired (404/InvalidObject — verified live on 10.5); both tools fall back to the v2 system-log API (`system-log/all`, `system-log/critical`) with an epoch-ms window. On the v2 shape the client identity nests under `parameters.CLIENT`. The default event limit is 1000 — a busy home site logs several hundred events per day, and a small page silently truncates rate measurements.
- **5 GHz roaming assistant on `update_wlan`** (`roaming_assistant_enabled`, `roaming_assistant_rssi`): exposes the controller's `roaming_assistant_na_enabled`/`roaming_assistant_na_rssi` WLAN fields, which nudge clients holding a weaker 5 GHz signal than the threshold toward a better AP. The RSSI threshold is validated to the controller's accepted -90..-60 dBm range before any network I/O.

- **Smart Queue management** (`get_smart_queue_status`, `configure_smart_queue`): read and set WAN Smart Queues (fq_codel) on the WAN network config. The public interface speaks Mbps; the controller's `wan_smartq_up_rate`/`wan_smartq_down_rate` fields are kilobits per second even though the UI shows Mbps, so the tools convert on both read and write — passing the UI's number through raw shapes the line to roughly a thousandth of the intended rate (verified live: an 840 write capped a ~940 Mbps line at 0.84 Mbps). A regression test pins the wire payload.
- **`tagged_vlan_mgmt` on port profiles**: current controllers drive tagged VLAN handling from `tagged_vlan_mgmt` and derive the legacy `forward` field from it, so sending only `forward` made it impossible to create an access port. Create/update and the `PortProfile` model now support `auto`/`block_all`/`custom` (`block_all` is the access-port case), `forward` is documented as legacy and derived, and the update path reports any field the controller stored differently from what was requested.

### Fixed

- **`MCP_SERVER_TRANSPORT=streamable_http` crashed the server on startup (issue #159)**: FastMCP's `run()` only recognizes `"streamable-http"` (hyphen); the documented and recommended env var value, `streamable_http` (underscore, matching `stdio`/`http`/`sse`'s naming), was passed through unchanged and raised `ValueError: Unknown transport: streamable_http` the moment the server tried to start — every deployment following the README's own recommendation to prefer Streamable HTTP over SSE hit this immediately. The transport name is now translated at the single `mcp.run()` call site; `stdio`, `http`, and `sse` are unaffected.
- **`docker-compose.yml` silently dropped six `.env` settings, including SSL verification (issue #161)**: the `environment:` block forwarded `UNIFI_HOST`, `UNIFI_PORT`, `UNIFI_VERIFY_SSL`, `UNIFI_SITE`, `UNIFI_RATE_LIMIT`, and `UNIFI_TIMEOUT`, but `Settings` binds to `UNIFI_CLOUD_API_URL`, `UNIFI_LOCAL_PORT`, `UNIFI_LOCAL_VERIFY_SSL`, `UNIFI_DEFAULT_SITE`, `UNIFI_RATE_LIMIT_REQUESTS`, and `UNIFI_REQUEST_TIMEOUT` respectively. `extra="ignore"` meant every one of these fell back to its default with no warning — most visibly, `UNIFI_LOCAL_VERIFY_SSL=false` in `.env` had no effect under Docker Compose, so every local-gateway deployment with a self-signed cert (the typical UDM/UDM Pro case) failed to authenticate at all. `docker-compose.yml` and `.env.example` now use the names `Settings` actually reads; a regression test (`tests/unit/config/test_docker_compose_env_vars.py`) checks every forwarded `UNIFI_*` name against the model going forward.
- **Credentials were written to the audit log in plaintext**: tools pass their request payloads straight into `audit_action(details=...)`, and `AuditLogger.log_operation` persisted that dict verbatim — `src/utils/audit.py` never imported the `sanitize` module that sits next to it. `update_radius_profile` is the concrete case: it builds a redacted `payload_safe` but only inside its `dry_run` branch, so the real path audited the raw payload including `auth_secret` and `acct_secret`. Audit records are now redacted centrally, so this no longer depends on each call site remembering. Redaction uses a new `sanitize_credentials()` rather than the existing `sanitize_dict()`: the latter also redacts `site_id`, `name` and `mac`, and an audit trail that cannot say which site or resource was touched has lost its purpose — credentials go, identifiers stay.
- **Sensitive values leaked their last two characters**: `_redact_value` fell through to `f"***{value[-2:]}"` for every sensitive field, so `hunter2` was logged as `***r2` and a RADIUS shared secret ending `2026` as `***26`. Partial reveal is only ever appropriate for the network identifiers `PARTIAL_REDACT_FIELDS` names (MAC, IP), never for credentials: a trailing fragment both shrinks the search space and confirms guesses, and these records are persisted. Credentials are now fully redacted; MAC and IP partial reveal is unchanged.
- **`UNIFI_AUDIT_LOG_PATH` had no effect**: `audit_action` read `settings.audit_log_file`, but no such field existed on `Settings`, and `extra="ignore"` meant the environment variable was dropped without a warning — every audit record went to `audit.log` relative to the process working directory, which is not predictable under stdio transport. The field now exists and the documented variable works. `API.md` also stated a default of `audit.jsonl`; the code default is `audit.log`.
- **`UNIFI_AUDIT_LOG_ENABLED` had no effect**: the setting existed but was never read, so auditing could not be switched off. `audit_action` now honours it.
- **The audit log was created world-readable**: `open(..., "a")` with a typical umask produces mode 0644, and the file holds operation parameters. It is now created 0600.
- **`site_id` reached request paths unvalidated in 16 tool modules**: `validate_site_id` already existed (`^[a-zA-Z0-9_\-]+$`) and was applied in some modules, but 96 tools interpolated the caller's `site_id` straight into a path — `f"/ea/sites/{site_id}/rest/radiusprofile"` and equivalents in `acls`, `content_filtering`, `dhcp_reservations`, `dns_management`, `firewall_groups`, `firewall_policies`, `firewall_zones`, `qos`, `radius`, `topology`, `traffic_flows`, `vouchers`, `zbf_matrix` and three others. Nothing in `src/` URL-encodes (`quote`/`urlencode`: zero occurrences), and the client's translation regex matches `^/ea/sites/([^/]+)/(.+)$`, so a value carrying `/`, `..`, `?` or `#` moves the capture boundary and lands the request on a different path than the tool name implies: `create_radius_profile(site_id="default/../../../v2/api/site/default/firewall-policies")` POSTs a caller-chosen body to an endpoint that has no tool and no confirmation wording. The host stays pinned, so this is a path escape rather than request forgery. All 96 now validate before any network I/O. `site_manager` is exempt (four tools take `site_id: str | None`) as is `connector` (addresses consoles by `console_id`, which contains a colon).
- **An unrecognised `UNIFI_PROFILE` failed open**: an unknown value produced an empty module set, and the `... or _all_local` fallback then loaded every module — so an operator who set a profile expecting a reduced tool surface silently got the full one, with no warning. The value is now validated and logs a warning naming the profiles that exist. `API.md` also advertised a `read-only` profile value that was never implemented; that row now lists the real profiles and points at `UNIFI_READ_ONLY`.
- **`set_ap_radio_channel` silently lost radio changes**: the tool PUT the whole `stat/device` operational blob back to `rest/device/{id}`; the controller answers HTTP 200 but drops the change (observed live: a tx_power write that never stuck). It also enumerated devices on a `rest/device` collection GET that current controllers answer with NotFound. The tool now enumerates on `stat/device`, fetches the config record by id (falling back to the stat record's `radio_table` on surfaces without the per-id config GET), PUTs only `{"radio_table": ...}`, and verifies the controller's echo — reporting `success: false` plus a warning for any field the controller did not store, with the stored power figures (`stored_tx_power`, `stored_tx_power_mode`) in the result.

- **`update_dhcp_reservation` never activated the reservation**: setting a `fixed_ip` wrote the address onto the client entry but omitted `use_fixedip=true`, so the controller stored the IP inertly — the reservation never took effect and never appeared in `list_dhcp_reservations` (which filters on `use_fixedip`). The return value also hard-coded `use_fixedip: true` regardless of the controller response, masking the failure. `update_dhcp_reservation` now sets `use_fixedip=true` whenever a `fixed_ip` is provided, and both `create_dhcp_reservation` and `update_dhcp_reservation` now report the controller's actual `use_fixedip` value — falling back to the requested/known reservation state (coerced via `coerce_bool`) instead of hard-coding `true`.
- **`list_wan_connections` on Integration v1 (issue #100)**: `GET /integration/v1/sites/{site_id}/wans` returns only `id` and `name`, but `WANConnection` required `site_id`, `wan_type`, `interface` and `status`, so every response raised `ValidationError` and the tool was unusable in local API mode. Those four fields are now optional. There is no per-WAN detail route to enrich the sparse record from, so relaxing the model is the only fix.
- **`get_device_details` on Integration v1 (issue #108)**: the tool reads the Integration v1 device route but parsed the response with the legacy `Device` model, which requires `type` and `mac` and types `state` as an integer. The Integration v1 API sends `macAddress`, no `type` at all, and a string `state` (`"ONLINE"`), so every call raised `ValidationError` for every device in local API mode. Now parsed with `IntegrationDevice`, the model that matches the endpoint.
- **`IntegrationDevice.features` / `.interfaces`**: both were typed `list[str]` but the controller returns objects (`features.accessPoint`, `interfaces.ports[...]`, `interfaces.radios[...]`). This also broke `list_integration_devices` and `get_integration_device` against real hardware.
- **`list_dpi_applications` on Integration v1 (issue #108)**: `GET /integration/v1/dpi/applications` returns only `{"id": 3, "name": "ICQ"}`, but `DPIApplication` required `category_id` and typed `id` as a string, so every response raised `ValidationError` and the tool was unusable in local API mode. `category_id` is now optional, `id` accepts the numeric form the Integration v1 route sends, and `category_id`/`category_name` also accept the API's camelCase spellings.
- **`WEB` firewall matching target (issue #106)**: `MatchingTarget` was missing the `WEB` member that the UniFi controller returns for web-category rules, so any policy using it failed model validation. Because `list_firewall_policies` validates the whole payload, a single `WEB` rule made the entire policy list unavailable rather than just that one entry.
- **`get_speed_test_status` queried a nonexistent resource**: `GET cmd/devmgr/speedtest-status` exists on no controller, so every call 404'd. The state lives on the gateway's `stat/device` record — the `speedtest-status` object carries the last result (`xput_download`/`xput_upload` in Mbps, `latency` in ms, `rundate` in epoch seconds), `uplink.speedtest_status` carries the outcome string, and `speedtest-pending-interfaces` is non-empty while a test runs. The tool now reads that record, reports `running` while a test is in flight, an honest `no_result` before the first test, and omits fields the gateway does not report.
- **IndexError on writes the controller does not echo**: UniFi returns `{"data": []}` when it accepts a write without echoing the stored object, and seven call sites parsed the reply with `response.get("data", [{}])[0]`, raising IndexError after the POST/PUT had already landed. All seven now route through `first_response_item()`; `update_port_profile` re-reads the profile when the PUT is not echoed, and create/update compare the caller's fields against the stored result, attaching a `warnings` list on any mismatch (surfacing the controller rewriting `forward=native` to `customize`).
- **`get_port_mappings` / `get_device_connections` silently returned nothing for legacy ids**: topology node ids are Integration UUIDs while every other device tool speaks the legacy `_id` or a MAC, so lookups matched nothing and returned `{}`/`[]` — indistinguishable from a device that genuinely has no connections. Identifiers now resolve by node id, MAC, or name, and an unknown device raises `ResourceNotFoundError`.
- **Topology edges had null ports and speeds, and port maps dropped all but one host**: the Integration API's uplink object is only `{"deviceId"}`, so the `portIndex`/`speedMbps` keys the code read never existed. Edge detail is now joined from the legacy `stat/device`/`stat/sta` records on MAC (best-effort: a controller that refuses the legacy routes yields a graph without port detail rather than no graph). `get_port_mappings` keyed the map as port → peer, so each write clobbered the last; each port now maps to a list of peers carrying `connected_name`. Documented in `API.md`.
- **`list_firewall_zones_v2` returned `[]` when Zone-Based Firewall is off**: an empty list read as "no zones exist", which is not a state a ZBF-enabled site can be in — the built-in zones always exist once the feature is on (the integration zones route reports an explicit `api.firewall.zone-based-firewall-not-configured` 400 for the same condition). The empty case now raises a clear error pointing at the legacy firewall tools.
- **Port overrides required `portconf_id`**: a port with no `portconf_id` inherits the site default profile, and overrides that set only a name, PoE mode or speed are both valid and common — requiring it made renaming a port or turning PoE off impossible without also reassigning its profile. An override now requires `port_idx` plus at least one field to actually set.
- **`create_dhcp_reservation` failed with `api.err.MacUsed` for known clients**: the controller already holds a `rest/user` record for any client it has seen — the common case, not the edge case. The tool now looks the MAC up first (case-insensitively) and merges into the existing record with PUT, falling back to POST only for a genuinely unknown MAC.
- **Integration v1 endpoints rejected the site short name**: the client mapped UUID → short name for the legacy `/ea/` and v2 endpoints but not the reverse, so Integration v1 calls failed with `api.request.argument-type-mismatch` when given `default`. The site segment in `/integration/v{n}/sites/{site}/...` is now rewritten from either form; callers already passing the UUID are unaffected.
- **Guest portal tools called a fictional endpoint**: `/integration/v1/sites/{site}/guest-portal/config` exists in no Network version, so both tools 404'd on every controller. The configuration lives in the legacy `setting/guest_access` section: `get_guest_portal_config` translates it (with `x_*` secrets stripped), and `configure_guest_portal` gains `portal_enabled` — the switch that turns the captive portal off while `purpose=guest` networks keep their isolation. Portal-customization keys are written only if the controller version reports them, with anything else named in `skipped_fields`.

- **`get_dpi_statistics` / `list_top_applications` always reported zero applications**: the `stat/dpi` path they queried answers with nothing on current controllers. Counters are now read from the `stat/sitedpi` report (POST with type `by_app`/`by_cat`). The `time_range` parameter is removed — the counters are lifetime totals and no variant of the endpoint accepts a window. Controllers that run traffic identification through the flow engine report an empty result with a note pointing at the flow tools. Documented in `API.md`.
- **Spectrum tools queried a nonexistent site-wide path**: spectrum data is per access point at `stat/spectrum-scan/{ap_mac}`; the site-wide `stat/spectrumscan` path 404'd on every call. `get_spectrum_scan` queries one AP or enumerates the site's APs, returning the controller's per-AP shape; `list_spectrum_interference` flattens each radio's `spectrum_table` annotated with AP MAC and radio. An AP that has never run an RF scan reports empty tables — a state, not an error.
- **`get_speed_test_history` queried a nonexistent resource**: `rest/speedtest` fails every call with `api.err.InvalidObject`; results are stored in the `stat/report/archive.speedtest` report (`xput_download`/`xput_upload` in Mbps, `latency` in ms, `time` in epoch milliseconds). The tool now POSTs the report query with a caller-selectable window (`hours`, default one week) and returns ISO 8601 timestamps.
- **`list_backups` and the backup schedule tools used invented routes**: `list_backups` requested the site-less `/api/backup/list-backups`, which the controller rejects with `api.err.NoSiteContext` on an HTTP 401 — surfaced as "Authentication failed". Backups are listed with `POST cmd/backup {"cmd": "list-backups"}`. `get_backup_schedule`/`configure_backup_schedule` used a `rest/backup/schedule` resource that does not exist (`api.err.InvalidObject`); the schedule is the `auto_backup` settings section. UniFi OS consoles do not carry that section — their scheduled backups are console-level — so reads report `configured: false` with an explanation and writes refuse with the same; self-hosted controllers read and write the section's real fields.
- **Retry hangs (issue #97)**: with the default 30 s request timeout and 3 retries, one logical request can burn ~127 s (4 attempts plus backoff), and a tool that authenticates before its data call stacks two of those — the reported four-minute hangs. Retries now also respect a total wall-clock budget (`UNIFI_RETRY_TOTAL_TIMEOUT`, default 60 s) covering all attempts and backoff waits, failing fast with a message naming the budget and the knob.
- **Hotspot package tools (issue #108, item B3)**: `/integration/v1/sites/{site}/hotspot/packages` 404s and no Integration v1 route for packages exists; the classic `rest/hotspotpackage` surface answers. Duration is hours-granular (sent as `hours`, rounded up from `duration_minutes`), price is `amount` with `currency` alongside. The previous bandwidth/quota/enabled parameters are removed rather than remapped: the controller's validator never acknowledged any of them.
- **Voucher tools (issue #108, items B1 and A3)**: every tool called `/integration/v1/sites/{site}/vouchers`, which no controller serves; the documented surface is `/v1/sites/{siteId}/hotspot/vouchers`. The `Voucher` model now mirrors the documented camelCase response (only `id` required, absent fields omitted), `create_vouchers` sends the documented body (`name`, `timeLimitMinutes`), generation replies nested under a `vouchers` key are unwrapped, `code` accepts the string form live controllers send, and `bulk_delete_vouchers` reads `{"vouchersDeleted": N}` and refuses an empty filter.
- **`get_application_info` (issue #108, item B5)**: requested an `application/info` resource, which no controller serves, so the tool 404'd everywhere. Now calls the documented Integration API info route (prefix varies by API mode: `/v1/info` on Cloud V1, `/proxy/network/integration/v1/info` on local gateways) and reports its `applicationVersion` as `application_version`, passing any additional keys a controller sends through verbatim.
- **`list_pending_devices` (issue #101)**: the Integration v1 API has no `/devices/pending` route — the path matches `/devices/{deviceId}`, so the controller rejects the literal string `pending` with `api.request.argument-type-mismatch`. Unadopted devices are read from the legacy `stat/device` route, flagged `adopted=false`, with client-side pagination.
- **Wired clients reported zero traffic**: the sta route reports wired clients' counters as `wired-tx_bytes`, `wired-rx_bytes`, `wired-tx_packets` and `wired-rx_packets`; every client tool read only the plain keys. The `Client` model now fills the plain fields from the `wired-` keys in a before-validator, and `get_client_statistics` reads both key families. Wireless clients are unaffected: their plain keys are present and win.
- **Per-network and per-WLAN statistics were site-wide totals**: networks were matched to clients by VLAN read from a `vlan_id` key `networkconf` does not have (the field is `vlan`), so every network matched every client via `None == None`; the WLAN matcher's `or not is_wired` clause admitted every wireless client to every WLAN; and `get_subnet_info` always reported `vlan_id: null`. Clients are now matched on `network_id`, WLANs on `essid` alone, and byte sums also read the `wired-tx_bytes`/`wired-rx_bytes` keys wired clients report, so a network of wired servers stops reporting zero traffic.

### Changed

- **BREAKING - nine write tools now require `confirm`** (`update_protect_device`, `update_protect_light`, `update_protect_sensor`, `update_protect_chime`, `update_protect_viewer`, `create_protect_live_view`, `update_protect_live_view`, `send_protect_alarm_webhook`, `run_speed_test`): these issued a PATCH or POST with no gate at all — no `confirm`, no `dry_run` — while every other mutating tool in the server requires confirmation. Nothing stood between a tool call and a write to a Protect device, a live-view change, an alarm webhook, or a WAN speed test. All nine now take `confirm` and `dry_run` and route through `validate_confirmation`, matching the other 76 call sites, and all nine return a preview under `dry_run` without issuing a request. Callers that used these tools without `confirm` must add `confirm=True`. The Protect tools' one-line docstrings gained full `Args` sections, since documenting only the new parameters would have left the rest undocumented.
- **SSE transport documented as deprecated in favor of Streamable HTTP (issue #96)**: `mcp-remote` and similar client proxies can send the first tool call before the SSE `initialize` handshake completes, which the `mcp` SDK rejects with `Received request before initialization was complete` — a timing issue upstream in the SSE transport, not in this server's tool logic. README and `.env.example` now lead with `streamable_http` for network-accessible deployments; SSE remains available for backward compatibility.
- **`list_wan_connections` output contract**: optional fields now default to `None` instead of `[]`/`False` (`dns_servers`, `is_backup`), and the tool dumps with `exclude_none=True`, so fields the controller does not report are omitted rather than emitted as `null`. An absent key means "not reported", never "empty" or "false" — consumers must look keys up defensively. Documented in `API.md`.
- **`get_device_details` output shape**: now the Integration v1 shape — `mac_address`/`ip_address` rather than `mac`/`ip`, a string `state`, no `type` — and dumped with `exclude_none=True` so unreported keys are omitted rather than emitted as `null`. Documented in `API.md`. The legacy `/ea/` shape is unchanged for `search_devices` and `list_devices_by_type`.
- **`list_dpi_applications` / `list_dpi_categories` output contract**: optional fields now default to `None` instead of `[]`/`True` (`protocols`, `ports`, `enabled`), and both tools dump with `exclude_none=True`, so fields the controller does not report are omitted rather than emitted as `null`. An absent key means "not reported", never "empty" or "disabled". Both tools are now documented in `API.md`.

### Tests

- **Patch-coverage follow-up for merged PRs #122/#124/#126/#128**: covers the lines codecov flagged after merge — the voucher unwrap's bare-list filter and scalar fallback, the 429 rate-limit retry path (both the within-budget retry and budget-exhausted give-up, which surfaces as `APIError` via the request catch-all), both `list_backups` endpoint modes, the weekday-name validation and cloud endpoint in `configure_backup_schedule`, and the spectrum tools' malformed-payload guards.

- Corrected `test_update_ip` to assert the PUT body enables `use_fixedip`, and added `test_update_name_only_does_not_enable_fixedip` to ensure metadata-only updates don't flip the flag.
- **Fixture MAC moved to the RFC 7042 documentation range**: `test_firewall_policy.py` used a sample client MAC whose OUI belongs to Proxmox/QEMU — a real VM's address from someone's network rather than a synthetic value. Replaced with `00:00:5e:00:53:01` from the range RFC 7042 reserves for documentation; the value is opaque to every assertion that reads it.

## [0.4.0] - 2026-07-19

### Added

- **Protect Phase 3 docs update**: documented the new read-only Protect surfaces in `API.md`, `README.md`, and `docs/UNIFI_API.md` so the repo now calls out devices, live views, and events as wired where applicable.
- **Protect device surface**: added `list_protect_devices` as the read-only device update/message tool for the Phase 3 Protect module.
- **Protect views surface**: added `list_protect_views` as the live views / viewer metadata tool for the Phase 3 Protect module.
- **Protect events surface**: added `list_protect_events` as the read-only Protect event / alarm notification tool for the Phase 3 Protect module.

## [0.2.4] - 2026-02-19

### Fixed

- **Critical startup bug (issue #42)**: `ImportError: cannot import 'config' from 'agnost'` prevented the server from starting for all users, even when `AGNOST_ENABLED=false`. Root cause: `agnost` v0.1.13 removed the `config` export, and the old code imported it unconditionally at module top-level. Fixed by moving agnost imports inside the conditional block — they now only execute when `AGNOST_ENABLED=true` and `AGNOST_ORG_ID` is set, and any import or runtime failure is gracefully caught and logged as a warning.

### Tests

- Added `tests/unit/test_main_agnost_import.py` with 3 regression tests covering missing `config` export, agnost not installed, and agnost disabled scenarios.
- Test count: 1,159 passing (up from 1,156).

## [0.2.3] - 2026-02-18

### Added

**RADIUS & Guest Portal — Complete CRUD (4 new tools)**

- `get_radius_account` — Retrieve a single RADIUS account by ID; password field auto-redacted
- `update_radius_account` — Update username, password, VLAN, tunnel type, enabled status, and notes; confirm/dry-run support
- `get_hotspot_package` — Retrieve a single hotspot package by ID
- `update_hotspot_package` — Update name, duration, bandwidth limits, quotas, price, currency, and enabled status; confirm/dry-run support

These complete full CRUD for RADIUS accounts and hotspot packages. Phase 6 (Enhanced RADIUS & Guest Portal) is now feature-complete.

### Fixed

- **QoS Tools**: Fixed runtime `TypeError` in 6 `audit_action` calls in `qos.py` that incorrectly used `action=` keyword argument instead of the required `action_type=`. Affected `create_qos_profile`, `update_qos_profile`, `configure_smart_queue`, `disable_smart_queue`, `create_traffic_route`, `update_traffic_route`. Would have crashed at runtime whenever audit logging was enabled.
- **Site Manager**: Removed duplicate `@require_site_manager` decorator on `get_sdwan_config_status` (was applied twice — redundant and confusing).
- **Topology Tests**: Fixed 6 `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` warnings in the topology test suite. Root cause: 6 tests called `client.settings.get_integration_path()` through an auto-created `AsyncMock` (because `mock_instance.settings` was not set). Fixed by adding `mock_instance.settings = mock_settings` to each affected test.
- **Backup Client**: Added 3 missing methods to `UniFiClient` that `backups.py` calls at runtime:
  - `get_restore_status(operation_id)` — returns `not_supported` stub (endpoint not in UniFi API)
  - `configure_backup_schedule(...)` — `PUT /proxy/network/api/s/{site}/rest/backup/schedule`
  - `get_backup_schedule(site_id)` — `GET /proxy/network/api/s/{site}/rest/backup/schedule`
  Previously these silently fell back to an `AttributeError` handler in `backups.py`.

### Tests

- Added `TestUniFiClientBackupMethods` with 5 tests covering the new backup client methods.
- Test count: 1,156 passing (up from 1,128).
- Zero `RuntimeWarning` coroutine warnings (down from 6).

## [0.2.2] - 2026-02-16

### 🎉 Feature Release - Port Profile Management & Security Hardening

This release adds comprehensive switch port management capabilities, fixes critical security vulnerabilities, corrects API endpoint issues, and improves code quality across the codebase.

### Added

**Port Profile & Switch Port Management (8 new tools)**

- `list_port_profiles` - Paginated listing of switch port profiles with filtering
- `get_port_profile` - Fetch detailed port profile configuration by ID
- `create_port_profile` - Create port profiles with full configuration:
  - PoE settings (auto, passthrough, 24V, 48V, passthrough+)
  - VLAN configuration (native, trunk, excluded VLANs)
  - 802.1X port-based authentication
  - LLDP-MED voice VLAN support
  - Port speed/duplex configuration
  - Port isolation and storm control
- `update_port_profile` - Update profiles with fetch-then-merge to preserve fields
- `delete_port_profile` - Delete port profiles with existence verification
- `get_device_port_overrides` - Retrieve per-port overrides and full port table for devices
- `set_device_port_overrides` - Apply port-specific configuration:
  - Smart merge by `port_idx` (preserves other ports)
  - Full replace mode for complete reconfiguration
  - Validation of required fields (`port_idx`, `portconf_id`)
- `get_device_by_mac` - Look up devices by MAC address for port configuration

**Pydantic Models**

- `PortProfile` - Complete port profile data model with validation
- `PortOverride` - Per-port override configuration
- `PortTableEntry` - Read-only port status and statistics
- `DuplicateResourceError` - Exception for duplicate name detection

**Test Coverage**

- 75 new unit tests for port profile tools (100% of new code covered)
- Total test count: 1,068 (up from 990)
- All tests passing across Python 3.10, 3.11, 3.12

### Security

**Critical Dependency Updates (18 vulnerabilities fixed)**

- **FastMCP**: 0.1.0 → 2.14.5
  - Fixed CVE-2025-66416 (high severity)
  - Fixed auth integration confused deputy attack (high)
  - Fixed reflected XSS in callback page (medium)
  - Fixed Windows command injection (medium)
- **MCP SDK**: 1.16.0 → 1.26.0
  - Enabled DNS rebinding protection by default (high)
- **cryptography**: 43.0.0 → 46.0.5
  - Fixed SECT curve subgroup attack vulnerability (high)
- **httpx**: 0.27.0 → 0.28.1
- **pydantic**: 2.0.0 → 2.12.5
- **agnost**: 0.1.8 → 0.1.12
- **urllib3**: Added >=2.3.0 requirement
  - Fixed decompression bomb safeguards bypass (high)
  - Fixed unbounded links in decompression chain (high)
  - Fixed O(n²) streaming API DoS (high)

**Security Hardening**

- Removed `session-work.md` and `TEST_RESULTS.md` from git tracking (contained real internal IPs)
- Added both files to `.gitignore` to prevent future leaks
- Replaced PII in `SECURITY.md` (placeholder emails → GitHub Security Advisories)
- MAC address sanitization in logs and error messages (masked to `aa:bb:cc:xx:xx:xx`)
- Git history verified clean - no secrets ever committed

### Fixed

**API Endpoint & Payload Corrections**

- **RADIUS Tools** - Corrected endpoints and field names:
  - Profile endpoints: `/integration/v1/.../radius/profiles` → `/ea/sites/.../rest/radiusprofile`
  - Account endpoints: `/integration/v1/.../radius/accounts` → `/ea/sites/.../rest/account`
  - Password field: `password` → `x_password` (actual UniFi API field)
  - VLAN field: `vlan_id` → `vlan`
  - Auto-populate `tunnel_type`/`tunnel_medium_type` when VLAN specified
  - Secrets redacted (`***REDACTED***`) in all responses
  - Fixed list response handling at 5 locations (prevents `AttributeError` on `.get()`)

- **Firewall Tools** - New payload fields for proper rule creation:
  - Added `ruleset` (default `WAN_IN`) and `rule_index` (default `2000`)
  - Added `src_networkconf_id`/`dst_networkconf_id` with type variants (default `None`, typed `str | None`)
  - Added connection state flags: `state_established`, `state_related`, `state_new`, `state_invalid`
  - Added traffic `logging` flag
  - Fixed parameter names: `source`/`destination` → `src_address`/`dst_address`

- **WLAN Tools** - New creation parameters:
  - Added `networkconf_id` - associate SSID with specific network
  - Added `ap_group_ids`/`ap_group_mode` - per-AP-group broadcasting
  - Added `wlan_bands` - band selection (`2g`, `5g`, or both)
  - Added IoT optimization and minimum data rate controls

- **Network Config Tools** - Fixed VLAN field name (`vlan_id` → `vlan`)

- **All Tools** - Boolean parameter coercion (`"true"` → `True`) for MCP JSON-RPC compatibility

**Bug Fixes**

- Fixed `dry_run` requiring `confirm=True` - `validate_confirmation()` now accepts `dry_run` parameter
- Fixed missing `DuplicateResourceError` exception (was imported but not defined)
- Fixed RADIUS response crashes where list responses were passed to `.get()` or Pydantic constructors
- Updated all 55 call sites across 16 tool modules for dry_run fix

**Code Quality**

- Added full type hints to `coerce_bool(value: bool | str | None) -> bool`
- Added full type hints to `validate_confirmation(confirm: bool | str | None, operation: str, dry_run: bool | str = False) -> None`
- Port profile tools validate responses through Pydantic models before returning
- Fixed import ordering (isort) across all files

### Changed

- Tool count: 74 → 82+ MCP tools
- Test count: 990 → 1,068 tests
- Updated version references in README.md, CLAUDE.md, pyproject.toml

### Technical Details

**Commits**

- `94277cb` - Fix RADIUS, firewall, WLAN, network endpoints/payloads (29 files)
- `20efe10` - Add port profile and device port override tools (6 files)
- `b7c0489` - Remove PII, harden repo for public release (4 files)
- `448b916` - Add missing DuplicateResourceError exception (2 files)
- `653d957` - Allow dry_run without confirm, fix firewall param names
- `360339f` - Add type hints to coerce_bool and validate_confirmation
- `d666965` - Validate port profile responses through Pydantic models
- `e77129c` - Fix MAC leak in logs/errors, firewall defaults, RADIUS response handling
- `ffe8d86` - Merge PR #35: port profile tools, API fixes, and security hardening
- `9feb15b` - Style: apply black and isort formatting fixes
- `ddaa9e9` - Fix(deps): update dependencies to address security vulnerabilities
- `5674286` - Style: fix isort import ordering
- `ffc1e6e` - Docs: update documentation for v0.2.2 release

**Statistics**

- 40 files changed (+2,726 / -1,235 lines)
- 8 new MCP tools (total: ~82)
- 75 new unit tests (total: 1,068)
- 3 new Pydantic models
- 1 new exception class
- 18 security vulnerabilities fixed
- 0 test failures
- 6 warnings (pre-existing async mock coroutines)

## [0.2.1] - 2026-01-25

### 🔧 Critical Bug Fix - Topology Tools

Fixed topology tools that were completely non-functional due to using non-existent API endpoints.

### Fixed

- **Topology Tools (5 tools)**: Rewrote all topology tools to use correct Integration API endpoints
  - Changed from non-existent `/api/s/{site}/stat/topology` to proper Integration API endpoints
  - Now uses `/v1/sites/{siteId}/devices` and `/v1/sites/{siteId}/clients`
  - Updated data model field names to match Integration API response format
  - Fixed endpoint path construction using `get_integration_path()` for proper API translation
  - Added pagination support for large device/client lists
  - Fixed network depth calculation and client connection type detection

### Added

- **Integration Test Framework**: Comprehensive test harness for real-world validation
  - Multi-environment support (6 environments: 2 local + 4 cloud)
  - API mode testing (local, cloud-v1, cloud-ea)
  - Intelligent test skipping for unsupported API features
  - Detailed reporting with pass/fail/skip statistics
  - JSON export for CI/CD integration
  - Dry-run mode for test planning
  - Test suite organization with setup/teardown hooks
- **Topology Test Suite**: 8 comprehensive tests with 100% pass rate on local APIs
- **Test Documentation**: Complete guide for writing and running integration tests

### Technical Details

**Data Model Changes**:

- `device._id` → `device.id`
- `device.mac` → `device.macAddress`
- `device.ip` → `device.ipAddress`
- `uplink.device_id` → `uplink.deviceId`
- `device.state` (int) → `device.state` (string: "CONNECTED"|other)

**Test Results**:

- 16/16 tests PASSED on local APIs (100%)
- 32/32 tests SKIPPED on cloud APIs (expected - topology not supported)
- 0 FAILED
- Total test duration: 6.97s across 6 environments

**API Limitations Documented**:

- Local APIs: Full topology support
- Cloud APIs (v1 & EA): Aggregate statistics only, no device-level data

## [0.2.0] - 2026-01-25

### 🎉 Production Release - All Features Complete

This is the definitive v0.2.0 release with all 7 planned feature phases complete, comprehensive testing, and production-ready quality.

### Added

**Phase 1: QoS Enhancements (11 tools)**

- QoS profile management (list, get, create, update, delete)
- Reference QoS profiles and ProAV templates
- Traffic routing with time-based schedules
- Application-based QoS configuration
- Coverage: 82.43% (46 tests passing)

**Phase 2: Backup & Restore (8 tools)**

- Manual and automated backup creation
- Backup listing and download with checksum verification
- Backup restore functionality
- Automated scheduling with cron expressions
- Cloud synchronization tracking
- Coverage: 86.32% (10 tests passing)

**Phase 3: Multi-Site Aggregation (4 tools)**

- Cross-site device and client analytics
- Site health monitoring and scoring
- Side-by-side site comparison
- Consolidated reporting across locations
- Coverage: 92.95% (10 tests passing)

**Phase 4: ACL & Traffic Filtering (7 tools)**

- Layer 3/4 access control list management
- Traffic matching lists (IP, MAC, domain, port groups)
- Firewall policy automation
- Rule ordering and priority management
- Coverage: 89.30-93.84%

**Phase 5: Site Management (9 tools)**

- Multi-site provisioning and configuration
- Site-to-site VPN setup
- Device migration between sites
- Advanced site settings management
- Configuration export for backup
- Coverage: 92.95% (10 tests passing)

**Phase 6: RADIUS & Guest Portal (6 tools)**

- RADIUS profile configuration (802.1X authentication)
- RADIUS accounting server support
- Guest portal customization
- Hotspot billing and voucher management
- Session timeout and redirect control
- Coverage: 69.77% (17 tests passing)

**Phase 7: Network Topology (5 tools)**

- Complete network topology graph retrieval
- Multi-format export (JSON, GraphML, DOT)
- Device interconnection mapping
- Port-level connection tracking
- Network depth analysis
- Coverage: 95.83% (29 tests passing)

### Quality Metrics

- **74 Total MCP Tools**: Comprehensive UniFi network management
- **990 Tests Passing**: Robust validation across all modules
- **78.18% Test Coverage**: 4,865 of 6,105 statements covered
- **18/18 CI/CD Checks Passing**: All quality gates met
- **Zero Security Vulnerabilities**: Clean security scans
- **30+ AI Assistant Example Prompts**: Comprehensive usage documentation

### Documentation

- Added comprehensive VERIFICATION_REPORT.md documenting complete testing and validation
- Added 30+ AI assistant example prompts across 10 categories in API.md
- Updated API.md with all 74 tools documented with examples
- Updated UNIFI_API.md with complete API endpoint reference

### Fixed

- CodeQL security alerts resolved (wrong parameter names in QoS tools)
- Secret redaction in RADIUS dry-run logging
- Pre-commit hook failures (import formatting)
- Duplicate function definitions
- Test coverage gaps in critical paths

### Changed

- License: Apache 2.0
- Architecture: All 7 feature phases complete
- Test coverage improved from 41.27% to 78.18%
- Total tests increased from 228 to 990

### Release Artifacts

- Docker: ghcr.io/enuno/unifi-mcp-server:0.2.0 (multi-arch: amd64, arm64, arm/v7)
- npm: unifi-mcp-server@0.2.0
- PyPI: unifi-mcp-server==0.2.0
- GitHub: <https://github.com/enuno/unifi-mcp-server/releases/tag/v0.2.0>

See [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md) for complete details.

---

## [0.1.4] - 2025-11-17

### Version Correction Notice

This release corrects a premature v0.2.0 release. The code is identical to v0.2.0, but v0.1.4 is the correct version number. The true v0.2.0 release is planned for Q1 2025 with complete Zone-Based Firewall implementation, full Traffic Flow monitoring, and 80%+ test coverage.

### Added

- Comprehensive WiFi tools test suite with 23 tests and 70.34% coverage
- Cloud API compatibility for Site model using Pydantic v2 validation_alias
- Support for both Cloud API (`siteId`, `isOwner`) and Local API (`_id`, `name`) schemas
- 17 comprehensive unit tests for Site model covering Cloud/Local API compatibility
- Automatic name fallback generation for Cloud API sites without explicit names

### Fixed

- **GitHub Issue #3**: Cloud API schema mismatch in Site model
  - Fixed Pydantic validation errors when using Cloud API
  - Site model now accepts `siteId` (Cloud) and `_id` (Local) field names
  - Site model now accepts `siteName` and `name` field variations
  - Added model_validator to generate fallback names from site IDs
- All 16 failing WiFi tests resolved (23/23 now passing)
  - Fixed mock return value structures to match UniFi API response format
  - Added missing `security` parameter to WLAN creation tests
  - Changed exception types from ConfirmationRequiredError to ValidationError
  - Fixed missing API call mocks for update/delete operations
  - Fixed field name assertions (passphrase → x_passphrase)
  - Rewrote statistics tests to handle dual API calls correctly
- Python 3.10 compatibility issues resolved
- Import sorting issues fixed per isort/pre-commit requirements
- Ruff linting errors in WiFi test suite resolved
- Missing ValidationError import added to Site model tests
- Traffic flows formatting with Black

### Changed

- Site model made backward compatible with existing Local API code
- Enhanced Site model with Cloud API-specific fields (`is_owner`)
- Improved test coverage from 36.83% to 41.27% overall
- Site model test coverage: 100%

### Technical Details

- All 228 tests passing
- Test coverage: 41.27%
- CI/CD pipelines: All checks passing
- Compatible with Python 3.10, 3.11, 3.12

## [0.2.0] - 2025-11-16 [PREMATURE - DO NOT USE]

### ⚠️ Version Correction Notice

**This version was published prematurely. Please use v0.1.4 instead, which contains identical code.**

The true v0.2.0 release is planned for Q1 2025 and will include:

- Complete Zone-Based Firewall (ZBF) implementation (~60% complete as of this release)
- Full Traffic Flow monitoring (~100% complete as of this release)
- Advanced QoS and traffic management
- Backup and restore operations
- 80%+ test coverage (currently 34%)

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for the complete roadmap.

### Original v0.2.0 Release Notes (For Reference)

### Added

- Comprehensive WiFi tools test suite with 23 tests and 70.34% coverage
- Cloud API compatibility for Site model using Pydantic v2 validation_alias
- Support for both Cloud API (`siteId`, `isOwner`) and Local API (`_id`, `name`) schemas
- 17 comprehensive unit tests for Site model covering Cloud/Local API compatibility
- Automatic name fallback generation for Cloud API sites without explicit names

### Fixed

- **GitHub Issue #3**: Cloud API schema mismatch in Site model
  - Fixed Pydantic validation errors when using Cloud API
  - Site model now accepts `siteId` (Cloud) and `_id` (Local) field names
  - Site model now accepts `siteName` and `name` field variations
  - Added model_validator to generate fallback names from site IDs
- All 16 failing WiFi tests resolved (23/23 now passing)
  - Fixed mock return value structures to match UniFi API response format
  - Added missing `security` parameter to WLAN creation tests
  - Changed exception types from ConfirmationRequiredError to ValidationError
  - Fixed missing API call mocks for update/delete operations
  - Fixed field name assertions (passphrase → x_passphrase)
  - Rewrote statistics tests to handle dual API calls correctly
- Python 3.10 compatibility issues resolved
- Import sorting issues fixed per isort/pre-commit requirements
- Ruff linting errors in WiFi test suite resolved
- Missing ValidationError import added to Site model tests
- Traffic flows formatting with Black

### Changed

- Site model made backward compatible with existing Local API code
- Enhanced Site model with Cloud API-specific fields (`is_owner`)
- Improved test coverage from 36.83% to 41.27% overall
- Site model test coverage: 100%

### Technical Details

- All 228 tests passing
- Test coverage: 41.27%
- CI/CD pipelines: All checks passing
- Compatible with Python 3.10, 3.11, 3.12

## [0.1.3] - 2025-01-XX

### Initial Release

- Model Context Protocol (MCP) server for UniFi Network API
- Support for Cloud and Local Controller APIs
- Device, Client, Network, and Site management tools
- Traffic flow monitoring and analysis
- Zone-based firewall (ZBF) management
- WiFi network configuration
- Comprehensive test suite

[0.2.0]: https://github.com/enuno/unifi-mcp-server/compare/v0.1.3...v0.2.0
[0.1.4]: https://github.com/enuno/unifi-mcp-server/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/enuno/unifi-mcp-server/releases/tag/v0.1.3
