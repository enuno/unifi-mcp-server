# Implementation Plan: Security Fix & P0 Updates

## Part 1: Resolve Dependabot CVE-2025-69872 (diskcache vulnerability)

### Problem Statement

**Vulnerability**: CVE-2025-69872 - DiskCache has unsafe pickle deserialization
**Severity**: Medium (CVSS 4.0 score: 5.2)
**Affected Package**: diskcache <= 5.6.3
**Status**: No patched version available yet

**Our Dependency Chain**:

```
unifi-mcp-server
└── fastmcp==2.14.5
    └── py-key-value-aio[disk,keyring,memory]
        └── diskcache==5.6.3 (via [disk] extra)
```

**Impact Assessment**:

- ✅ **NOT VULNERABLE** - We don't use FastMCP's disk-based key-value store feature
- ✅ We use Redis for optional caching
- ✅ FastMCP's disk cache feature is unused in our codebase
- ⚠️  The vulnerable package is still installed, triggering Dependabot alerts

### Proposed Solution: Override FastMCP's Dependencies

Use uv's `tool.uv.override-dependencies` to exclude the `[disk]` extra.

**Pros**: Prevents installation of unused dependency, reduces attack surface
**Cons**: Requires uv-specific configuration

### Implementation Steps

1. **Update pyproject.toml** - Add uv dependency override
2. **Regenerate lock file** - `uv lock --upgrade-package py-key-value-aio`
3. **Update SECURITY.md** - Document the vulnerability and mitigation
4. **Add security test** - Verify diskcache is not installed
5. **Test baseline** - Run full test suite
6. **Commit changes** - Reference CVE in commit message
7. **Dismiss Dependabot alert** - Reference security documentation

---

## Part 2: P0 (Priority 0 - Critical) Updates

### Current Status

**v0.2.0 P0 features:**

- ✅ Zone-Based Firewall - IMPLEMENTED (7 tools)
- ✅ Traffic Flows Monitoring - IMPLEMENTED (15 tools)

**v0.3.0 P0 features:**

- ⏳ SD-WAN Management - BLOCKED by Site Manager API

### Next P0 Work: Complete Site Manager API Foundation

SD-WAN Management (P0) requires Site Manager API. Recently documented endpoints:

- ISP Metrics (Get/Query ISP Metrics)
- SD-WAN Config Visibility (List/Get configs, Get status)
- Version Control, Host Management

**✨ MAJOR DISCOVERY (2026-02-16):**

Site Manager API uses **API Key authentication** (X-API-Key header), NOT OAuth/SSO!
This is the same authentication we already use for Cloud API. No OAuth implementation needed.

**Revised Timeline:** Phase 1 reduced from 2-3 weeks to 3-5 days.

**Implementation Phases** (Revised):

#### Phase 1: Extend API Client for Site Manager (3-5 days) ⚡ Much Faster

- Extend existing `UniFiAPIClient` to support Site Manager endpoints
- Use existing API key authentication (X-API-Key header)
- Add Site Manager base URL: `https://api.ui.com/v1/`
- Rate limiting: 10,000 req/min (v1 stable)

#### Phase 2: ISP Metrics Endpoints (3-5 days)

- `get_isp_metrics`, `query_isp_metrics` tools
- New Pydantic models and tests

#### Phase 3: SD-WAN Config Visibility (3-5 days)

- `list_sdwan_configs`, `get_sdwan_config`, `get_sdwan_config_status` tools
- Read-only visibility for now

#### Phase 4: Host & Version Management (2-3 days)

- `list_hosts`, `get_host`, `get_version_control` tools

### Priority Order

1. **Fix security issue** (Part 1) - Immediate (~1-2 hours)
2. **OAuth/SSO Authentication** (Phase 1) - Foundation for Site Manager API
3. **ISP Metrics** (Phase 2) - High value monitoring
4. **SD-WAN Config Visibility** (Phase 3) - Unblocks SD-WAN Management P0
5. **Start SD-WAN Management** - Once Site Manager API is ready

### Estimated Timeline

- **Part 1 (Security Fix)**: 1-2 hours
- **Part 2 (Complete Site Manager API)**: 3-4 weeks
  - Phase 1 (OAuth): 2-3 weeks
  - Phase 2 (ISP Metrics): 3-5 days
  - Phase 3 (SD-WAN Visibility): 3-5 days
  - Phase 4 (Host Management): 2-3 days

---

## Decision Point

Should we proceed with:

- **Option A**: Part 1 only (security fix, ~1-2 hours)
- **Option B**: Part 1 + Part 2 Phase 1 (security + OAuth foundation, ~2-3 weeks)
- **Option C**: Complete plan (Parts 1 & 2, ~3-4 weeks total)

**Recommended**: Option B - Fix security issue, then start OAuth implementation as foundation for future P0 work.
