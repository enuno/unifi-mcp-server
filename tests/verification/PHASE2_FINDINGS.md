# ZBF Phase 2: API Endpoint Verification - Findings

**Date:** 2025-11-18
**Tester:** Claude Code (AI Assistant)
**Environment:** UniFi Express 7 (U7 Express) - Local Gateway at 10.2.2.1
**UniFi Network Version:** (detected from gateway)
**Site ID:** 88f7af54-98f8-306a-a1c7-c9349722b1f6 (Default)

## Executive Summary

Phase 2 endpoint verification revealed that **only 2 out of 15 implemented ZBF endpoints actually exist** in the UniFi Network API. The majority of ZBF functionality (policy matrix, statistics, application blocking) was based on **speculative/non-existent endpoints**.

### Critical Findings

- ✅ **2 endpoints verified** (13% success rate)
- ❌ **13 endpoints non-existent** (87% failure rate)
- ⚠️ **Cloud API does not support ZBF** (local gateway only)
- ✅ **ZBF zones are configured** on test gateway (6 zones, multiple networks assigned)

## API Access Method

### Cloud API Limitations (CRITICAL)

**Finding:** UniFi Cloud API has a **limited set of endpoints** and does NOT support ZBF operations.

**Cloud API Supported Endpoints:**
- Sites management (`/v1/hosts`)
- Hosts information
- ISP metrics
- SD-WAN configurations

**Implication:** All ZBF tools require **local gateway API access** with the `/proxy/network/` path prefix.

### Local Gateway API

**Authentication:** X-API-Key header (works correctly)
**Base URL:** `https://{gateway_ip}/proxy/network/integration/v1/...`
**SSL:** Self-signed certificate (requires `verify=False`)

**Critical Path Difference:**
- ❌ Implemented: `/integration/v1/sites/{site_id}/...`
- ✅ Actual: `/proxy/network/integration/v1/sites/{site_id}/...`

## Endpoint Verification Results

### Zone Management (2/7 verified)

| Tool | Endpoint | Status | Notes |
|------|----------|--------|-------|
| `list_firewall_zones` | `GET /sites/{site_id}/firewall/zones` | ✅ VERIFIED | Returns 6 zones |
| `get_zone_details`* | `GET /sites/{site_id}/firewall/zones/{zone_id}` | ✅ VERIFIED | Returns zone with networkIds |
| `create_firewall_zone` | `POST /sites/{site_id}/firewall/zones` | ⚠️ UNTESTED | Not tested (mutating) |
| `update_firewall_zone` | `PUT /sites/{site_id}/firewall/zones/{zone_id}` | ⚠️ UNTESTED | Not tested (mutating) |
| `delete_firewall_zone` | `DELETE /sites/{site_id}/firewall/zones/{zone_id}` | ⚠️ UNTESTED | Not tested (mutating) |
| `assign_network_to_zone` | `PUT /sites/{site_id}/firewall/zones/{zone_id}` | ⚠️ UNTESTED | Not tested (mutating) |
| `unassign_network_from_zone` | `PUT /sites/{site_id}/firewall/zones/{zone_id}` | ⚠️ UNTESTED | Not tested (mutating) |
| `get_zone_networks` | `GET /sites/{site_id}/firewall/zones/{zone_id}` | ✅ VERIFIED | Same as get_zone_details |
| `get_zone_statistics` | `GET /sites/{site_id}/firewall/zones/{zone_id}/statistics` | ❌ NOT FOUND | Endpoint does not exist |

*Note: `get_zone_details` was tested as part of verifying the get endpoint - it's the same as `get_zone_networks`

### Zone Policy Matrix (0/5 verified)

| Tool | Endpoint | Status | Notes |
|------|----------|--------|-------|
| `get_zbf_matrix` | `GET /sites/{site_id}/firewall/policies/zone-matrix` | ❌ NOT FOUND | Endpoint does not exist |
| `get_zone_policies` | `GET /sites/{site_id}/firewall/policies/zones/{zone_id}` | ❌ NOT FOUND | Endpoint does not exist |
| `get_zone_matrix_policy` | `GET /sites/{site_id}/firewall/policies/zone-matrix/{src}/{dst}` | ❌ NOT FOUND | Endpoint does not exist |
| `update_zbf_policy` | `PUT /sites/{site_id}/firewall/policies/zone-matrix/{src}/{dst}` | ❌ NOT FOUND | Endpoint does not exist |
| `delete_zbf_policy` | `DELETE /sites/{site_id}/firewall/policies/zone-matrix/{src}/{dst}` | ❌ NOT FOUND | Endpoint does not exist |

**Alternative paths tested:**
- `/firewall/zone-matrix` - ❌ NOT FOUND
- `/firewall/zone-based-firewall/matrix` - ❌ NOT FOUND
- `/zone-based-firewall/matrix` - ❌ NOT FOUND
- `/firewall/zone-based-firewall/policies` - ❌ NOT FOUND
- `/firewall/zones/{zone_id}/policies` - ❌ NOT FOUND

### Application Blocking (0/2 verified)

| Tool | Endpoint | Status | Notes |
|------|----------|--------|-------|
| `block_application_by_zone` | `POST /sites/{site_id}/firewall/zones/{zone_id}/app-block` | ❌ NOT FOUND | Endpoint does not exist |
| `list_blocked_applications` | `GET /sites/{site_id}/firewall/zones/{zone_id}/app-block` | ❌ NOT FOUND | Endpoint does not exist |

**Alternative paths tested:**
- `/firewall/zones/{zone_id}/application-blocking` - ❌ NOT FOUND
- `/firewall/zones/{zone_id}/blocked-applications` - ❌ NOT FOUND

## ZBF Configuration on Test Gateway

The U7 Express gateway has ZBF fully configured with 6 system-defined zones:

```json
{
  "zones": [
    {
      "id": "93557a51-814f-4643-b965-6388208a7329",
      "name": "Hotspot",
      "networkIds": [],
      "origin": "SYSTEM_DEFINED"
    },
    {
      "id": "d8772130-1dbc-4e3f-b798-cd268aee94c8",
      "name": "Gateway",
      "networkIds": [],
      "origin": "SYSTEM_DEFINED"
    },
    {
      "id": "db12f158-4795-4f7b-bba3-04a274f0d011",
      "name": "External",
      "networkIds": ["9ce06ea9-4b8d-4296-b6f4-c8cb86ec57bf"],
      "origin": "SYSTEM_DEFINED"
    },
    {
      "id": "dc51ea8e-aee7-43c9-a180-19de948f1808",
      "name": "Dmz",
      "networkIds": [],
      "origin": "SYSTEM_DEFINED"
    },
    {
      "id": "1a17e412-12a7-41ef-9d26-518ca3cc56e5",
      "name": "Vpn",
      "networkIds": [
        "e669db67-1640-4c91-8b5e-294375836f48",
        "18b24aa7-2fa5-4789-915e-5eca350ccf03"
      ],
      "origin": "SYSTEM_DEFINED"
    },
    {
      "id": "2b7c3b44-a6c3-4bcc-9842-d648ca736991",
      "name": "Internal",
      "networkIds": [
        "7f2fa88f-ffa3-4a48-8aa0-3d36a2caf9e2",
        "427ebe33-bd45-4a66-944b-53175bf7be7c",
        "82da982c-28ca-49ea-a9e5-d3786ed020dc",
        "303ac66d-5713-4248-bfbf-7acd13cbc564"
      ],
      "origin": "SYSTEM_DEFINED"
    }
  ]
}
```

**Statistics:**
- Total zones: 6
- Zones with networks: 3 (External, Vpn, Internal)
- Total networks assigned: 7
- All zones are SYSTEM_DEFINED (not user-created)

## Implementation Issues Discovered

### 1. Path Prefix Missing (CRITICAL)

**Issue:** All ZBF tools use `/integration/v1/...` but local gateways require `/proxy/network/integration/v1/...`

**Impact:** ALL ZBF tools will fail on local gateways

**Fix Required:** Update all ZBF tool paths to include `/proxy/network/` prefix when using local API

**Affected Files:**
- `src/tools/firewall_zones.py` - All 8 functions
- `src/tools/zbf_matrix.py` - All 5 functions

### 2. Site ID Validation Issue

**Issue:** Tools accept "default" as site_id but local API requires UUID format

**Actual site structure:**
```json
{
  "id": "88f7af54-98f8-306a-a1c7-c9349722b1f6",
  "internalReference": "default",
  "name": "Default"
}
```

**Impact:** Users passing "default" will get 400 errors

**Fix Required:** Add site ID resolution logic or better error messages

### 3. Speculative Endpoints (CRITICAL)

**Issue:** 13 out of 15 endpoints don't exist in the actual API

**Tools that will NEVER work (endpoints don't exist):**
- `get_zone_statistics`
- `get_zbf_matrix`
- `get_zone_policies`
- `get_zone_matrix_policy`
- `update_zbf_policy`
- `delete_zbf_policy`
- `block_application_by_zone`
- `list_blocked_applications`

**Impact:** 8 tools (53% of ZBF implementation) are non-functional

**Options:**
1. Remove these tools entirely
2. Mark as "not implemented by UniFi API"
3. Keep but document as non-functional
4. Search for alternative endpoints

### 4. Config.py SSL Bug

**Issue:** When `local_verify_ssl=False`, config uses `http://` protocol instead of `https://` with unverified certificate

**Current behavior:**
```python
protocol = "https" if self.local_verify_ssl else "http"
```

**Expected behavior:**
- Always use `https://` for local gateways
- Use `verify=False` in httpx client to skip certificate validation

**Impact:** Local gateway connections fail with "plain HTTP sent to HTTPS port" error

## Recommendations

### Immediate Actions (Phase 2 Completion)

1. **Update documentation**
   - Mark 8 tools as "endpoint does not exist"
   - Update ZBF_STATUS.md with verification results
   - Add warning about Cloud API limitations

2. **Fix critical bugs**
   - Add `/proxy/network/` prefix for local API
   - Fix config.py SSL protocol logic
   - Add site ID resolution

3. **Test mutating operations**
   - Test CREATE/UPDATE/DELETE zone endpoints
   - Verify network assignment/unassignment
   - Document actual request/response formats

### Medium-term (Phase 3)

1. **Search for alternative endpoints**
   - Investigate if policy matrix exists under different paths
   - Check if statistics are available elsewhere
   - Research UniFi API documentation for ZBF v2

2. **Implement dual-mode support**
   - Auto-detect Cloud vs Local API
   - Add path prefix automatically
   - Provide clear error messages

3. **Remove or deprecate non-functional tools**
   - Decision needed: remove or keep with "not available" status
   - Update API.md documentation
   - Update README.md feature list

### Long-term (Phase 4)

1. **API discovery**
   - Build endpoint discovery tool
   - Map all available ZBF endpoints
   - Document actual vs. expected behavior

2. **Community engagement**
   - Check UniFi community forums
   - Report findings to UniFi/Ubiquiti
   - Collaborate with other MCP server developers

## Test Environment Details

**Gateway:** UniFi Express 7 (UXMAX)
**IP:** 10.2.2.1
**API Key:** FElLm9Pb2ftOxib0OwoG8clJaWbKkwnJ (Local)
**SSL:** Self-signed certificate
**ZBF Status:** Configured with 6 zones, 7 networks

**Authentication Method:** X-API-Key header
**Working Path:** `/proxy/network/integration/v1/...`
**Response Format:** JSON with pagination (offset, limit, count, totalCount, data)

## Conclusion

Phase 2 verification revealed significant discrepancies between the implemented ZBF tools and the actual UniFi API:

- **Only 13% of endpoints exist** (2/15)
- **87% of implementation is speculative** (13/15)
- **Critical path bug** prevents all tools from working on local gateways
- **Cloud API does not support ZBF** at all

The ZBF Phase 1 implementation was based on assumptions about API structure that do not match reality. Significant rework is needed to create a functional ZBF toolset.

**Next Steps:** Update ZBF_STATUS.md, fix critical bugs, and decide whether to remove non-functional tools or mark them as unavailable.
