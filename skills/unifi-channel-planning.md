---
name: unifi-channel-planning
description: >
  Build an AI-driven non-overlapping WiFi channel plan from UniFi MCP neighbor
  observations. Use when the task is RF optimization, channel conflict
  reduction, co-channel interference mitigation, or per-AP channel assignment.
---

# UniFi Channel Planning

Use this skill to produce a deterministic channel plan from MCP output.

Primary intent:

- Reduce overlap and co-channel contention.
- Keep assignments reproducible and explainable.
- Provide safe change rollout with validation.

## Required MCP Inputs

| Tool | Purpose |
|---|---|
| `list_sites` | Select target site |
| `list_neighboring_aps` | External RF congestion view (`stat/rogueap`) |
| `list_devices_by_type` | Get managed AP inventory (`type=uap`) |
| `list_site_internal_ap_neighbors_v2` | Build internal AP-to-AP graph for one site in one call |
| `list_ap_neighbors_v2` | Optional per-AP drill-down/debug for one AP |
| `get_device_details` | Read AP model/radio capabilities if needed |

Optional execution tool:

| Tool | Purpose |
|---|---|
| `set_ap_radio_channel` | Apply proposed channel per AP/radio |

## Data Contract For Planning

Expected fields from neighbor observations:

- `ap_mac`: AP that observed the neighbor
- `bssid` or `mac`: observed AP/BSSID identity
- `channel`: observed channel number
- `signal`: RSSI (dBm)
- `last_seen`: freshness indicator
- `radio` or `band`: radio context when available

If any field is missing:

- Drop records without `ap_mac`, `channel`, or `signal`.
- Keep processing with partial data and log dropped count.

## Correct Data Source Split (Critical)

Use two distinct datasets and do not mix them:

1. Internal AP-to-AP graph (for channel assignment):

- Primary source: `list_site_internal_ap_neighbors_v2(site_id, start_ms, end_ms, min_rssi)`
- The tool already executes v2 per-AP neighbor queries and keeps only rows where neighbor `mac` is a managed AP MAC from the same site.
- Optional fallback/debug: `list_ap_neighbors_v2` per AP.
- This is the authoritative input for "which site AP sees which other site AP and how strong".

2. External RF pressure (optional tie-breaker):

- Source: `list_neighboring_aps` (`stat/rogueap`)
- Represents foreign BSSIDs around the site.
- Use only as additional congestion context, not as the internal AP graph.

## Planning Rules

1. Scope by band:

- 2.4 GHz candidates: channels 1-14 (practical non-overlap: 1, 6, 11)
- 5 GHz candidates: local policy set (for example 36/40/44/48 and DFS set if allowed)

2. Filter weak observations:

- Default threshold: keep neighbors with `signal >= -85`.
- For dense environments, use `>= -80`.

3. Build per-AP conflict score:

- For each AP and candidate channel, sum weighted conflicts from observed neighbors on same or overlapping channels.
- Stronger RSSI contributes higher penalty.
- Internal AP-to-AP penalties must be weighted higher than external rogue BSSID penalties.

4. Deterministic assignment:

- Sort APs by descending neighbor pressure (most constrained first).
- Assign channel with lowest score.
- Tie-breaker order must be fixed (for example ascending channel number).

5. Guardrails:

- Avoid changing all APs at once.
- Keep at least one stable channel anchor per area.
- Respect hardware/regulatory constraints reported by UniFi.

## Example Scoring Heuristic

For each observed neighbor relation:

- Same channel penalty: `p_same = max(0, signal + 100)`
- Adjacent channel penalty (2.4 GHz): `p_adj = 0.5 * p_same`
- Non-overlapping channel penalty: `0`

Total candidate score:

- `score(ap, ch) = sum(penalties from all neighbors seen by ap on/near ch)`

Lower score is better.

## Output Contract

Return a plan table with:

- `ap_mac`
- `current_channel`
- `proposed_channel`
- `band`
- `confidence` (`high|medium|low`)
- `reason` (top 1-3 conflict drivers)

Also return summary metrics:

- Estimated co-channel conflict delta
- Number of APs changed
- APs skipped with reason

## Safe Rollout Workflow

1. Discovery:

- Run `list_sites` and select `site_id`.
- Build managed AP set (`type=uap`).
- Pull internal graph with `list_site_internal_ap_neighbors_v2` over a fixed window (default 24h).
- If needed, inspect problematic APs with `list_ap_neighbors_v2`.
- Optionally pull `list_neighboring_aps(site_id, min_rssi=-85)` for external context.

2. Plan:

- Generate per-AP candidate ranking and proposed channels.
- Mark risky APs (sparse data, stale `last_seen`, extreme noise).

3. Stage:

- Apply to small batch first with `set_ap_radio_channel`.
- Wait validation window and compare client health/events.

4. Expand:

- Roll out remaining APs in waves.
- Re-run neighbor scan and adjust.

## Validation Checks

After each rollout wave, verify:

- AP online state is stable.
- Client disconnect spikes did not increase.
- Channel reuse distance improved in dense zones.
- No AP is assigned unsupported channel width/channel pair.

Pre-plan data-quality checks:

- Confirm each managed AP has at least one internal neighbor observation in the selected window, otherwise mark low-confidence.
- Reject impossible RSSI outliers for planning (for example values above -20 dBm or below -95 dBm unless intentionally configured).
- If internal graph is empty, do not derive channel plan from `rogueap` alone.

## Failure Handling

- If neighbor dataset is empty for a site, do not auto-assign.
- If an AP has no observations, keep current channel and mark `low` confidence.
- On per-AP apply failure, continue with others and report partial status.
- If `list_site_internal_ap_neighbors_v2` reports `skipped_aps`, keep those APs unchanged and mark low confidence.
- If only `rogueap` is available and internal AP graph is missing, return "insufficient internal data" instead of proposing deterministic AP-to-AP assignments.

## Example Prompt Pattern

"Using `list_neighboring_aps` output for site X, produce a non-overlapping channel
plan per AP for 2.4 GHz first. Use channels 1/6/11 only, filter signal < -85,
minimize same-channel conflicts, and return deterministic sorted results with reasons."
