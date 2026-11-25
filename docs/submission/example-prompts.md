# Example prompts

The Anthropic Software Directory Policy §3.E requires "at least three working examples of prompts or use cases that demonstrate core functionality". These are the three to submit, each with the skill it loads and the tools it exercises.

`TODO(verify)`: no plugin submission page documents the form field where a plugin bundle supplies these three prompts. The guide for a **connector** listing has a "Use cases" step; the plugin bundle path does not name one. Confirm where the portal expects them.

---

## 1. Find a client that cannot reach the internet

**Prompt**

```
Which clients on this site are connected but have no internet access right now?
Show me the client, the AP it is on, and how long it has been failing.
```

**Skill:** `unifi-discovery`, then `unifi-network`

**Tools:** `list_sites`, `list_active_clients`, `search_clients`, `get_client_details`, `get_client_statistics`

**Why it demonstrates the plugin:** it is the most common first question, it needs no write access, and it works with the default read-only profile.

**Expected result:** a table of clients with their upstream state, drawn from the controller the user configured.

---

## 2. Audit the zone-based firewall

**Prompt**

```
Audit the zone-based firewall. List every policy that allows traffic from
the WAN zone to a LAN zone, and every policy that lets the guest zone reach
the corporate zone. For each one, show the rule, the zones it applies to and
whether it is enabled.
```

**Skill:** `unifi-security`

**Tools:** `list_firewall_zones`, `list_firewall_policies`, `get_firewall_policy`, `get_zone_policy_matrix`, `get_zone_networks`

**Why it demonstrates the plugin:** it is the highest-value read-only task in the library, it spans the firewall zone model rather than a single tool, and it is the task that most often leads to a change the user then approves.

**Expected result:** the list of policies that permit the traffic the user asked about, with their state.

---

## 3. Plan a change, then make it

**Prompt**

```
The guest WiFi SSID needs a new VLAN. Show me the current guest network and
SSID, then propose the change and wait for my confirmation before applying
it. Do not change anything yet.
```

**Skill:** `unifi-safe-changes`, then `unifi-network`

**Tools:** `list_networks`, `get_network_details`, `list_wlans`, `create_network`, `update_wlan`

**Why it demonstrates the plugin:** it shows the safety model rather than just the tool surface. The agent reads first, proposes the change, and does not write until the user confirms, because every mutating tool requires `confirm=True`.

**Expected result:** the current configuration, then a proposed diff, and a request for confirmation. Nothing is written until the user confirms.

---

## A fourth, for the write path

Not required, but useful to have ready if a reviewer asks what the write tools do.

**Prompt**

```
Show me the devices that have been offline for more than a day, and their
last-seen time. Do not restart anything.
```

**Skill:** `unifi-devices`

**Tools:** `list_pending_devices`, `search_devices`, `get_device_details`

**Expected result:** the offline device list, and no restart, because the request does not ask for one and the agent does not act beyond the request.
