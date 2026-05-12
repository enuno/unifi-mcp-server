"""Tests for health_check tool in main.py."""

import importlib
import importlib.metadata
import sys
from unittest.mock import patch

_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",
    "UNIFI_API_TYPE": "cloud-ea",
    "AGNOST_ENABLED": "false",
}


def _reload_main() -> object:
    """Re-import src.main with a clean module cache."""
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", _BASE_ENV, clear=False):
        return importlib.import_module("src.main")


class TestHealthCheck:
    """health_check tool returns accurate, up-to-date server information."""

    async def test_version_reads_from_package_metadata_not_hardcode(self) -> None:
        """health_check must read version from metadata, not a hardcoded string.

        Uses a sentinel value to prove the implementation calls
        importlib.metadata.version() rather than returning a literal.
        """
        sentinel = "99.99.99-test-sentinel"
        # Patch the module-level _SERVER_VERSION that main.py reads at startup
        with patch.dict("os.environ", _BASE_ENV, clear=False):
            with patch("importlib.metadata.version", return_value=sentinel):
                main_mod = _reload_main()

        result = await main_mod.health_check()

        assert result["version"] == sentinel, (
            f"health_check returned '{result['version']}' instead of the sentinel "
            f"'{sentinel}'. The version string is hardcoded — replace it with "
            "_SERVER_VERSION read from importlib.metadata.version()."
        )

    async def test_version_matches_installed_package(self) -> None:
        """health_check version must match the installed package version.

        Skips the version-equality assertion when the package is not installed
        (e.g., running from source without `pip install -e .`), since
        health_check correctly returns "unknown" in that case.
        """
        main_mod = _reload_main()
        result = await main_mod.health_check()

        try:
            expected = importlib.metadata.version("unifi-mcp-server")
        except importlib.metadata.PackageNotFoundError:
            expected = "unknown"

        assert result["version"] == expected, (
            f"health_check returned '{result['version']}' but " f"expected '{expected}'."
        )

    async def test_health_check_returns_required_fields(self) -> None:
        """health_check must always return status, version, and api_type."""
        main_mod = _reload_main()
        result = await main_mod.health_check()

        assert result["status"] == "healthy"
        assert "version" in result
        assert "api_type" in result

    async def test_graceful_fallback_when_package_not_installed(self) -> None:
        """health_check must return 'unknown' version if package metadata is missing.

        Covers the case where the server is run directly from source (not installed
        via pip/uv), causing importlib.metadata.version() to raise PackageNotFoundError.
        """
        with patch(
            "importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("unifi-mcp-server"),
        ):
            main_mod = _reload_main()

        result = await main_mod.health_check()

        assert result["version"] == "unknown", (
            f"health_check should return 'unknown' when the package is not installed, "
            f"got '{result['version']}' instead."
        )
        assert result["status"] == "healthy"
