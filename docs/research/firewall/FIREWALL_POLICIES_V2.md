# Endpoint Research: Firewall Policies (v2 API)

**Status:** VERIFIED ✅  
**Verified on:** UniFi Network (UDM-Pro-Max, firmware current as of 2026-04-05)  
**Verified date:** 2026-04-05  
**Verified by:** Live curl probes against 192.168.100.1  
**Controller hardware:** UDM-Pro-Max

---

## Endpoint Details

| Field | Value |
|-------|-------|
| **Portal docs path** | `GET/PUT/PATCH /v1/sites/{siteId}/firewall/policies/{firewallPolicyId}` |
| **Code path (actual)** | `GET/PUT /proxy/network/v2/api/site/{site}/firewall-policies/{id}` |
| **Version discrepancy** | YES — portal documents integration v1 API (camelCase, different field names). Code uses v2 network API (snake_case, different schema). See discrepancy table below. |
| **Auth required** | API key (`X-API-KEY` header) |
| **Local API only** | Yes |

---

## GET Response — Actual Shape (v2)

Full response from a predefined policy:

```json
{
  "_id": "6842f4b49bb16a6d2f2e4be96842f4b49bb16a6d2f2e4be92147483647",
  "action": "ALLOW",
  "connection_state_type": "ALL",
  "connection_states": [],
  "create_allow_respond": true,
  "destination": {
    "match_opposite_ports": false,
    "matching_target": "ANY",
    "port_matching_type": "ANY",
    "zone_id": "6842f4b49bb16a6d2f2e4be9"
  },
  "enabled": true,
  "icmp_typename": "ANY",
  "icmp_v6_typename": "ANY",
  "index": 2147483647,
  "ip_version": "BOTH",
  "logging": false,
  "match_ip_sec": false,
  "match_opposite_protocol": false,
  "name": "Allow All Traffic",
  "origin_id": "684df23e552f171c0ae79aa7",
  "predefined": true,
  "protocol": "all",
  "schedule": {
    "mode": "ALWAYS"
  },
  "source": {
    "match_opposite_ports": false,
    "matching_target": "ANY",
    "port_matching_type": "ANY",
    "zone_id": "6842f4b49bb16a6d2f2e4be9"
  }
}
```

Full response from a user-defined policy (richer example with IP matching):

```json
{
  "_id": "69b9c04afce5cfb6d289ec4c",
  "action": "ALLOW",
  "connection_state_type": "RESPOND_ONLY",
  "connection_states": [],
  "create_allow_respond": false,
  "description": "",
  "destination": {
    "ips": ["192.168.30.12"],
    "match_opposite_ips": false,
    "match_opposite_ports": false,
    "matching_target": "IP",
    "matching_target_type": "SPECIFIC",
    "port": "53",
    "port_matching_type": "SPECIFIC",
    "zone_id": "6842f4b49bb16a6d2f2e4be9"
  },
  "enabled": true,
  "icmp_typename": "ANY",
  "icmp_v6_typename": "ANY",
  "index": 10000,
  "ip_version": "IPV4",
  "logging": false,
  "match_ip_sec": false,
  "match_opposite_protocol": false,
  "name": "Internal DNS",
  "predefined": false,
  "protocol": "tcp_udp",
  "schedule": {
    "mode": "ALWAYS"
  },
  "source": {
    "ips": ["192.168.20.0/24"],
    "match_mac": false,
    "match_opposite_ips": false,
    "match_opposite_ports": false,
    "matching_target": "IP",
    "matching_target_type": "SPECIFIC",
    "port_matching_type": "ANY",
    "zone_id": "6842f4b49bb16a6d2f2e4be9"
  }
}
```

### Complete field inventory (v2 GET)

| Field | Type | Notes |
|-------|------|-------|
| `_id` | string | Policy ID |
| `action` | string | `"ALLOW"`, `"BLOCK"` — flat string, NOT an object |
| `connection_state_type` | string | `"ALL"`, `"RESPOND_ONLY"`, `"CUSTOM"` |
| `connection_states` | array | e.g. `["NEW", "ESTABLISHED"]` — empty when `connection_state_type` is not CUSTOM |
| `create_allow_respond` | boolean | |
| `description` | string | Optional, present on user-defined policies |
| `destination` | object | See source/destination shape below |
| `enabled` | boolean | |
| `icmp_typename` | string | `"ANY"` or specific ICMP type |
| `icmp_v6_typename` | string | `"ANY"` or specific ICMPv6 type |
| `index` | integer | Policy ordering. Predefined rules use `2147483647` |
| `ip_version` | string | `"IPV4"`, `"IPV6"`, `"BOTH"` |
| `logging` | boolean | |
| `match_ip_sec` | boolean | |
| `match_opposite_protocol` | boolean | |
| `name` | string | |
| `origin_id` | string | ID of origin config entry |
| `predefined` | boolean | True for system rules |
| `protocol` | string | `"all"`, `"tcp"`, `"udp"`, `"tcp_udp"`, `"icmpv6"` |
| `schedule` | object | `{"mode": "ALWAYS"}` minimum |
| `source` | object | See source/destination shape below |

### source / destination object shape

| Field | Type | Notes |
|-------|------|-------|
| `zone_id` | string | Required — which zone |
| `matching_target` | string | `"ANY"`, `"IP"`, `"NETWORK"`, `"CLIENT"` |
| `matching_target_type` | string | `"SPECIFIC"` when matching IPs/networks |
| `ips` | array of strings | Present when `matching_target` is `"IP"` |
| `port` | string | Port number or range |
| `port_matching_type` | string | `"ANY"`, `"SPECIFIC"` |
| `match_opposite_ports` | boolean | |
| `match_opposite_ips` | boolean | |
| `match_mac` | boolean | Source only |

---

## PUT Behaviour — CONFIRMED

### Full object replacement required ✅

**Partial PUT returns HTTP 400.** Required fields per error response:

| Field | NotNull error |
|-------|---------------|
| `source` | yes |
| `destination` | yes |
| `action` | yes |
| `schedule` | yes |
| `ip_version` (`ipVersion` in Java) | yes |

**Implementation pattern: fetch-then-merge.**
GET the current policy → merge caller's changes over the top → PUT the complete merged object.

### Full round-trip confirmed ✅

PUT with the exact GET response returned HTTP 200 with the unchanged policy. The v2 API accepts `_id` in the body without error.

### PATCH — NOT SUPPORTED ❌

`PATCH /proxy/network/v2/api/site/default/firewall-policies/{id}` returns **HTTP 405 Method Not Allowed**.

---

## Existing Bug in `update_firewall_policy`

**The current implementation is broken on the live controller.**

`update_firewall_policy` in `src/tools/firewall_policies.py` currently sends a partial PUT payload (only changed fields). This returns HTTP 400 on the live controller because `source`, `destination`, `action`, `schedule`, and `ip_version` are all required.

This must be fixed as part of the full-field update implementation.

---

## Discrepancies from Portal Docs (v1 integration API)

| Portal (v1) says | v2 actual | Impact |
|------------------|-----------|--------|
| `id` | `_id` | Model alias needed |
| `ipProtocolScope` (object with discriminator) | `ip_version` (flat string: IPV4/IPV6/BOTH) | Different field name and type |
| `loggingEnabled` (boolean) | `logging` (boolean) | Different field name |
| `action` (object with type discriminator) | `action` (flat string: ALLOW/BLOCK) | Different structure entirely |
| `connectionStateFilter` (array of enums) | `connection_states` (array) + `connection_state_type` (string) | Split into two fields |
| `ipsecFilter` (enum) | `match_ip_sec` (boolean) | Different field name and type |
| `origin` (enum: USER_DEFINED/SYSTEM_DEFINED/DERIVED) | `predefined` (bool) + `origin_id` (string) | Different representation |
| PATCH supported | HTTP 405 | PATCH does not exist on v2 |
| REJECT as valid action | Not observed in live data | Unconfirmed — may not exist on v2 |

### Fields in v2 NOT documented in portal

- `create_allow_respond`
- `icmp_typename` / `icmp_v6_typename`
- `match_opposite_protocol`
- `match_opposite_ports` / `match_opposite_ips`
- `connection_state_type`
- `matching_target_type`
- `match_mac`
- `origin_id`

---

## Implementation Notes

1. **Fetch-then-merge is mandatory** — GET current policy, overlay caller's changes, PUT full object
2. **`action` is a flat string** — `"ALLOW"` / `"BLOCK"` (REJECT not confirmed on v2)
3. **`ip_version` not `ipProtocolScope`** — values: `"IPV4"`, `"IPV6"`, `"BOTH"`
4. **`logging` not `loggingEnabled`**
5. **`_id` field** — Pydantic model must alias `_id` → `id`
6. **`FirewallPolicy` model needs updating** — missing: `logging`, `ip_version`, `connection_state_type`, `create_allow_respond`, `icmp_typename`, `icmp_v6_typename`, `match_ip_sec`, `match_opposite_protocol`, `origin_id`, `index`
7. **Fix existing bug** — current partial PUT in `update_firewall_policy` returns 400 in production

---

## Probe Commands Used

```bash
# 1. GET first policy (predefined)
curl -sk -H "X-API-KEY: $UNIFI_API_KEY" \
  https://192.168.100.1/proxy/network/v2/api/site/default/firewall-policies | jq '.[0]'

# 2. GET first user-defined policy
curl -sk -H "X-API-KEY: $UNIFI_API_KEY" \
  https://192.168.100.1/proxy/network/v2/api/site/default/firewall-policies | jq '[.[] | select(.predefined == false)] | .[0]'

# 3. PUT full round-trip (HTTP 200 confirmed)
curl -sk -X PUT -H "X-API-KEY: $UNIFI_API_KEY" -H "Content-Type: application/json" \
  -d '<full GET response>' \
  https://192.168.100.1/proxy/network/v2/api/site/default/firewall-policies/69b9c04afce5cfb6d289ec4c

# 4. PUT partial payload (HTTP 400 confirmed — full object required)
curl -sk -X PUT -H "X-API-KEY: $UNIFI_API_KEY" -H "Content-Type: application/json" \
  -d '{"name": "Internal DNS"}' \
  https://192.168.100.1/proxy/network/v2/api/site/default/firewall-policies/69b9c04afce5cfb6d289ec4c

# 5. PATCH (HTTP 405 confirmed — not supported on v2)
curl -sk -X PATCH -H "X-API-KEY: $UNIFI_API_KEY" -H "Content-Type: application/json" \
  -d '{"name": "Internal DNS"}' \
  https://192.168.100.1/proxy/network/v2/api/site/default/firewall-policies/69b9c04afce5cfb6d289ec4c
```
