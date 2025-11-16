"""Pytest configuration and shared fixtures."""

import pytest

from src.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        api_key="test-api-key-XXZDILlzznocKT6JG7_s9VlMAW0HD8Ew",
        api_type="cloud",
        host="api.ui.com",
        verify_ssl=True,
    )


@pytest.fixture(autouse=True)
def reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset environment variables before each test."""
    # Clear any existing UNIFI_ environment variables
    import os

    for key in list(os.environ.keys()):
        if key.startswith("UNIFI_") or key == "LOG_LEVEL":
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def sample_site_data() -> dict:
    """Sample site data for testing."""
    return {
        "meta": {"rc": "ok"},
        "data": [
            {
                "_id": "default",
                "name": "Default Site",
                "desc": "Default site description",
            },
            {
                "_id": "site-123",
                "name": "Test Site",
                "desc": "Test site description",
            },
        ],
    }


@pytest.fixture
def sample_device_data() -> dict:
    """Sample device data for testing."""
    return {
        "meta": {"rc": "ok"},
        "data": [
            {
                "_id": "507f1f77bcf86cd799439011",
                "name": "AP-Office",
                "model": "U6-LR",
                "type": "uap",
                "mac": "aa:bb:cc:dd:ee:ff",
                "ip": "192.168.1.10",
                "state": 1,
                "uptime": 86400,
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "name": "Switch-Main",
                "model": "USW-24-POE",
                "type": "usw",
                "mac": "11:22:33:44:55:66",
                "ip": "192.168.1.11",
                "state": 1,
                "uptime": 172800,
            },
        ],
    }


@pytest.fixture
def sample_client_data() -> dict:
    """Sample client data for testing."""
    return {
        "meta": {"rc": "ok"},
        "data": [
            {
                "mac": "aa:bb:cc:dd:ee:01",
                "ip": "192.168.1.100",
                "hostname": "laptop-001",
                "is_wired": False,
                "signal": -45,
                "tx_bytes": 1024000,
                "rx_bytes": 2048000,
            },
            {
                "mac": "aa:bb:cc:dd:ee:02",
                "ip": "192.168.1.101",
                "hostname": "desktop-001",
                "is_wired": True,
                "tx_bytes": 5120000,
                "rx_bytes": 10240000,
            },
        ],
    }
