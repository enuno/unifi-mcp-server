---
name: unifi-devices
description: >
  UniFi device management: inventory, adoption, restarts, firmware upgrades,
  radio/channel configuration, port profiles, switching/stacks, network
  topology, and diagnostics. Use when the task involves physical UniFi
  hardware (APs, switches, gateways, cameras).
---

# UniFi Device Management

All tools require `local` API mode unless noted.

## Device Inventory & Details

| Tool | Description |
|---|---|
| `list_devices_by_type` | List devices filtered by type (ap, switch, gateway…) |
| `search_devices` | Search devices by name, MAC, IP, or model |
| `get_device_details` | Full configuration and status for a device |
| `get_device_statistics` | CPU, memory, uptime, and traffic stats |
| `list_pending_devices` | List devices waiting for adoption |
| `adopt_device` | Adopt a pending device into the site |
| `execute_port_action` | Execute an action on a specific device port |

## Device Control

| Tool | Description |
|---|---|
| `restart_device` | Restart a device by ID or MAC |
| `locate_device` | Flash device LEDs to physically locate it |
| `upgrade_device` | Upgrade device firmware (dry-run supported) |
| `get_ap_radio_config` | Get radio configuration for an access point |
| `set_ap_radio_channel` | Set channel/power on a specific radio band |

## Port Profiles & Switching

| Tool | Description |
|---|---|
| `list_port_profiles` | List all switch port profiles on a site |
| `get_port_profile` | Get details for a specific port profile |
| `create_port_profile` | Create a new port profile |
| `update_port_profile` | Modify a port profile (native VLAN, tagged VLANs, PoE…) |
| `delete_port_profile` | Delete a port profile |
| `get_device_by_mac` | Find a switch by its MAC address |
| `get_device_port_overrides` | Get per-port configuration overrides on a switch |
| `set_device_port_overrides` | Apply per-port profile or PoE overrides |

## Switching & Stacking

| Tool | Description |
|---|---|
| `list_lags` | List Link Aggregation Groups (LAGs) |
| `get_lag_details` | Get LAG member and status details |
| `list_switch_stacks` | List switch stacks on a site |
| `get_switch_stack` | Get stack members and roles |
| `list_mclag_domains` | List MCLAG domains |
| `get_mclag_domain` | Get MCLAG domain configuration |

## Network Topology

| Tool | Description |
|---|---|
| `get_network_topology` | Full uplink tree of all devices on a site |
| `get_device_connections` | Devices connected to a specific device |
| `get_port_mappings` | Port-level connection map for a device |
| `get_topology_statistics` | Link speeds, utilization across the topology |
| `export_topology` | Export topology as JSON or CSV |

## Diagnostics

| Tool | Description |
|---|---|
| `run_speed_test` | Trigger a WAN speed test (requires `confirm=True`) |
| `get_speed_test_status` | Check status of a running speed test |
| `get_speed_test_history` | Historical speed test results |
| `get_spectrum_scan` | Get WiFi spectrum scan data for an AP |
| `list_spectrum_interference` | List interference sources detected on a site |
| `get_network_references` | Get cross-references between network objects |

## Example Workflows

```
# Identify a slow AP
Get topology statistics, then get spectrum scan for the AP with highest
interference, then set its channel to a less congested one

# Prepare for maintenance
Locate device with MAC aa:bb:cc:11:22:33 (LED flash), then restart it

# Upgrade all APs
List devices by type "ap", then upgrade each one (dry_run=True first)

# Configure a trunk port
Set device port overrides on switch aa:bb:cc:dd:ee:ff, port 12,
profile "Trunk-All-VLANs"
```
