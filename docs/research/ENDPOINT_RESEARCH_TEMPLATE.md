# Endpoint Research: [ENDPOINT NAME]

**Status:** UNVERIFIED / VERIFIED  
**Verified on:** [controller firmware version, e.g. UniFi Network 9.x.x]  
**Verified date:** [YYYY-MM-DD]  
**Verified by:** [who ran the probe]  
**Controller hardware:** [e.g. UDM-Pro-Max]

---

## Endpoint Details

| Field | Value |
|-------|-------|
| **Portal docs path** | e.g. `GET /v1/sites/{siteId}/firewall/policies/{id}` |
| **Code path (actual)** | e.g. `GET /proxy/network/v2/api/site/{site}/firewall-policies/{id}` |
| **Version discrepancy** | Yes / No — [describe if yes] |
| **Auth required** | API key / session / none |
| **Local API only** | Yes / No |

---

## GET Response — Actual Shape

Paste the raw response from a live probe. Do not paraphrase.

```json
{
  // paste actual response here
}
```

**Fields noted:**

| Field | Type | Notes |
|-------|------|-------|
| `id` | string (UUID) | |
| ... | | |

---

## PUT / POST / PATCH Behaviour

### Does PUT require full object or accept partial?

- [ ] Full object replacement (all required fields must be present)
- [ ] Partial update accepted (only changed fields needed)

**Evidence:** [paste probe command and response that confirms this]

### Accepted fields on mutating request

| Field | Required? | Type | Notes |
|-------|-----------|------|-------|
| ... | | | |

### Error response shape

```json
{
  // paste a real error response if obtained
}
```

### PATCH support?

- [ ] Yes — fields accepted: [list]
- [ ] No — returns [status code]
- [ ] Not tested

---

## Probe Commands

Record the exact commands used so probes can be repeated.

```bash
# GET probe
curl -sk -H "X-API-KEY: $UNIFI_API_KEY" \
  https://192.168.100.1/proxy/network/v2/api/site/default/[endpoint] | jq .

# PUT probe — full object
curl -sk -X PUT -H "X-API-KEY: $UNIFI_API_KEY" -H "Content-Type: application/json" \
  -d '{ ... }' \
  https://192.168.100.1/proxy/network/v2/api/site/default/[endpoint]/[id] | jq .

# PUT probe — partial object
curl -sk -X PUT -H "X-API-KEY: $UNIFI_API_KEY" -H "Content-Type: application/json" \
  -d '{ "name": "test" }' \
  https://192.168.100.1/proxy/network/v2/api/site/default/[endpoint]/[id] | jq .
```

---

## Discrepancies from Portal Docs

List any fields, types, or behaviours that differ from what `developer.ui.com` documents.

| Portal says | Actual |
|-------------|--------|
| ... | ... |

---

## Implementation Notes

Key decisions for the tool implementation based on findings:

- [e.g. Must fetch current object before PUT and merge — API rejects partial payloads]
- [e.g. `action` field uses string values "ALLOW"/"BLOCK"/"REJECT", not an object as docs suggest]
- [e.g. PATCH not supported on v2 path — use PUT with fetch-then-merge pattern]
