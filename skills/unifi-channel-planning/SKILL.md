---
name: unifi-channel-planning
description: >
  Build an AI-driven low-interference WiFi channel plan from UniFi MCP neighbor
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
| `list_devices_by_type` | Get managed AP inventory (`type=uap`) |
| `list_site_internal_ap_neighbors_v2` | Build internal AP-to-AP graph for one site in one call |

## Conditional / Optional MCP Inputs

| Tool | When to use |
|---|---|
| `list_neighboring_aps` | Optional external RF tie-breaker or explanation; do not fetch by default |
| `list_ap_neighbors_v2` | Per-AP drill-down, debugging, or partial-result validation |
| `get_device_details` | When radio configuration, current channel, width, or regulatory capabilities are not available from inventory |

Optional execution tool:

| Tool | Purpose |
|---|---|
| `set_ap_radio_channel` | Apply proposed channel per AP/radio |

## Data Contract For Planning

Expected fields from neighbor observations:

- `ap_mac`: AP that observed the neighbor
- `bssid` or `mac`: observed AP/BSSID identity
- `channel`: observed neighbor channel number
- `signal`: RSSI (dBm)
- `last_seen`: freshness indicator
- `radio` or `band`: required radio/band dimension (`ng`/2.4 GHz or `na`/5 GHz)
- `channel_width` or `ht`: channel width, required when available for 5 GHz

If any field is missing:

- Drop records without `ap_mac`, `channel`, or `signal`.
- Do not use records without a band/radio dimension for channel assignment.
- Keep records without width only for a conservative 20 MHz fallback and mark
  the affected recommendation medium-confidence.
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

## Data Volume Controls

Keep the MCP interaction bounded and return summaries rather than raw payloads:

- Use a fixed planning window, normally 24 hours; shorten it when the graph or
  response is too large.
- Pass `min_rssi` during collection (`-85` by default, `-80` for dense sites)
  instead of collecting all weak observations and filtering after output.
- Prefer `list_site_internal_ap_neighbors_v2` because it aggregates the
  per-AP v2 calls server-side. Do not repeat `list_ap_neighbors_v2` for every
  AP unless debugging a specific AP or validating a partial result.
- Request AP inventory with an explicit `limit` and `offset` when supported;
  continue in pages until the managed AP set is complete.
- Call `list_neighboring_aps` only when external RF pressure is needed for a
  tie-breaker or explanation. It can contain hundreds of rows and must never
  be dumped into the planning response by default.
- Normalize, deduplicate, score, and sort before presenting results. Return
  metadata, counts, top conflict drivers, and a compact per-AP summary instead
  of raw JSON.
- Cap displayed neighbors per AP to the strongest relevant observations and
  report the total count plus omitted-row count. Offer per-AP drill-down only
  on request.
- If a response is still too large, process APs or pages in deterministic
  batches and merge the normalized results before optimization; never silently
  truncate the graph.

Required collection metadata:

- `start_ms`, `end_ms`, and `min_rssi`
- managed AP count and collected edge count
- dropped, skipped, paged, and omitted-row counts
- whether external rogue-AP data was collected

When physical AP locations are unavailable:

- Do not block planning on a floor plan, coordinates, or manually supplied
  zones.
- Use the normalized internal v2 graph as the measurable overlap proxy:
  observed AP pairs, RSSI, freshness, band, channel, and width.
- Do not claim that two APs are physically distant or in separate areas unless
  that is reported by UniFi or supplied by the operator.
- Lower confidence for conclusions that depend on unobserved coverage or
  client roaming between APs.
- Prefer no-op or small staged changes when the graph is sparse; the planner
  may still produce a deterministic plan from the telemetry that is available.

## Planning Rules

1. Scope by band:

- 2.4 GHz candidates: channels 1-14 (practical non-overlap: 1, 6, 11)
- 5 GHz candidates: local policy set (for example 36/40/44/48 and DFS set if allowed).
- Plan each band/radio independently. Never score a 2.4 GHz observation against
  a 5 GHz candidate or use one band to fill missing data in the other.
- Derive occupied channel ranges from primary channel and width. For 20 MHz,
  use one channel block; for 40/80 MHz, include every overlapping 20 MHz block
  in the configured channel range.
- Before scoring, convert every UniFi radio configuration into a canonical
  `occupied_20mhz_channels` set.
- Do not infer occupied blocks solely from a numeric primary channel. Use the
  UniFi-reported primary/control/center channel and width representation.
- If UniFi does not provide enough information to determine occupied 20 MHz
  blocks unambiguously, mark the radio medium-confidence and use the
  conservative supported interpretation.

2. Filter weak observations:

- Default threshold: keep neighbors with `signal >= -85`.
- For dense environments, use `>= -80`.

3. Build per-AP conflict score:

- For each AP and candidate channel, sum weighted conflicts from observed neighbors on same or overlapping channels.
- Stronger RSSI contributes higher penalty.
- Internal AP-to-AP penalties must be weighted higher than external rogue BSSID penalties.

4. Deterministic assignment:

- Sort APs by descending neighbor pressure (most constrained first).
- Evaluate assignments against the complete internal AP graph, not each AP in
  isolation. Re-score all graph edges after every proposed assignment so a
  locally good choice cannot create a global co-channel cluster.
- Use deterministic greedy global optimization: assign the next most
  constrained AP, then recompute the complete graph score after each assignment.
- Select the candidate with the lowest total graph penalty. Use descending
  pressure and ascending channel order as deterministic tie-breakers.
- Tie-breaker order must be fixed (for example ascending channel number).

Optimization order is strict:

1. Minimize the complete RF conflict score.
2. Among equivalent or near-equivalent scores, minimize channel concentration
  and prefer a balanced population such as `3/3/2` for eight APs on three
  2.4 GHz channels.
3. Minimize the number of changes.
4. Use ascending channel order as the final deterministic tie-breaker.

Default score tolerance:

- Relative tolerance: `2%`
- Absolute tolerance: `0.01`
- A candidate is near-equivalent when `candidate_score <= best_score * 1.02`
  or `candidate_score - best_score <= 0.01`.

For a global 2.4 GHz assignment, score every internal edge using the proposed
channels of both APs:

- Same channel: `rssi_weight(signal)`
- Adjacent 2.4 GHz channel: `0.5 * rssi_weight(signal)`
- Non-overlapping channel: `0`

For 5 GHz, score overlap between the occupied channel ranges. A shared 20 MHz
block receives the same base penalty, scaled by the fraction of overlapping
blocks. An 80 MHz AP therefore contributes more spectrum pressure than a 20
MHz AP when the ranges overlap.

Use deterministic RSSI weight classes instead of assuming a linear RF effect:

- `signal >= -55`: weight `4.0`
- `-65 <= signal < -55`: weight `3.0`
- `-75 <= signal < -65`: weight `2.0`
- `-85 <= signal < -75`: weight `1.0`

Multiply same-channel or overlap penalties by this weight. Keep the raw RSSI
in the output reason so the score remains explainable.

Before optimization, normalize the internal graph:

- Treat AP-A seeing AP-B and AP-B seeing AP-A as one undirected physical pair.
- Deduplicate repeated observations within the planning window.
- Use the most recent valid RSSI per undirected pair, retaining band and width
  separately. A configurable freshness window may retain the strongest valid
  observation as secondary context, but must not replace the current value.
- Never infer the observer's current channel from the `channel` field: it is
  the observed neighbor/BSSID channel only.

Do not sum an observer's neighbor rows against a candidate while leaving all
other APs at their current channels. That produces misleading results such as
moving several APs to channel 11 simply because each AP was evaluated alone.

5. Guardrails:

- Avoid changing all APs at once.
- Keep at least one stable channel anchor per area.
- With enough APs to use the practical 2.4 GHz set, keep every candidate
  channel represented unless measured RF data clearly justifies abandoning one.
- When topology and RF scores permit, prefer a balanced channel population. For
  eight APs on three channels, prefer counts of `3/3/2` (in deterministic
  channel order) over a `4/3/1` or more concentrated distribution.
- Treat a mathematically lower score that moves many APs or abandons a channel
  as a candidate for staged review, not as an automatic rollout.
- Respect hardware/regulatory constraints reported by UniFi.

## Example Scoring Heuristic

For each observed neighbor relation:

- Same channel penalty: `p_same = rssi_weight(signal)`
- Adjacent channel penalty (2.4 GHz): `p_adj = 0.5 * rssi_weight(signal)`
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
- Rollout defaults: first wave maximum 3 AP radios; subsequent waves maximum
  25% of remaining changed radios; never change more than 50% of site radios
  without explicit confirmation.
- Persist the original channel, width, and power settings for every change.
- Wait validation window and compare client health/events.
- If AP instability or client disconnects exceed the configured threshold,
  restore the persisted settings before continuing.

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
- Treat `channel=auto` as unknown current state. Infer it only when the v2
  graph provides a fresh observation of that AP as a neighbour. Mark the
  inferred current state and resulting recommendation medium-confidence. If
  the AP is not observed as a neighbour, keep it unchanged and mark
  low-confidence.
- Distinguish the observed neighbor's channel from the observer's channel:
  the `channel` field on a v2 edge describes the observed neighbor/BSSID.
- Read the observer's current channel from AP radio configuration or telemetry;
  never infer it from a row where that AP is the observer. An AP configured as
  `Auto` may be inferred from a fresh row where its MAC is the observed
  neighbour, and may be changed to the proposed fixed channel when the plan is
  explicitly accepted.
- Reject impossible RSSI outliers for planning (for example values above -20 dBm or below -95 dBm unless intentionally configured).
- If internal graph is empty, do not derive channel plan from `rogueap` alone.

Confidence must be deterministic:

- `high`: complete internal data, fresh observations, known capabilities, and
  a clear score improvement or a validated no-op.
- `medium`: partial or stale data, inferred `Auto` state, missing width, or a
  marginal score difference.
- `low`: no or very few observations, skipped APs, unknown capabilities, or an
  unknown current channel.

## Failure Handling

- If neighbor dataset is empty for a site, do not auto-assign.
- If an AP has no observations, keep current channel and mark `low` confidence.
- If an AP is configured as `Auto` and its current channel is inferred from a
  fresh neighbour observation, preserve the original `Auto` setting for
  rollback and allow the accepted plan to set an explicit fixed channel.
- On per-AP apply failure, continue with others and report partial status.
- If `list_site_internal_ap_neighbors_v2` reports `skipped_aps`, keep those APs unchanged and mark low confidence.
- If only `rogueap` is available and internal AP graph is missing, return "insufficient internal data" instead of proposing deterministic AP-to-AP assignments.
- If the current configuration is already within the accepted score tolerance,
  return a valid no-op plan with `0 APs changed`; do not manufacture changes.

## Example Prompt Pattern

"For site X, use the internal AP neighbor graph to produce a low-interference
channel plan per AP for 2.4 GHz first. Use channels 1/6/11 only, use minimum
RSSI -85, minimize same-channel conflicts, and return deterministic sorted
results with reasons. Fetch external rogue-AP data only if needed for context."
