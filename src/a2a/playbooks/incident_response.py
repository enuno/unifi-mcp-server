"""Incident response playbook.

Example:
    >>> from src.a2a.prompt_playbook import render_playbook
    >>> print(render_playbook("incident_response", {"site_id": "default"}))
"""

from __future__ import annotations

from ..prompt_playbook import PlaybookStep, PromptPlaybook

PLAYBOOK = PromptPlaybook(
    name="incident_response",
    description="Contain a security incident, preserve evidence, and validate remediation.",
    safetyLevel="strict",
    requiredSkills=[
        "search_clients",
        "get_client_details",
        "get_device_details",
        "block_client",
        "list_active_clients",
        "get_traffic_flows",
        "export_traffic_flows",
        "get_flow_risks",
        "block_flow_source_ip",
        "block_flow_application",
        "create_firewall_rule",
        "get_network_topology",
    ],
    steps=[
        PlaybookStep(
            order=1,
            action="Identify the impacted client, device, or network segment.",
            tool="search_clients",
            params={"site_id": "${site_id}", "query": "${indicator}"},
            validation="Confirm the suspected asset is real, currently active, and tied to the incident scope.",
            fallback="If the client cannot be found, pivot to get_device_details or get_network_topology to locate the affected endpoint.",
        ),
        PlaybookStep(
            order=2,
            action="Contain the suspected client immediately if it is safe to do so.",
            tool="block_client",
            params={"site_id": "${site_id}", "client_mac": "${client_mac}"},
            validation="Verify the client disappears from active access or is marked blocked in controller state.",
            fallback="If the client block does not take effect, isolate the upstream device or fall back to a temporary firewall rule.",
        ),
        PlaybookStep(
            order=3,
            action="Capture network evidence for later analysis.",
            tool="export_traffic_flows",
            params={"site_id": "${site_id}", "format": "json", "window_minutes": 60},
            validation="Ensure the export includes the incident time window and the relevant source/destination tuples.",
            fallback="If export fails, use get_traffic_flows and get_flow_risks to assemble a manual evidence set.",
        ),
        PlaybookStep(
            order=4,
            action="Block the most likely malicious path while preserving the rest of the site.",
            tool="create_firewall_rule",
            params={
                "site_id": "${site_id}",
                "action": "block",
                "source": "${indicator}",
                "destination": "any",
            },
            validation="Verify the rule is scoped as narrowly as possible and does not disrupt unrelated traffic.",
            fallback="If a firewall rule is too broad, use block_flow_source_ip or block_flow_application for a tighter containment path.",
        ),
        PlaybookStep(
            order=5,
            action="Check for lateral movement or secondary affected assets.",
            tool="get_network_topology",
            params={"site_id": "${site_id}"},
            validation="Confirm whether other clients or devices exhibit the same indicator or abnormal connectivity.",
            fallback="If topology is not enough, inspect active clients and device details individually for suspicious relationships.",
        ),
        PlaybookStep(
            order=6,
            action="Record the containment outcome and plan the rollback path.",
            tool="list_active_clients",
            params={"site_id": "${site_id}"},
            validation="Verify the impacted asset remains contained and the rest of the site is still functioning.",
            fallback="If containment harms normal operations, document the exception and escalate for a supervised rollback.",
        ),
    ],
)
