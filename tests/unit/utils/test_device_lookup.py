"""Tests for the device-lookup helper (issue #284).

The controller reports a device under two identifiers at once: the legacy
24-hex ``_id`` and the integration UUID in ``external_id``. Tools that
read ``stat/device`` must accept either, plus the MAC.
"""

from typing import Any

from src.utils.device_lookup import device_legacy_id, find_device

# Identifiers taken from a live UniFi OS console's ``stat/device`` payload.
LEGACY_ID = "689d9f9ef4061b1ea839a6ec"  # pragma: allowlist secret
LEGACY_EXTERNAL_ID = "3b9f4018-be2a-3a93-9e90-a7a5f3603479"  # pragma: allowlist secret
SWITCH_EXTERNAL_ID = "f1364b54-bdb9-34f8-9f87-35da273426f6"  # pragma: allowlist secret

DEVICES = [
    {
        "_id": LEGACY_ID,
        "external_id": LEGACY_EXTERNAL_ID,
        "mac": "8c:30:66:9c:9b:46",
        "model": "UDMA69B",
    },
    {
        "_id": "abc123def456abc123def456",
        "external_id": SWITCH_EXTERNAL_ID,
        "mac": "aa:bb:cc:dd:ee:ff",
        "model": "USW24",
    },
]


def test_finds_by_legacy_id():
    assert find_device(DEVICES, LEGACY_ID) is DEVICES[0]


def test_finds_by_integration_uuid():
    """The ID list_devices_by_type hands out must resolve (issue #284)."""
    assert find_device(DEVICES, SWITCH_EXTERNAL_ID) is DEVICES[1]


def test_finds_by_external_id():
    assert find_device(DEVICES, LEGACY_EXTERNAL_ID) is DEVICES[0]


def test_finds_by_mac():
    assert find_device(DEVICES, "aa:bb:cc:dd:ee:ff") is DEVICES[1]


def test_match_is_case_insensitive():
    assert find_device(DEVICES, SWITCH_EXTERNAL_ID.upper()) is DEVICES[1]
    assert find_device(DEVICES, "AA:BB:CC:DD:EE:FF") is DEVICES[1]


def test_unknown_id_returns_none():
    assert find_device(DEVICES, "00000000-0000-0000-0000-000000000000") is None


def test_empty_id_returns_none():
    assert find_device(DEVICES, "") is None


def test_empty_device_list_returns_none():
    assert find_device([], LEGACY_ID) is None


def test_non_dict_entries_are_skipped():
    devices: list[Any] = ["junk", DEVICES[0]]
    assert find_device(devices, LEGACY_ID) is DEVICES[0]


def test_device_legacy_id():
    assert device_legacy_id(DEVICES[0]) == LEGACY_ID


def test_device_legacy_id_missing():
    assert device_legacy_id({"external_id": "x"}) is None
