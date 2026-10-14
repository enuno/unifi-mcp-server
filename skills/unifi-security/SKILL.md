---
name: unifi-security
description: >
  UniFi security operations: traditional firewall rules, firewall groups,
  zone-based firewall (ZBF), ACL rules, port forwarding, VPN tunnels,
  site-to-site VPN, and content filtering. Use when the task involves
  network access control, firewall policies, traffic blocking, or VPN
  configuration. Zone-based firewall requires UniFi Network 9.0+ and
  local API mode.
---

# UniFi Security Operations

**API mode requirements:**

- Zone-based firewall, firewall rules/zones/groups: `local` only
- ACLs, traffic matching lists: `local` only (the console's integration API)
- Port forwarding, VPN: `local` only

**Roles:** with bearer tokens, creating or updating firewall policies, ZBF
policies, legacy firewall rules and network-to-zone assignments needs the
`admin` role. The `operator` role can still manage ACL rules, port forwards,
groups, zones and traffic matching lists.

## Traditional Firewall Rules

| Tool | Description |
|---|---|
| `list_firewall_rules` | List all firewall rules on a site |
| `create_firewall_rule` | Create a new firewall rule |
| `update_firewall_rule` | Modify an existing firewall rule |
| `delete_firewall_rule` | Delete a firewall rule (requires `confirm=True`) |

## Firewall Groups

Groups are reusable IP/port sets referenced by rules.

| Tool | Description |
|---|---|
| `list_firewall_groups` | List all firewall groups |
| `get_firewall_group` | Get group members and details |
| `create_firewall_group` | Create a generic firewall group |
| `create_address_group` | Create an IP address group |
| `create_port_group` | Create a port group |
| `update_firewall_group` | Update group members |
| `delete_firewall_group` | Delete a group (requires `confirm=True`) |

## Zone-Based Firewall (requires Network 9.0+, local API)

### Zones

| Tool | Description |
|---|---|
| `list_firewall_zones` | List all security zones |
| `list_firewall_zones_v2` | List zones using the v2 API |
| `create_firewall_zone` | Create a new zone |
| `update_firewall_zone` | Modify zone name or settings |
| `delete_firewall_zone` | Delete a zone (requires `confirm=True`) |
| `assign_network_to_zone` | Add a network/VLAN to a zone |
| `unassign_network_from_zone` | Remove a network from a zone |
| `get_zone_networks` | List networks assigned to a zone |
| `get_zone_statistics` | Traffic stats for a zone |

### ZBF Policies

| Tool | Description |
|---|---|
| `list_firewall_policies` | List all inter-zone policies |
| `get_firewall_policy` | Get a specific policy |
| `create_firewall_policy` | Create a zone-to-zone policy |
| `update_firewall_policy` | Modify a policy (action, schedule, match criteria) |
| `delete_firewall_policy` | Delete a policy (requires `confirm=True`) |

### ZBF Matrix

| Tool | Description |
|---|---|
| `get_zbf_matrix` | Full zone-to-zone policy matrix |
| `get_zone_policies` | All policies for a specific zone |
| `get_zone_matrix_policy` | Policy between two specific zones |
| `update_zbf_policy` | Update a zone-pair policy |
| `delete_zbf_policy` | Delete a zone-pair policy |
| `block_application_by_zone` | Block a DPI application category in a zone |
| `list_blocked_applications` | List applications blocked by zone policies |

## ACL Rules (local API)

| Tool | Description |
|---|---|
| `list_acl_rules` | List all ACL rules on a site |
| `get_acl_rule` | Get a specific ACL rule |
| `create_acl_rule` | Create a new ACL rule |
| `update_acl_rule` | Modify an ACL rule |
| `delete_acl_rule` | Delete an ACL rule (requires `confirm=True`) |

## Port Forwarding

| Tool | Description |
|---|---|
| `list_port_forwards` | List all port forwarding rules |
| `create_port_forward` | Add a port forward (external → internal IP:port) |
| `update_port_forward` | Modify an existing port forward |
| `delete_port_forward` | Delete a port forward (requires `confirm=True`) |

## VPN

| Tool | Description |
|---|---|
| `list_vpn_servers` | List VPN server configurations |
| `list_vpn_tunnels` | List active VPN tunnels |
| `list_site_to_site_vpns` | List site-to-site VPN configurations |
| `get_site_to_site_vpn` | Get a specific S2S VPN |
| `update_site_to_site_vpn` | Modify a site-to-site VPN |

## Content Filtering

| Tool | Description |
|---|---|
| `list_content_filters` | List content filtering policies |
| `list_content_filter_categories` | List available filter categories |
| `update_content_filter` | Enable/disable filter categories |
| `delete_content_filter` | Remove a content filter |

## Example Workflows

```
# Audit firewall posture
Get ZBF matrix to see all zone-to-zone policies, then list firewall policies
for zones with "allow all" rules

# Block a new threat IP
Create address group "Blocked-IPs", add the malicious IP, then create a
firewall rule to drop traffic from that group

# Set up IoT isolation
Create zone "IoT", assign IoT VLAN to it, then create ZBF policy blocking
IoT → LAN (action: drop) but allowing IoT → WAN (action: allow)

# Expose a home server
Create port forward: external port 443 → 192.168.1.50:443 (tcp)
```
