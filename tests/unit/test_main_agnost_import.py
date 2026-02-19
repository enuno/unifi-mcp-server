"""Tests for agnost import handling in main.py.

Regression tests for issue #42: ImportError when agnost package changes its API.
The server must start even when agnost is not installed or has API changes.
"""

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# Minimum env vars required by Settings() at module load time
_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",
    "UNIFI_API_TYPE": "cloud-ea",
    "AGNOST_ENABLED": "false",
}


def _reload_main(env_overrides: dict | None = None) -> ModuleType:
    """Import (or reimport) src.main with a clean module cache."""
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]

    env = {**_BASE_ENV, **(env_overrides or {})}
    with patch.dict("os.environ", env, clear=False):
        return importlib.import_module("src.main")


class TestAgnostImportHandling:
    """Verify server starts regardless of agnost package state."""

    def test_server_starts_when_agnost_has_no_config_export(self) -> None:
        """Server must start when agnost package lacks the 'config' export (issue #42)."""
        broken_agnost = ModuleType("agnost")
        # Deliberately omit 'config' — simulating the breaking API change in v0.1.13
        broken_agnost.track = MagicMock()

        orig = sys.modules.get("agnost")
        sys.modules["agnost"] = broken_agnost
        try:
            _reload_main({"AGNOST_ENABLED": "false"})
        except ImportError as exc:
            raise AssertionError(
                f"Server failed to start due to agnost import issue: {exc}"
            ) from exc
        finally:
            if orig is None:
                sys.modules.pop("agnost", None)
            else:
                sys.modules["agnost"] = orig

    def test_server_starts_when_agnost_not_installed(self) -> None:
        """Server must start when agnost is not installed at all."""
        orig = sys.modules.get("agnost")
        sys.modules["agnost"] = None  # type: ignore[assignment]  # simulate missing module
        try:
            _reload_main({"AGNOST_ENABLED": "false"})
        except ImportError as exc:
            raise AssertionError(f"Server failed to start without agnost installed: {exc}") from exc
        finally:
            if orig is None:
                sys.modules.pop("agnost", None)
            else:
                sys.modules["agnost"] = orig

    def test_server_starts_with_agnost_disabled_by_default(self) -> None:
        """Server starts normally when AGNOST_ENABLED is not set."""
        broken_agnost = ModuleType("agnost")
        # No 'config', no 'track' — worst-case broken package

        orig = sys.modules.get("agnost")
        sys.modules["agnost"] = broken_agnost
        try:
            _reload_main({"AGNOST_ENABLED": "false"})
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"Server failed to start with agnost disabled: {exc}") from exc
        finally:
            if orig is None:
                sys.modules.pop("agnost", None)
            else:
                sys.modules["agnost"] = orig

    def test_server_starts_when_agnost_enabled_but_api_changed(self) -> None:
        """Server must start with AGNOST_ENABLED=true when agnost API has changed (issue #42).

        This is the primary regression test: agnost.config was removed in v0.1.13,
        causing ImportError even when agnost tracking was enabled. The fix wraps
        the imports in try/except, so the server starts and logs a warning instead.
        """
        broken_agnost = ModuleType("agnost")
        # 'config' is absent — exact API break from agnost v0.1.13
        broken_agnost.track = MagicMock()

        orig = sys.modules.get("agnost")
        sys.modules["agnost"] = broken_agnost
        try:
            _reload_main({"AGNOST_ENABLED": "true", "AGNOST_ORG_ID": "org-123"})
        except ImportError as exc:
            raise AssertionError(
                f"Server crashed with ImportError when agnost API changed (issue #42): {exc}"
            ) from exc
        finally:
            if orig is None:
                sys.modules.pop("agnost", None)
            else:
                sys.modules["agnost"] = orig
