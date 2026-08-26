"""Pytest configuration for UniFi MCP Server tests."""

import os
import sys
from pathlib import Path

import pytest

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True, scope="function")
def isolate_env_file(tmp_path, monkeypatch):
    """Isolate process environment and working directory during unit tests.

    Settings intentionally ignores working-directory .env files, but a temporary
    directory also keeps file-producing tests isolated from the checkout.
    """
    # Change to a temp directory so .env file won't be found
    temp_dir = tmp_path / "test_env"
    temp_dir.mkdir()
    monkeypatch.chdir(temp_dir)

    # Clear all UNIFI_* env vars so tests start clean
    for key in list(os.environ.keys()):
        if key.startswith("UNIFI_") or key.startswith("LOG_"):
            monkeypatch.delenv(key, raising=False)

    yield

    # Restore working directory (handled by monkeypatch automatically)
