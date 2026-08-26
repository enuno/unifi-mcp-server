#!/usr/bin/env python3
"""
Diagnostics Integration Test Suite

Tests all diagnostics-related MCP tools against real UniFi environments.
"""

from typing import Any

import pytest

from src.tools import diagnostics
from tests.integration.test_harness import TestEnvironment, TestHarness, TestSuite


@pytest.mark.integration
async def test_get_network_references(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test get_network_references tool."""
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {
            "status": "SKIP",
            "message": "Cloud APIs may not support network references (local only)",
        }

    try:
        # First, discover a network
        from src.tools.networks import list_vlans

        network_list = await list_vlans(
            site_id=env.site_id,
            settings=settings,
            limit=1,
        )

        if not network_list:
            return {
                "status": "SKIP",
                "message": "No networks found for references test",
            }

        network_id = network_list[0].get("_id") or network_list[0].get("id")
        assert network_id, "Network must have an ID"

        result = await diagnostics.get_network_references(
            site_id=env.site_id,
            network_id=network_id,
            settings=settings,
        )

        assert isinstance(result, dict), "Result must be a dictionary"
        assert "references" in result, "Result must have references"
        assert "network_id" in result, "Result must have network_id"

        return {
            "status": "PASS",
            "message": f"Retrieved {len(result.get('references', []))} references for network {network_id[:8]}...",
            "details": {
                "network_id": network_id[:8] + "...",
                "reference_count": len(result.get("references", [])),
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


@pytest.mark.integration
async def test_run_speed_test(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test run_speed_test tool."""
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {
            "status": "SKIP",
            "message": "Cloud APIs may not support speed test execution (local only)",
        }

    try:
        result = await diagnostics.run_speed_test(
            site_id=env.site_id,
            settings=settings,
            confirm=True,
        )

        assert isinstance(result, dict), "Result must be a dictionary"
        assert "status" in result, "Result must have status"

        return {
            "status": "PASS",
            "message": f"Speed test initiated with status: {result.get('status')}",
            "details": {
                "status": result.get("status"),
                "test_id": result.get("test_id"),
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


@pytest.mark.integration
async def test_get_speed_test_status(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test get_speed_test_status tool."""
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {
            "status": "SKIP",
            "message": "Cloud APIs may not support speed test status (local only)",
        }

    try:
        result = await diagnostics.get_speed_test_status(
            site_id=env.site_id,
            settings=settings,
        )

        assert isinstance(result, dict), "Result must be a dictionary"
        assert "status" in result, "Result must have status"

        return {
            "status": "PASS",
            "message": f"Speed test status: {result.get('status')}",
            "details": {
                "status": result.get("status"),
                "download_speed_mbps": result.get("download_speed_mbps"),
                "upload_speed_mbps": result.get("upload_speed_mbps"),
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


@pytest.mark.integration
async def test_get_speed_test_history(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test get_speed_test_history tool."""
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {
            "status": "SKIP",
            "message": "Cloud APIs may not support speed test history (local only)",
        }

    try:
        result = await diagnostics.get_speed_test_history(
            site_id=env.site_id,
            settings=settings,
        )

        assert isinstance(result, list), "Result must be a list"

        if not result:
            return {
                "status": "SKIP",
                "message": "No speed test history found",
            }

        return {
            "status": "PASS",
            "message": f"Retrieved {len(result)} speed test results",
            "details": {
                "count": len(result),
                "latest_status": result[0].get("status") if result else None,
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


@pytest.mark.integration
async def test_get_spectrum_scan(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test get_spectrum_scan tool."""
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {
            "status": "SKIP",
            "message": "Cloud APIs do not support spectrum scan (local only)",
        }

    try:
        result = await diagnostics.get_spectrum_scan(
            site_id=env.site_id,
            settings=settings,
        )

        assert isinstance(result, dict), "Result must be a dictionary"

        if not result:
            return {
                "status": "SKIP",
                "message": "No spectrum scan data available (may need to trigger scan first)",
            }

        return {
            "status": "PASS",
            "message": f"Retrieved spectrum scan for {result.get('device_name', 'unknown')}",
            "details": {
                "device_id": result.get("device_id", "unknown")[:8] + "...",
                "frequency_band": result.get("frequency_band"),
                "channel": result.get("channel"),
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


@pytest.mark.integration
async def test_list_spectrum_interference(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test list_spectrum_interference tool."""
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {
            "status": "SKIP",
            "message": "Cloud APIs do not support spectrum interference (local only)",
        }

    try:
        result = await diagnostics.list_spectrum_interference(
            site_id=env.site_id,
            settings=settings,
        )

        assert isinstance(result, list), "Result must be a list"

        if not result:
            return {
                "status": "SKIP",
                "message": "No spectrum interference data available",
            }

        return {
            "status": "PASS",
            "message": f"Retrieved {len(result)} interference entries",
            "details": {
                "count": len(result),
                "first_channel": result[0].get("channel") if result else None,
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


def create_diagnostics_suite() -> TestSuite:
    """Create the diagnostics test suite."""
    return TestSuite(
        name="diagnostics",
        description="Network Diagnostics Tools - get_network_references, run_speed_test, get_speed_test_status, get_speed_test_history, get_spectrum_scan, list_spectrum_interference",
        tests=[
            test_get_network_references,
            test_run_speed_test,
            test_get_speed_test_status,
            test_get_speed_test_history,
            test_get_spectrum_scan,
            test_list_spectrum_interference,
        ],
    )


# CLI entry point
if __name__ == "__main__":
    import asyncio
    import sys
    from pathlib import Path

    async def main():
        harness = TestHarness()
        harness.verbose = "--verbose" in sys.argv or "-v" in sys.argv

        suite = create_diagnostics_suite()
        harness.register_suite(suite)

        # Parse environment filter
        env_filter = None
        if "--env" in sys.argv:
            idx = sys.argv.index("--env")
            if idx + 1 < len(sys.argv):
                env_filter = [sys.argv[idx + 1]]

        # Run suite
        await harness.run_suite("diagnostics", environment_filter=env_filter)

        # Print summary
        harness.print_summary()

        # Export results if requested
        if "--export" in sys.argv:
            idx = sys.argv.index("--export")
            output_file = (
                Path(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else Path("test_results.json")
            )
            harness.export_results(output_file)

        # Exit with error code if any tests failed
        failed_count = sum(1 for r in harness.results if r.status.value in ["FAIL", "ERROR"])
        sys.exit(1 if failed_count > 0 else 0)

    asyncio.run(main())
