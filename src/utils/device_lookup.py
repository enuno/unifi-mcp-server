"""Find a device record in a legacy ``stat/device`` collection by any ID.

The controller reports devices under two identifiers at once and the
server's tools accept both, so a lookup has to consider both:

* ``_id`` — the legacy 24-hex ObjectId, the only identifier the legacy
  routes (``stat/device``, ``rest/device``) accept;
* ``external_id`` — the RFC-style UUID the Integration API v1 reports as
  ``id`` and the topology tools return;
* ``mac`` — the MAC address, which every tool accepts.

Issue #284: ``list_devices_by_type`` returns the Integration API's UUID,
but ``get_device_port_overrides`` matched only ``_id`` and ``mac``, so the
UUID that the listing handed out was rejected by the tool that consumes
it ("device not found"). The same lookup is duplicated in six places
across ``device_control.py`` and ``port_profiles.py``; they all share the
same blind spot, so they share one helper.
"""

from typing import Any

# Keys a caller may pass a device identifier under.
_DEVICE_ID_KEYS = ("_id", "external_id", "id")


def find_device(
    devices: list[dict[str, Any]],
    device_id: str,
) -> dict[str, Any] | None:
    """Find a device record by legacy ID, integration UUID or MAC.

    Args:
        devices: Device records from ``stat/device``
        device_id: Identifier to look for — legacy ObjectId, integration
            UUID, or MAC address

    Returns:
        The matching device record, or ``None`` when nothing matches
    """
    if not device_id:
        return None
    needle = device_id.strip().lower()
    for device in devices:
        if not isinstance(device, dict):
            continue
        for key in _DEVICE_ID_KEYS:
            value = device.get(key)
            if isinstance(value, str) and value.lower() == needle:
                return device
        mac = device.get("mac")
        if isinstance(mac, str) and mac.lower() == needle:
            return device
    return None


def device_legacy_id(device: dict[str, Any]) -> str | None:
    """Return the legacy ObjectId of a device record, if it has one.

    Args:
        device: Device record from ``stat/device``

    Returns:
        The ``_id`` value, or ``None`` when the record carries no legacy ID
    """
    value = device.get("_id")
    return value if isinstance(value, str) and value else None
