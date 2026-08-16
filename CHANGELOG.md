# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`update_dhcp_reservation` never activated the reservation**: setting a `fixed_ip` wrote the address onto the client entry but omitted `use_fixedip=true`, so the controller stored the IP inertly — the reservation never took effect and never appeared in `list_dhcp_reservations` (which filters on `use_fixedip`). The return value also hard-coded `use_fixedip: true` regardless of the controller response, masking the failure. `update_dhcp_reservation` now sets `use_fixedip=true` whenever a `fixed_ip` is provided, and both `create_dhcp_reservation` and `update_dhcp_reservation` now report the controller's actual `use_fixedip` value — falling back to the requested/known reservation state (coerced via `coerce_bool`) instead of hard-coding `true`.
- **`list_wan_connections` on Integration v1 (issue #100)**: `GET /integration/v1/sites/{site_id}/wans` returns only `id` and `name`, but `WANConnection` required `site_id`, `wan_type`, `interface` and `status`, so every response raised `ValidationError` and the tool was unusable in local API mode. Those four fields are now optional. There is no per-WAN detail route to enrich the sparse record from, so relaxing the model is the only fix.
- **`get_device_details` on Integration v1 (issue #108)**: the tool reads the Integration v1 device route but parsed the response with the legacy `Device` model, which requires `type` and `mac` and types `state` as an integer. The Integration v1 API sends `macAddress`, no `type` at all, and a string `state` (`"ONLINE"`), so every call raised `ValidationError` for every device in local API mode. Now parsed with `IntegrationDevice`, the model that matches the endpoint.
- **`IntegrationDevice.features` / `.interfaces`**: both were typed `list[str]` but the controller returns objects (`features.accessPoint`, `interfaces.ports[...]`, `interfaces.radios[...]`). This also broke `list_integration_devices` and `get_integration_device` against real hardware.
- **`list_dpi_applications` on Integration v1 (issue #108)**: `GET /integration/v1/dpi/applications` returns only `{"id": 3, "name": "ICQ"}`, but `DPIApplication` required `category_id` and typed `id` as a string, so every response raised `ValidationError` and the tool was unusable in local API mode. `category_id` is now optional, `id` accepts the numeric form the Integration v1 route sends, and `category_id`/`category_name` also accept the API's camelCase spellings.
- **`WEB` firewall matching target (issue #106)**: `MatchingTarget` was missing the `WEB` member that the UniFi controller returns for web-category rules, so any policy using it failed model validation. Because `list_firewall_policies` validates the whole payload, a single `WEB` rule made the entire policy list unavailable rather than just that one entry.
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

- **`list_wan_connections` output contract**: optional fields now default to `None` instead of `[]`/`False` (`dns_servers`, `is_backup`), and the tool dumps with `exclude_none=True`, so fields the controller does not report are omitted rather than emitted as `null`. An absent key means "not reported", never "empty" or "false" — consumers must look keys up defensively. Documented in `API.md`.
- **`get_device_details` output shape**: now the Integration v1 shape — `mac_address`/`ip_address` rather than `mac`/`ip`, a string `state`, no `type` — and dumped with `exclude_none=True` so unreported keys are omitted rather than emitted as `null`. Documented in `API.md`. The legacy `/ea/` shape is unchanged for `search_devices` and `list_devices_by_type`.
- **`list_dpi_applications` / `list_dpi_categories` output contract**: optional fields now default to `None` instead of `[]`/`True` (`protocols`, `ports`, `enabled`), and both tools dump with `exclude_none=True`, so fields the controller does not report are omitted rather than emitted as `null`. An absent key means "not reported", never "empty" or "disabled". Both tools are now documented in `API.md`.

### Tests

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
