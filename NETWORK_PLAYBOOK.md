# NETWORK_PLAYBOOK

Operator-grade runbooks for recurring UniFi Network operations.

## Purpose

Provide repeatable, safe, stepwise guidance for operators and agents performing common UniFi Network changes. These runbooks are intended to be executed with explicit approval, clear inputs, and a verification-first mindset.

## Scope

Covered workflows:

- VLAN provisioning and validation
- Guest portal setup
- Firewall policy review
- Device adoption and post-adoption checks
- WAN failover verification
- DNS policy review
- WiFi broadcast lifecycle changes
- Port profile rollout
- Backup and restore validation

## Shared guardrails

- Confirm the target controller and site before making changes.
- Prefer read-only inspection first; do not mutate until the pre-change state is captured.
- Record the expected outcome in plain language before the first write.
- Use dry-run / preview mode where available.
- Re-check the post-change state from the controller, not from memory.
- Roll back immediately if the controller state diverges from the intended change.
- Never store credentials, tokens, or API keys in the runbook.

## Standard runbook template

Each runbook below follows the same structure:

1. Objective
2. Preconditions
3. Procedure
4. Verification
5. Rollback
6. Common failure modes

---

## 1) VLAN provisioning and validation

### Objective
Create or update a VLAN-backed network and confirm it is usable on the intended sites and switch ports.

### Preconditions

- You have the controller, site, VLAN ID, subnet, gateway, DHCP plan, and naming convention.
- No conflicting network already owns the target VLAN ID.
- A rollback plan exists for any dependent switches or SSIDs.

### Procedure

1. Inspect existing networks and record the current VLAN allocation.
2. Check DHCP scope, gateway, and DHCP relay requirements.
3. Create or update the network definition.
4. Apply any switch port profile updates that depend on the VLAN.
5. If the VLAN is used by WiFi, confirm the SSID mapping.
6. Allow controller synchronization to settle before validating clients.

### Verification

- Network exists with the expected VLAN ID and subnet.
- Gateway and DHCP settings match the requested design.
- Target switch ports show the new profile or VLAN tagging.
- A test client can obtain an address and route as expected.

### Rollback

- Revert the network definition to the previous subnet/VLAN assignment.
- Restore switch port profiles.
- Remove WiFi mappings if the network is not meant to remain active.

### Common failure modes

- VLAN ID collision with an existing network.
- Port profile mismatch on trunks vs access ports.
- DHCP scope conflict or incorrect gateway.

---

## 2) Guest portal setup

### Objective
Enable or update a guest portal workflow with the minimum required access and clear expiry behavior.

### Preconditions

- Portal branding, terms text, and authentication model are approved.
- Guest network and WLAN exist or are being created alongside the portal.
- Voucher, hotspot, or redirect requirements are documented.

### Procedure

1. Inspect the current guest portal configuration.
2. Confirm the guest network isolation policy.
3. Apply portal changes in a staged manner: appearance, access rules, expiry, and vouchers/packages.
4. Verify redirect and landing page behavior from a test device.

### Verification

- Guests are isolated from internal networks.
- Portal landing page loads and authenticates as expected.
- Voucher or package expiry behaves correctly.
- DNS and captive portal redirects work from a fresh client.

### Rollback

- Restore the previous portal settings.
- Disable the portal temporarily if authentication is failing and the site needs emergency access.

### Common failure modes

- Portal redirect loops caused by DNS or firewall rules.
- Incorrect guest isolation allowing internal access.
- Voucher or package misconfiguration.

---

## 3) Firewall policy review

### Objective
Review firewall policy state for correctness, drift, and least-privilege alignment.

### Preconditions

- You have the target site, policy intent, and the expected source/destination objects.
- There is a current policy inventory and a change reason.

### Procedure

1. Export or list the current firewall policy set.
2. Compare rule order, targets, and actions against the requested design.
3. Identify shadowed, duplicate, or overly broad rules.
4. Stage the desired change and validate any object references.
5. Apply the change with explicit confirmation.

### Verification

- Policy order is correct.
- Objects resolve to the intended networks, groups, or endpoints.
- Negative test traffic is blocked and positive test traffic passes.

### Rollback

- Restore the prior policy snapshot or the known-good rule order.
- Remove any newly introduced objects that are not referenced elsewhere.

### Common failure modes

- Rule-order mistakes that shadow the new policy.
- Incorrect zone or object resolution.
- Legacy rules retained after a change window.

---

## 4) Device adoption and post-adoption checks

### Objective
Bring a device into management cleanly and confirm it is healthy after adoption.

### Preconditions

- Device model, physical location, and expected uplink are known.
- The target site is selected and the device is reachable.
- The operator knows whether the device is new, migrated, or recovering.

### Procedure

1. Confirm the device appears in pending or disconnected state.
2. Verify the intended site and adoption target.
3. Start adoption and wait for the controller to report progress.
4. Confirm the device receives the expected configuration.
5. Validate uplink, firmware state, and port status.

### Verification

- Device is adopted into the correct site.
- Device is online and provisioned.
- Port profiles, VLANs, and management IP are correct.
- No unexpected alert remains after the device settles.

### Rollback

- Remove the device from management if adoption was accidental.
- Restore the previous controller assignment for migrated hardware.

### Common failure modes

- Wrong site selected during adoption.
- Firmware mismatch causing a long provisioning delay.
- Physical connectivity issues that look like controller failures.

---

## 5) WAN failover verification

### Objective
Prove that WAN failover behaves as designed before a real outage.

### Preconditions

- Primary and secondary WAN definitions are present.
- Failover criteria are documented.
- Test window is approved because the procedure may briefly interrupt traffic.

### Procedure

1. Record the current WAN health and route preference.
2. Simulate a primary WAN degradation or outage.
3. Confirm traffic shifts to the backup path.
4. Restore the primary WAN and confirm failback behavior.

### Verification

- Failover triggers at the expected threshold.
- Secondary WAN becomes active without manual intervention.
- Failback occurs only under the intended stability conditions.

### Rollback

- Restore the primary WAN and revert any temporary test overrides.

### Common failure modes

- Health-check thresholds too strict or too loose.
- DNS or NAT state lingering across the transition.
- ISP handoff issues misread as controller problems.

---

## 6) DNS policy review

### Objective
Validate DNS policy behavior for content filtering, split DNS, or resolver selection.

### Preconditions

- The intended resolver set and policy goals are defined.
- You know whether the policy applies to one network or multiple sites.

### Procedure

1. Inspect current DNS settings at the network and controller level.
2. Confirm the resolver addresses and any content filtering rules.
3. Review exceptions and split-horizon records if present.
4. Apply changes.
5. Test resolution from a client on the affected network.

### Verification

- Clients resolve the expected internal and external records.
- Policy exceptions are honored.
- Malformed or disallowed destinations are blocked as intended.

### Rollback

- Restore the previous resolver and policy configuration.

### Common failure modes

- DHCP hands out stale resolver values.
- Split DNS overrides are incomplete.
- Clients cache the previous resolver state.

---

## 7) WiFi broadcast lifecycle changes

### Objective
Safely create, modify, or retire a wireless broadcast without impacting unrelated SSIDs.

### Preconditions

- SSID name, security type, VLAN mapping, and radio behavior are documented.
- Guest or staff impact is assessed.

### Procedure

1. Review the current broadcast settings.
2. Change one dimension at a time when possible: security, VLAN, radio policy, or schedule.
3. Push the update to the target site.
4. Monitor client reconnection behavior.

### Verification

- Broadcast appears on the expected APs.
- Security settings match the requested policy.
- Clients reconnect and obtain the correct network identity.

### Rollback

- Restore the previous SSID definition.
- Reinstate the prior VLAN or security mode.

### Common failure modes

- Unexpected client disconnects due to security-mode changes.
- Incorrect band steering or radio settings.
- SSID clone collisions from duplicated names.

---

## 8) Port profile rollout

### Objective
Roll out a switch port profile change with minimal disruption.

### Preconditions

- The affected switches and ports are known.
- The profile change has been validated in a lab or on a low-risk port.

### Procedure

1. Inventory the target ports and their current profile assignment.
2. Stage the new profile.
3. Apply to a small canary set first.
4. Observe link status, LLDP, PoE, and client behavior.
5. Expand only after canary validation passes.

### Verification

- Ports negotiate the expected speed, VLAN, PoE, and voice/data settings.
- No new port flapping or client loss appears.

### Rollback

- Re-apply the previous profile to the affected ports.

### Common failure modes

- Voice VLAN or PoE settings omitted.
- Edge ports accidentally converted to trunk behavior.
- Profile applied to the wrong port group.

---

## 9) Backup and restore validation

### Objective
Prove that controller backups are complete and that restores are usable.

### Preconditions

- Backup retention policy exists.
- Restore test window is approved.
- The operator has the backup identifier and target restore environment.

### Procedure

1. Trigger or select a known backup.
2. Confirm the backup artifact exists and is recent.
3. Restore to a non-production target whenever possible.
4. Compare restored settings to the source environment.
5. Document any drift or missing state.

### Verification

- Backup artifact can be retrieved.
- Restore completes successfully.
- Core config items match the source environment.

### Rollback

- Revert the test environment to its pre-restore state.
- Do not overwrite production without explicit approval.

### Common failure modes

- Backup artifact corruption.
- Restore target too old or incompatible.
- Operator assumes the restore is valid without comparing settings.

## Status

Phase-4 documentation. This file should be kept in sync with the Network API surface and updated when new operational patterns become stable.