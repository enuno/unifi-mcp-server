"""Guest WiFi setup playbook.

Example:
    >>> from src.a2a.prompt_playbook import render_playbook
    >>> print(render_playbook("guest_wifi_setup", {"site_id": "default"}))
"""

from __future__ import annotations

from ..prompt_playbook import PlaybookStep, PromptPlaybook

PLAYBOOK = PromptPlaybook(
    name="guest_wifi_setup",
    description="Configure guest wireless access with vouchers, portal settings, and content filtering.",
    safetyLevel="confirm",
    requiredSkills=[
        "list_wlans",
        "create_wlan",
        "configure_guest_portal",
        "list_vouchers",
        "create_vouchers",
        "list_content_filter_categories",
        "list_content_filters",
        "update_content_filter",
    ],
    steps=[
        PlaybookStep(
            order=1,
            action="Inspect the existing WLAN landscape to avoid duplicate guest networks.",
            tool="list_wlans",
            params={"site_id": "${site_id}"},
            validation="Confirm whether a guest SSID already exists and whether its security model matches the intended deployment.",
            fallback="If WLAN inventory is incomplete, search by SSID name or review the site settings manually before creating anything new.",
        ),
        PlaybookStep(
            order=2,
            action="Create or update the guest WLAN with the desired guest isolation settings.",
            tool="create_wlan",
            params={
                "site_id": "${site_id}",
                "name": "${guest_ssid}",
                "security": "${security_profile}",
            },
            validation="Verify the SSID is broadcast with the expected guest access and client isolation behavior.",
            fallback="If creation is risky or blocked, defer to update_wlan on the existing guest SSID instead of duplicating networks.",
        ),
        PlaybookStep(
            order=3,
            action="Configure the guest portal and voucher policy for user access.",
            tool="configure_guest_portal",
            params={"site_id": "${site_id}", "enabled": True, "voucher_enabled": True},
            validation="Confirm the portal is enabled and voucher authentication is available for guest onboarding.",
            fallback="If guest portal configuration fails, keep the WLAN isolated and route access through vouchers only after a manual review.",
        ),
        PlaybookStep(
            order=4,
            action="Generate or review guest vouchers for the access window.",
            tool="create_vouchers",
            params={"site_id": "${site_id}", "count": 10, "duration_minutes": 1440},
            validation="Check the voucher count, validity window, and any reuse limits before handing them out.",
            fallback="If vouchers cannot be created, fall back to a manual access workflow and note the controller limitation.",
        ),
        PlaybookStep(
            order=5,
            action="Apply content filtering to the guest profile to reduce abuse risk.",
            tool="update_content_filter",
            params={
                "site_id": "${site_id}",
                "filter_id": "${guest_filter_id}",
                "categories": ["ADULT", "GAMBLING"],
            },
            validation="Confirm risky categories are blocked and the guest filter scope only affects the intended VLANs or clients.",
            fallback="If the target filter does not exist, list_content_filter_categories first and attach the change to the correct profile.",
        ),
        PlaybookStep(
            order=6,
            action="Verify the final guest access experience and document the active controls.",
            tool="list_content_filters",
            params={"site_id": "${site_id}"},
            validation="Confirm the guest profile, voucher policy, and content filtering settings are all present and aligned.",
            fallback="If the profile cannot be inspected, manually verify the WLAN and guest portal state before announcing the network.",
        ),
    ],
)
