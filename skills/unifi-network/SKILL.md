---
name: unifi-network
description: >
  UniFi network operations: manage clients, VLANs, WiFi SSIDs, DHCP
  reservations, DNS settings, WAN connections, and guest vouchers. Use when
  the task involves connected clients, wireless networks, IP allocation,
  or internet access management.
---

# UniFi Network Operations

API mode requirements: these tools use `local` mode. ACL rules and traffic
matching lists also need `local` (see the `unifi-security` and `unifi-system`
skills).

## Client Management

| Tool | Description |
|---|---|
| `list_active_clients` | List all currently connected clients on a site |
| `search_clients` | Search clients by MAC, IP, hostname, or username |
| `get_client_details` | Full details for a specific client (MAC address) |
| `get_client_statistics` | Traffic and usage statistics for a client |
| `block_client` | Block a client from the network |
| `unblock_client` | Remove a block from a client |
| `reconnect_client` | Force reconnect a wireless client |
| `authorize_guest` | Authorize a guest client through the captive portal |
| `limit_bandwidth` | Apply upload/download bandwidth limits to a client |

## Networks & VLANs

| Tool | Description |
|---|---|
| `list_vlans` | List all networks/VLANs on a site |
| `get_network_details` | Configuration details for a specific network |
| `get_network_statistics` | Traffic statistics for a network |
| `get_subnet_info` | Subnet and IP allocation info for a network |
| `create_network` | Create a new VLAN/network |
| `update_network` | Modify an existing network (name, VLAN ID, subnet…) |
| `delete_network` | Delete a network (requires `confirm=True`) |

## WiFi (SSIDs)

| Tool | Description |
|---|---|
| `list_wlans` | List all wireless networks on a site |
| `get_wlan_statistics` | Client counts and traffic stats per SSID |
| `create_wlan` | Create a new SSID |
| `update_wlan` | Modify SSID (password, band, VLAN, guest policy…) |
| `delete_wlan` | Delete an SSID (requires `confirm=True`) |

## DHCP Reservations

| Tool | Description |
|---|---|
| `list_dhcp_reservations` | List all static DHCP assignments on a site |
| `get_dhcp_reservation` | Get a specific reservation |
| `create_dhcp_reservation` | Reserve an IP for a MAC address |
| `update_dhcp_reservation` | Update an existing reservation |
| `remove_dhcp_reservation` | Delete a DHCP reservation |

## DNS Management

| Tool | Description |
|---|---|
| `list_wan_dns` | List WAN DNS server configuration |
| `update_wan_dns` | Update DNS servers on WAN interfaces |
| `get_dns_filter_settings` | Get DNS filtering/ad-block settings |
| `update_dns_filter` | Enable/disable DNS filter categories |

## WAN & Internet

| Tool | Description |
|---|---|
| `list_wan_connections` | List WAN interfaces and their status |

## Guest Vouchers

| Tool | Description |
|---|---|
| `list_vouchers` | List all active guest vouchers |
| `get_voucher` | Get details for a specific voucher |
| `create_vouchers` | Generate new guest vouchers (count, duration, quota) |
| `delete_voucher` | Delete a single voucher |
| `bulk_delete_vouchers` | Delete multiple vouchers at once |

## Example Workflows

```
# Find a rogue client
Search clients by hostname "iPhone-unknown" then block it

# Set up a IoT VLAN
Create network with name "IoT", VLAN ID 20, subnet 192.168.20.0/24, then
create SSID "IoT-WiFi" on that VLAN

# Fix a guest's internet access
Authorize guest with MAC aa:bb:cc:dd:ee:ff for 4 hours with 10 GB quota

# Assign a static IP to a printer
Create DHCP reservation for MAC 00:11:22:33:44:55 with IP 192.168.1.100
```
