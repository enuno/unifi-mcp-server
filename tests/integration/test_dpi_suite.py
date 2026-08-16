#!/usr/bin/env python3
"""
DPI (Deep Packet Inspection) Integration Test Suite

Tests all DPI-related MCP tools against real UniFi environments.
All DPI operations are read-only.
"""

from typing import Any

import pytest

from src.tools import dpi
from tests.integration.test_harness import TestEnvironment, TestSuite


@pytest.mark.integration
async def test_get_dpi_statistics(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test get_dpi_statistics tool."""
    # Skip on cloud APIs - DPI statistics are local only
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {
            "status": "SKIP",
            "message": "Cloud APIs do not support DPI statistics (local only)",
        }

    try:
        result = await dpi.get_dpi_statistics(
            site_id=env.site_id,
            settings=settings,
        )

        # Validate response structure
        assert isinstance(result, dict), "Result must be a dictionary"
        assert "site_id" in result, "Must have site_id"
        assert "applications" in result, "Must have applications list"
        assert "categories" in result, "Must have categories list"

        app_count = len(result.get("applications", []))
        cat_count = len(result.get("categories", []))

        return {
            "status": "PASS",
            "message": f"Retrieved DPI statistics: {app_count} apps, {cat_count} categories",
            "details": {
                "application_count": app_count,
                "category_count": cat_count,
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


@pytest.mark.integration
async def test_get_dpi_statistics_empty_carries_note(
    settings, env: TestEnvironment
) -> dict[str, Any]:
    """A flow-engine controller must report empty counters with a note.

    Current releases run traffic identification through the flow engine, so
    stat/sitedpi legitimately answers with no counters; the tool then points
    at the flow tools instead of returning a silent empty.
    """
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {"status": "SKIP", "message": "Cloud APIs do not support DPI statistics"}

    try:
        result = await dpi.get_dpi_statistics(
            site_id=env.site_id,
            settings=settings,
        )

        if result.get("applications") or result.get("categories"):
            return {
                "status": "SKIP",
                "message": "Controller reports classic DPI counters; note not applicable",
            }

        assert "note" in result, "Empty counters must carry an explanatory note"
        assert "get_top_flows" in result["note"], "Note must point at the flow tools"

        return {
            "status": "PASS",
            "message": "Empty DPI counters carry the flow-engine note",
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


@pytest.mark.integration
async def test_list_top_applications(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test list_top_applications tool."""
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {"status": "SKIP", "message": "Cloud APIs do not support DPI statistics"}

    try:
        result = await dpi.list_top_applications(
            site_id=env.site_id,
            settings=settings,
            limit=5,
        )

        # Validate response structure
        assert isinstance(result, list), "Result must be a list"

        if not result:
            return {
                "status": "SKIP",
                "message": "No application data found (flow-engine controller or no traffic)",
            }

        # Rows are the controller's own sitedpi entries: numeric catalog ids
        # plus byte counters and the computed total.
        app = result[0]
        assert "app" in app, "Application row must carry the 'app' catalog id"
        assert "total_bytes" in app, "Application row must have 'total_bytes'"

        # Verify limit is respected
        assert len(result) <= 5, "Result should respect limit parameter"

        return {
            "status": "PASS",
            "message": f"Retrieved top {len(result)} applications",
            "details": {
                "top_app_id": app.get("app"),
                "top_app_bytes": app.get("total_bytes", 0),
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


@pytest.mark.integration
async def test_get_client_dpi(settings, env: TestEnvironment) -> dict[str, Any]:
    """Test get_client_dpi for discovered client."""
    if env.api_type in ["cloud-v1", "cloud-ea"]:
        return {"status": "SKIP", "message": "Cloud APIs do not support DPI statistics"}

    try:
        # First, discover a client
        from src.tools import clients

        client_list = await clients.list_active_clients(
            site_id=env.site_id,
            settings=settings,
            limit=1,
        )

        if not client_list:
            return {"status": "SKIP", "message": "No clients found for DPI test"}

        client_mac = client_list[0].get("mac")
        assert client_mac, "Client must have a MAC address"

        # Get client DPI statistics
        result = await dpi.get_client_dpi(
            site_id=env.site_id,
            client_mac=client_mac,
            settings=settings,
            time_range="24h",
        )

        # Validate response structure
        assert isinstance(result, dict), "Result must be a dictionary"
        assert "client_mac" in result, "Must have client_mac"
        assert "applications" in result, "Must have applications list"
        assert result.get("client_mac") == client_mac, "Client MAC must match"

        app_count = len(result.get("applications", []))

        return {
            "status": "PASS",
            "message": f"Retrieved DPI data for client (found {app_count} applications)",
            "details": {
                "client_mac": client_mac[:8] + "...",
                "application_count": app_count,
                "total_bytes": result.get("total_bytes", 0),
            },
        }

    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {str(e)}"}


def create_dpi_suite() -> TestSuite:
    """Create the DPI test suite."""
    return TestSuite(
        name="dpi",
        description="DPI (Deep Packet Inspection) Tools - statistics, top applications, client DPI data",
        tests=[
            test_get_dpi_statistics,
            test_get_dpi_statistics_empty_carries_note,
            test_list_top_applications,
            test_get_client_dpi,
        ],
    )


# CLI entry point
if __name__ == "__main__":
    import asyncio
    import sys
    from pathlib import Path

    async def main():
        from tests.integration.test_harness import TestHarness

        harness = TestHarness()
        harness.verbose = "--verbose" in sys.argv or "-v" in sys.argv

        suite = create_dpi_suite()
        harness.register_suite(suite)

        # Parse environment filter
        env_filter = None
        if "--env" in sys.argv:
            idx = sys.argv.index("--env")
            if idx + 1 < len(sys.argv):
                env_filter = [sys.argv[idx + 1]]

        # Run suite
        await harness.run_suite("dpi", environment_filter=env_filter)

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
