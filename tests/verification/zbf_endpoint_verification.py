#!/usr/bin/env python3
"""
ZBF Endpoint Verification Script

Tests all Zone-Based Firewall endpoints against real UniFi Network API
to verify endpoint paths, request/response formats, and model accuracy.

Usage:
    python tests/verification/zbf_endpoint_verification.py

Requirements:
    - Valid UNIFI_API_KEY in .env
    - UniFi Network Application 9.0+ with ZBF enabled
    - At least one site with ZBF configured
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api.client import UniFiClient
from src.config import Settings


class ZBFEndpointVerifier:
    """Verifies ZBF endpoints against real UniFi API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "api_type": str(settings.api_type.value),
            "base_url": settings.base_url,
            "endpoints": {},
            "summary": {
                "total": 0,
                "verified": 0,
                "failed": 0,
                "not_found": 0,
            },
        }

    async def verify_endpoint(
        self,
        name: str,
        method: str,
        path: str,
        description: str,
        payload: dict[str, Any] | None = None,
        expected_status: int = 200,
    ) -> dict[str, Any]:
        """Verify a single endpoint."""
        print(f"\n{'='*80}")
        print(f"Testing: {name}")
        print(f"Method: {method} {path}")
        print(f"Description: {description}")

        result: dict[str, Any] = {
            "endpoint": path,
            "method": method,
            "description": description,
            "status": "unknown",
            "http_status": None,
            "response": None,
            "error": None,
            "verified": False,
        }

        try:
            async with UniFiClient(self.settings) as client:
                if method == "GET":
                    response = await client.get(path)
                elif method == "POST":
                    response = await client.post(path, payload or {})
                elif method == "PUT":
                    response = await client.put(path, payload or {})
                elif method == "DELETE":
                    response = await client.delete(path)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                result["http_status"] = 200
                result["response"] = response
                result["status"] = "success"
                result["verified"] = True

                print(f"✅ SUCCESS: {name}")
                print(f"Response: {json.dumps(response, indent=2)[:500]}...")

        except Exception as e:
            error_str = str(e)
            result["error"] = error_str

            # Check if it's a 404 (endpoint doesn't exist)
            if "404" in error_str or "Not Found" in error_str:
                result["status"] = "not_found"
                result["http_status"] = 404
                print(f"❌ NOT FOUND: {name}")
                print(f"   Endpoint does not exist (404)")
            else:
                result["status"] = "error"
                print(f"⚠️  ERROR: {name}")
                print(f"   {error_str}")

        return result

    async def verify_all_endpoints(self, site_id: str) -> None:
        """Verify all ZBF endpoints."""
        print(f"\n{'#'*80}")
        print(f"# ZBF Endpoint Verification")
        print(f"# Site: {site_id}")
        print(f"# API: {self.settings.api_type.value} ({self.settings.base_url})")
        print(f"# Timestamp: {self.results['timestamp']}")
        print(f"{'#'*80}")

        # Zone Management Endpoints (Read-Only First)
        print(f"\n{'*'*80}")
        print("* ZONE MANAGEMENT - READ OPERATIONS")
        print(f"{'*'*80}")

        # 1. List zones
        result = await self.verify_endpoint(
            name="list_firewall_zones",
            method="GET",
            path=f"/integration/v1/sites/{site_id}/firewall/zones",
            description="List all firewall zones",
        )
        self.results["endpoints"]["list_firewall_zones"] = result
        self.results["summary"]["total"] += 1
        if result["verified"]:
            self.results["summary"]["verified"] += 1
        elif result["status"] == "not_found":
            self.results["summary"]["not_found"] += 1
        else:
            self.results["summary"]["failed"] += 1

        # Extract a zone_id from the response if available
        zone_id = None
        if result["verified"] and result["response"]:
            zones = result["response"].get("data", [])
            if zones:
                zone_id = zones[0].get("_id")
                print(f"\n   Found zone for testing: {zone_id}")

        # 2. Get zone networks (requires zone_id)
        if zone_id:
            result = await self.verify_endpoint(
                name="get_zone_networks",
                method="GET",
                path=f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}",
                description="Get networks assigned to a zone",
            )
            self.results["endpoints"]["get_zone_networks"] = result
            self.results["summary"]["total"] += 1
            if result["verified"]:
                self.results["summary"]["verified"] += 1
            elif result["status"] == "not_found":
                self.results["summary"]["not_found"] += 1
            else:
                self.results["summary"]["failed"] += 1

        # 3. Get zone statistics (speculative endpoint)
        if zone_id:
            result = await self.verify_endpoint(
                name="get_zone_statistics",
                method="GET",
                path=f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}/statistics",
                description="Get traffic statistics for a zone (SPECULATIVE)",
            )
            self.results["endpoints"]["get_zone_statistics"] = result
            self.results["summary"]["total"] += 1
            if result["verified"]:
                self.results["summary"]["verified"] += 1
            elif result["status"] == "not_found":
                self.results["summary"]["not_found"] += 1
            else:
                self.results["summary"]["failed"] += 1

        # Zone Policy Matrix Endpoints
        print(f"\n{'*'*80}")
        print("* ZONE POLICY MATRIX - READ OPERATIONS")
        print(f"{'*'*80}")

        # 4. Get ZBF matrix
        result = await self.verify_endpoint(
            name="get_zbf_matrix",
            method="GET",
            path=f"/integration/v1/sites/{site_id}/firewall/policies/zone-matrix",
            description="Get zone-to-zone policy matrix",
        )
        self.results["endpoints"]["get_zbf_matrix"] = result
        self.results["summary"]["total"] += 1
        if result["verified"]:
            self.results["summary"]["verified"] += 1
        elif result["status"] == "not_found":
            self.results["summary"]["not_found"] += 1
        else:
            self.results["summary"]["failed"] += 1

        # 5. Get zone policies (requires zone_id)
        if zone_id:
            result = await self.verify_endpoint(
                name="get_zone_policies",
                method="GET",
                path=f"/integration/v1/sites/{site_id}/firewall/policies/zones/{zone_id}",
                description="Get all policies for a specific zone",
            )
            self.results["endpoints"]["get_zone_policies"] = result
            self.results["summary"]["total"] += 1
            if result["verified"]:
                self.results["summary"]["verified"] += 1
            elif result["status"] == "not_found":
                self.results["summary"]["not_found"] += 1
            else:
                self.results["summary"]["failed"] += 1

        # 6. Get specific zone-to-zone policy (requires two zones)
        if zone_id:
            # Try to get a second zone for testing
            zones_result = self.results["endpoints"].get("list_firewall_zones", {})
            zones_data = zones_result.get("response", {}).get("data", [])
            zone_id_2 = None
            if len(zones_data) >= 2:
                zone_id_2 = zones_data[1].get("_id")

            if zone_id_2:
                result = await self.verify_endpoint(
                    name="get_zone_matrix_policy",
                    method="GET",
                    path=f"/integration/v1/sites/{site_id}/firewall/policies/zone-matrix/{zone_id}/{zone_id_2}",
                    description="Get specific zone-to-zone policy",
                )
                self.results["endpoints"]["get_zone_matrix_policy"] = result
                self.results["summary"]["total"] += 1
                if result["verified"]:
                    self.results["summary"]["verified"] += 1
                elif result["status"] == "not_found":
                    self.results["summary"]["not_found"] += 1
                else:
                    self.results["summary"]["failed"] += 1

        # Application Blocking Endpoints
        print(f"\n{'*'*80}")
        print("* APPLICATION BLOCKING - READ OPERATIONS")
        print(f"{'*'*80}")

        # 7. List blocked applications (speculative endpoint)
        if zone_id:
            result = await self.verify_endpoint(
                name="list_blocked_applications",
                method="GET",
                path=f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}/app-block",
                description="List blocked applications in zone (SPECULATIVE)",
            )
            self.results["endpoints"]["list_blocked_applications"] = result
            self.results["summary"]["total"] += 1
            if result["verified"]:
                self.results["summary"]["verified"] += 1
            elif result["status"] == "not_found":
                self.results["summary"]["not_found"] += 1
            else:
                self.results["summary"]["failed"] += 1

        # Note: We're NOT testing mutating operations (CREATE, UPDATE, DELETE)
        # to avoid modifying production configurations
        print(f"\n{'*'*80}")
        print("* MUTATING OPERATIONS - SKIPPED")
        print(f"{'*'*80}")
        print("⚠️  The following endpoints were NOT tested to avoid modifying")
        print("   production configurations:")
        print("   - create_firewall_zone (POST)")
        print("   - update_firewall_zone (PUT)")
        print("   - delete_firewall_zone (DELETE)")
        print("   - assign_network_to_zone (PUT)")
        print("   - unassign_network_from_zone (PUT)")
        print("   - update_zbf_policy (PUT)")
        print("   - delete_zbf_policy (DELETE)")
        print("   - block_application_by_zone (POST)")
        print("\n   These should be tested manually in a test environment.")

    def print_summary(self) -> None:
        """Print verification summary."""
        print(f"\n{'='*80}")
        print("VERIFICATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total Endpoints Tested: {self.results['summary']['total']}")
        print(f"✅ Verified: {self.results['summary']['verified']}")
        print(f"❌ Not Found (404): {self.results['summary']['not_found']}")
        print(f"⚠️  Failed (Other): {self.results['summary']['failed']}")

        success_rate = 0
        if self.results["summary"]["total"] > 0:
            success_rate = (
                self.results["summary"]["verified"] / self.results["summary"]["total"]
            ) * 100

        print(f"\nSuccess Rate: {success_rate:.1f}%")
        print(f"{'='*80}\n")

    def save_results(self, output_path: str) -> None:
        """Save results to JSON file."""
        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"Results saved to: {output_path}")


async def main() -> None:
    """Main verification function."""
    # Load settings from .env
    settings = Settings()

    print(f"\nConnecting to UniFi API...")
    print(f"API Type: {settings.api_type.value}")
    print(f"Base URL: {settings.base_url}")

    # Get default site or use 'default'
    site_id = settings.default_site or "default"

    # Create verifier
    verifier = ZBFEndpointVerifier(settings)

    # Run verification
    await verifier.verify_all_endpoints(site_id)

    # Print summary
    verifier.print_summary()

    # Save results
    output_dir = Path(__file__).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"zbf_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    verifier.save_results(str(output_path))

    # Print recommendations
    print("\nRECOMMENDATIONS:")
    if verifier.results["summary"]["not_found"] > 0:
        print("❌ Some endpoints returned 404 - these are likely speculative.")
        print("   Update documentation to mark as unverified/speculative.")

    if verifier.results["summary"]["verified"] > 0:
        print("✅ Verified endpoints can be marked as tested in ZBF_STATUS.md")

    print("\nNEXT STEPS:")
    print("1. Review zbf_verification_*.json for detailed results")
    print("2. Compare actual responses with Pydantic models")
    print("3. Update models if response structure differs")
    print("4. Test mutating operations in test environment")
    print("5. Update ZBF_STATUS.md with verification results")


if __name__ == "__main__":
    asyncio.run(main())
