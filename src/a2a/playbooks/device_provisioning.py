"""Device provisioning playbook.

Example:
    >>> from src.a2a.prompt_playbook import render_playbook
    >>> print(render_playbook("device_provisioning", {"site_id": "default"}))
"""

from __future__ import annotations

from ..prompt_playbook import PlaybookStep, PromptPlaybook

PLAYBOOK = PromptPlaybook(
    name="device_provisioning",
    description="Adopt a new UniFi device and apply the initial operational configuration.",
    safetyLevel="confirm",
    requiredSkills=[
        "list_pending_devices",
        "adopt_device",
        "get_device_details",
        "get_device_statistics",
        "set_device_port_overrides",
        "set_ap_radio_channel",
        "restart_device",
        "upgrade_device",
        "get_network_topology",
    ],
    steps=[
        PlaybookStep(
            order=1,
            action="Discover pending devices that are ready for adoption.",
            tool="list_pending_devices",
            params={"site_id": "${site_id}"},
            validation="Confirm the target device is in a pending/adoptable state and matches the expected serial or MAC.",
            fallback="If nothing appears pending, search devices by MAC or serial and verify whether it has already been adopted.",
        ),
        PlaybookStep(
            order=2,
            action="Adopt the target device into the site.",
            tool="adopt_device",
            params={"site_id": "${site_id}", "device_id": "${device_id}"},
            validation="Verify the device transitions from pending to adopting/connected and reports controller reachability.",
            fallback="If adoption stalls, retry after checking controller reachability or device factory-reset status.",
        ),
        PlaybookStep(
            order=3,
            action="Validate the adopted device identity and health.",
            tool="get_device_details",
            params={"site_id": "${site_id}", "device_id": "${device_id}"},
            validation="Confirm model, firmware, uplink, and management status match the intended device.",
            fallback="If details are incomplete, use get_device_statistics and get_network_topology to corroborate the device state.",
        ),
        PlaybookStep(
            order=4,
            action="Apply the first-pass physical and port-level configuration.",
            tool="set_device_port_overrides",
            params={
                "site_id": "${site_id}",
                "device_id": "${device_id}",
                "overrides": "${overrides}",
            },
            validation="Check that port profiles, PoE settings, and trunk/access intent match the deployment plan.",
            fallback="If port overrides fail, apply the minimum safe configuration and document the missing settings for follow-up.",
        ),
        PlaybookStep(
            order=5,
            action="Finalize the device by validating radio or firmware state when relevant.",
            tool="upgrade_device",
            params={"site_id": "${site_id}", "device_id": "${device_id}"},
            validation="Confirm the device returns to an online state with the expected firmware version.",
            fallback="If the upgrade path is not safe, postpone it and use restart_device only when a reboot is explicitly acceptable.",
        ),
        PlaybookStep(
            order=6,
            action="Confirm the device is visible in the live topology and operating normally.",
            tool="get_network_topology",
            params={"site_id": "${site_id}"},
            validation="Ensure the device appears in the correct location with the expected uplink and neighbors.",
            fallback="If topology is stale, refresh after a short delay or inspect the device directly with get_device_details.",
        ),
    ],
)
