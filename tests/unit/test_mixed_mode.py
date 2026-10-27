"""UNIFI_MIXED_MODE: the cloud and local tool surfaces exposed by one server.

``DEVELOPMENT_PLAN.md`` Phase 5.6. The controller registry has always been able
to hold cloud controllers and local gateways side by side, each with its own
API key, but the tool *modules* were selected once from the single base
``UNIFI_API_TYPE``. A cloud-typed server could therefore route a call to a
registered local gateway while roughly 53 local-only modules had never been
registered, so most of that gateway's tools did not exist. ``UNIFI_MIXED_MODE``
registers the union instead.

Each case imports the server in a subprocess: importing in-process would reuse
whatever ``src.main`` another test module already cached under a different
environment, and the registered surface is exactly what these tests compare.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Settings every case shares. No DATABASE_URL: the module selection is made
#: from the environment alone, so these cases need no Postgres.
_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "AGNOST_ENABLED": "false",
}

#: Reads the registered tool names and the module count out of a fresh import.
_PROBE = (
    "import json\n"
    "import src.main as M\n"
    "names = sorted(\n"
    "    k[5:].split('@', 1)[0]\n"
    "    for k in M.mcp._local_provider._components\n"
    "    if k.startswith('tool:')\n"
    ")\n"
    "print(json.dumps({'tools': names, 'modules': len(M._TOOL_MODULES)}))\n"
)


def _surface(**env: str) -> dict:
    """Import the server under ``env`` and return its registered surface.

    Args:
        env: Environment variables layered over :data:`_BASE_ENV`

    Returns:
        ``{"tools": [...], "modules": N}`` as the imported server reports it
    """
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=str(ROOT),
        env={
            **{k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            **_BASE_ENV,
            **env,
        },
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout.splitlines()[-1])


@pytest.fixture(scope="module")
def cloud_only() -> dict:
    """A cloud-typed server with mixed mode off."""
    return _surface(UNIFI_API_TYPE="cloud-ea")


@pytest.fixture(scope="module")
def mixed() -> dict:
    """A cloud-typed server with mixed mode on, and no base local host."""
    return _surface(UNIFI_API_TYPE="cloud-ea", UNIFI_MIXED_MODE="true")


@pytest.fixture(scope="module")
def local_only() -> dict:
    """A local-typed server, which has always registered cloud plus local."""
    return _surface(UNIFI_API_TYPE="local", UNIFI_LOCAL_HOST="192.0.2.1")


class TestMixedModeSurface:
    def test_cloud_base_alone_has_no_local_tools(self, cloud_only: dict) -> None:
        """Without mixed mode a cloud base exposes only the cloud modules."""
        tools = set(cloud_only["tools"])

        assert "list_hosts" in tools  # a cloud tool
        assert "list_firewall_zones" not in tools
        assert "list_mac_tags" not in tools
        assert "list_protect_cameras" not in tools

    def test_mixed_mode_adds_the_local_tools_to_a_cloud_base(
        self, cloud_only: dict, mixed: dict
    ) -> None:
        """The local-only tools appear without changing the base API type."""
        before, after = set(cloud_only["tools"]), set(mixed["tools"])

        assert before < after, "mixed mode must be a strict superset of cloud-only"
        for name in ("list_firewall_zones", "list_mac_tags", "list_protect_cameras"):
            assert name in after

    def test_mixed_mode_keeps_the_cloud_tools(self, cloud_only: dict, mixed: dict) -> None:
        """Nothing a cloud deployment had is lost by turning mixed mode on."""
        missing = set(cloud_only["tools"]) - set(mixed["tools"])

        assert missing == set()

    def test_mixed_mode_matches_the_local_mode_module_set(
        self, mixed: dict, local_only: dict
    ) -> None:
        """Mixed mode registers the same modules local mode always has."""
        assert mixed["modules"] == local_only["modules"]

    def test_mixed_mode_needs_no_base_local_host(self, mixed: dict) -> None:
        """The gateways come from the registry, so the base stays cloud-shaped.

        The fixture sets no ``UNIFI_LOCAL_HOST``; reaching this assertion at
        all means the import succeeded without one.
        """
        assert mixed["modules"] > 0
        assert "list_firewall_zones" in set(mixed["tools"])

    def test_mixed_mode_exposes_more_modules_than_a_cloud_base(
        self, cloud_only: dict, mixed: dict
    ) -> None:
        assert mixed["modules"] > cloud_only["modules"]


class TestMixedModeWithAProfile:
    def test_a_profile_still_narrows_the_union(self, mixed: dict) -> None:
        """UNIFI_PROFILE applies to the union, not instead of it."""
        narrowed = _surface(
            UNIFI_API_TYPE="cloud-ea",
            UNIFI_MIXED_MODE="true",
            UNIFI_PROFILE="protect",
        )

        assert narrowed["modules"] < mixed["modules"]
        tools = set(narrowed["tools"])
        assert "list_protect_cameras" in tools
        assert "list_firewall_zones" not in tools


class TestMixedModeIsOptIn:
    def test_an_absent_flag_changes_nothing(self, cloud_only: dict) -> None:
        """A deployment that does not ask for mixed mode is unaffected.

        ``cloud_only`` itself sets no ``UNIFI_MIXED_MODE``; this pins that the
        default is off rather than merely unspecified.
        """
        assert cloud_only["modules"] > 0
        assert "list_firewall_zones" not in set(cloud_only["tools"])

    def test_an_explicit_false_changes_nothing(self, cloud_only: dict) -> None:
        surface = _surface(UNIFI_API_TYPE="cloud-ea", UNIFI_MIXED_MODE="false")

        assert surface["modules"] == cloud_only["modules"]
        assert set(surface["tools"]) == set(cloud_only["tools"])
