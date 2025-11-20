"""Pytest configuration and shared fixtures."""

import pytest

from src.config import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create test settings."""
    # Set environment variables for Settings to read
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key-XXZDILlzznocKT6JG7_s9VlMAW0HD8Ew")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud")
    monkeypatch.setenv("UNIFI_HOST", "api.ui.com")
    monkeypatch.setenv("UNIFI_VERIFY_SSL", "true")

    # Settings will read from environment variables
    return Settings()


@pytest.fixture(autouse=True)
def reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset environment variables before each test and prevent .env loading."""
    # Clear any existing UNIFI_ environment variables
    import os
    from pathlib import Path

    for key in list(os.environ.keys()):
        if key.startswith("UNIFI_") or key == "LOG_LEVEL":
            monkeypatch.delenv(key, raising=False)

    # Temporarily rename .env file to prevent Pydantic from auto-loading it
    env_file = Path(__file__).parent.parent / ".env"
    temp_env_file = Path(__file__).parent.parent / ".env.test_backup"

    if env_file.exists() and not temp_env_file.exists():
        env_file.rename(temp_env_file)
        # Schedule restoration after test
        import atexit
        def restore_env():
            if temp_env_file.exists():
                temp_env_file.rename(env_file)
        atexit.register(restore_env)


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
