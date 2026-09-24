---
name: unifi-system
description: >
  UniFi system administration and monitoring: site management, multi-site
  aggregation, backups, QoS traffic routes, traffic flow analytics, deep
  packet inspection (DPI), RADIUS authentication, guest portal, hotspot
  packages, and SD-WAN. Use when the task involves site health, backups,
  bandwidth analytics, or RADIUS user management.
---

# UniFi System Administration & Monitoring

## Site Management

| Tool | Description |
|---|---|
| `list_sites` | List all sites managed by the controller |
| `get_site_details` | Configuration and details for a site |
| `get_site_statistics` | Traffic and device counts for a site |

## Multi-Site Aggregation (Site Manager)

Requires cloud API or Site Manager access.

| Tool | Description |
|---|---|
| `list_all_sites_aggregated` | Aggregated status across all sites |
| `get_site_health_summary` | Health scores for one or all sites |
| `get_site_inventory` | Device inventory aggregated by site |
| `compare_site_performance` | Compare performance metrics across sites |
| `get_cross_site_statistics` | Cross-site bandwidth and usage |
| `search_across_sites` | Search clients/devices across all sites |
| `get_internet_health` | Internet health score and metrics |
| `get_isp_metrics` | ISP performance metrics for a site |
| `query_isp_metrics` | Query historical ISP metrics |
| `list_hosts` | List all hosts in the organization |
| `get_host` | Get details for a specific host |
| `list_sdwan_configs` | List SD-WAN configurations |
| `get_sdwan_config` | Get an SD-WAN configuration |
| `get_sdwan_config_status` | Get deployment status of an SD-WAN config |
| `list_vantage_points` | List ISP vantage points |
| `get_version_control` | Get firmware version control policy |

## Backups

| Tool | Description |
|---|---|
| `list_backups` | List available backups |
| `get_backup_details` | Metadata for a specific backup |
| `get_backup_status` | Status of a backup operation |
| `get_backup_schedule` | Get the automatic backup schedule |
| `trigger_backup` | Start an immediate backup |
| `schedule_backups` | Configure automatic backup schedule |
| `download_backup` | Download a backup file |
| `validate_backup` | Verify backup file integrity |
| `restore_backup` | Restore from a backup (requires `confirm=True`) |
| `delete_backup` | Delete a backup file (requires `confirm=True`) |
| `get_restore_status` | Check restore operation status |

## QoS & Traffic Routes

| Tool | Description |
|---|---|
| `list_traffic_routes` | List UniFi Traffic Routes (policy-based routing, e.g. clients or domains via VPN); local API only |

## Traffic Flow Analytics (local API only)

| Tool | Description |
|---|---|
| `get_traffic_flows` | Get active traffic flows |
| `get_traffic_flow_details` | Detailed view of a specific flow |
| `filter_traffic_flows` | Filter flows by source, destination, application |
| `get_top_flows` | Top flows by bandwidth usage |
| `get_flow_statistics` | Aggregate flow statistics |
| `get_flow_analytics` | Flow analytics with trend data |
| `get_flow_risks` | Flows with security risk scores |
| `get_flow_trends` | Historical flow trends |
| `get_connection_states` | Current TCP/UDP connection states |
| `get_client_flow_aggregation` | Flows aggregated per client |
| `block_flow_application` | Block flows matching an application |
| `block_flow_source_ip` | Block flows from a source IP |
| `block_flow_destination_ip` | Block flows to a destination IP |
| `find_flows_for_rule_reference` | Find flows matching a firewall rule |
| `export_traffic_flows` | Export flows to JSON/CSV |
| `stream_traffic_flows` | Stream real-time flow events |

## Traffic Matching Lists (cloud-v1/cloud-ea only)

| Tool | Description |
|---|---|
| `list_traffic_matching_lists` | List all traffic matching lists |
| `get_traffic_matching_list` | Get a specific list (IPs or ports) |
| `create_traffic_matching_list` | Create an IP or port matching list |
| `update_traffic_matching_list` | Update list entries |
| `delete_traffic_matching_list` | Delete a list (requires `confirm=True`) |

## Deep Packet Inspection (DPI)

| Tool | Description |
|---|---|
| `get_dpi_statistics` | Site-wide DPI application stats |
| `get_client_dpi` | DPI breakdown for a specific client |
| `list_top_applications` | Top applications by bytes transferred |
| `list_dpi_applications` | Full list of recognized DPI applications |
| `list_dpi_categories` | DPI application categories |
| `list_countries` | Country codes for geo-based filtering |

## RADIUS & Guest Portal

| Tool | Description |
|---|---|
| `list_radius_profiles` | List RADIUS server profiles |
| `get_radius_profile` | Get a RADIUS profile |
| `create_radius_profile` | Create a RADIUS server profile |
| `update_radius_profile` | Modify a RADIUS profile |
| `delete_radius_profile` | Delete a RADIUS profile |
| `list_radius_accounts` | List RADIUS user accounts |
| `get_radius_account` | Get a specific RADIUS account |
| `create_radius_account` | Create a RADIUS user account |
| `update_radius_account` | Update account credentials or VLAN |
| `delete_radius_account` | Delete a RADIUS account |
| `get_guest_portal_config` | Get guest portal settings |
| `configure_guest_portal` | Configure captive portal behavior |
| `list_hotspot_packages` | List hotspot access packages |
| `get_hotspot_package` | Get a specific hotspot package |
| `create_hotspot_package` | Create an access package (duration, quota, price) |
| `update_hotspot_package` | Modify a hotspot package |
| `delete_hotspot_package` | Delete a hotspot package |

## Example Workflows

```
# Pre-maintenance backup
Trigger backup on site "default", wait for completion, then validate the
backup before proceeding with firmware upgrades

# Investigate bandwidth spike
Get top flows for the last 30 minutes, then get client flow aggregation
to identify which device is responsible

# Block Netflix on guest network
Get DPI categories, find the streaming category ID, then block_flow_application
for that category on the guest VLAN zone

# Set up RADIUS for WPA2-Enterprise
Create RADIUS profile with your auth server, then update the corporate SSID
to use WPA2-Enterprise with that profile

# Route IoT traffic through VPN
Create traffic route: source=IoT-VLAN, gateway=VPN-tunnel, priority=high
```
