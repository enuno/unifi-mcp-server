#!/usr/bin/env python3
"""
UniFi MCP Server Test Harness Framework

Provides a comprehensive testing framework for running real-world integration
tests against both UniFi Cloud and Local Gateway APIs.

Features:
- Multi-environment support (cloud, local lab, local home)
- API mode testing (cloud-v1, cloud-ea, local)
- Test suite organization and discovery
- Detailed reporting with pass/fail/skip statistics
- Error handling and debugging output
- Extensible test framework for new tools
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.config import Settings


class TestStatus(Enum):
    """Test execution status."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass
class TestResult:
    """Result from a single test execution."""

    test_name: str
    status: TestStatus
    duration_ms: float
    message: str = ""
    error: Exception | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestEnvironment:
    """Configuration for a UniFi test environment."""

    name: str
    api_type: str  # 'cloud-v1', 'cloud-ea', or 'local'
    api_key: str
    local_host: str | None = None
    local_port: int = 443
    verify_ssl: bool = False
    site_id: str = "default"

    def to_settings(self) -> Settings:
        """Convert environment to Settings object."""
        import os

        # Temporarily set environment variables
        env_backup = {
            "UNIFI_API_KEY": os.getenv("UNIFI_API_KEY"),
            "UNIFI_API_TYPE": os.getenv("UNIFI_API_TYPE"),
            "UNIFI_LOCAL_HOST": os.getenv("UNIFI_LOCAL_HOST"),
            "UNIFI_LOCAL_PORT": os.getenv("UNIFI_LOCAL_PORT"),
            "UNIFI_LOCAL_VERIFY_SSL": os.getenv("UNIFI_LOCAL_VERIFY_SSL"),
        }

        os.environ["UNIFI_API_KEY"] = self.api_key
        os.environ["UNIFI_API_TYPE"] = self.api_type
        if self.local_host:
            os.environ["UNIFI_LOCAL_HOST"] = self.local_host
            os.environ["UNIFI_LOCAL_PORT"] = str(self.local_port)
            os.environ["UNIFI_LOCAL_VERIFY_SSL"] = str(self.verify_ssl).lower()

        settings = Settings()

        # Restore environment
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

        return settings


@dataclass
class TestSuite:
    """A collection of related tests."""

    name: str
    description: str
    tests: list[Callable] = field(default_factory=list)
    setup: Callable | None = None
    teardown: Callable | None = None


class TestHarness:
    """Main test harness for running UniFi MCP Server integration tests."""

    def __init__(self, environments: list[TestEnvironment] | None = None):
        """
        Initialize test harness.

        Args:
            environments: List of test environments (if None, loads from .env)
        """
        self.environments = environments or self._load_environments()
        self.test_suites: dict[str, TestSuite] = {}
        self.results: list[TestResult] = []
        self.verbose = False

    def _load_environments(self) -> list[TestEnvironment]:
        """Load test environments from .env file."""
        load_dotenv()

        import os

        environments = []

        # Load unifi-lab environment
        lab_key = os.getenv("UNIFI_LAB_API_KEY")
        if lab_key:
            environments.append(
                TestEnvironment(
                    name="unifi-lab",
                    api_type="local",
                    api_key=lab_key,
                    local_host=os.getenv("UNIFI_LAB_HOST", "10.2.0.1"),
                    local_port=int(os.getenv("UNIFI_LAB_PORT", "443")),
                    verify_ssl=os.getenv("UNIFI_LAB_VERIFY_SSL", "false").lower() == "true",
                )
            )

        # Load unifi-home environment
        home_key = os.getenv("UNIFI_HOME_API_KEY")
        if home_key:
            environments.append(
                TestEnvironment(
                    name="unifi-home",
                    api_type="local",
                    api_key=home_key,
                    local_host=os.getenv("UNIFI_HOME_HOST", "192.168.2.1"),
                    local_port=int(os.getenv("UNIFI_HOME_PORT", "443")),
                    verify_ssl=os.getenv("UNIFI_HOME_VERIFY_SSL", "false").lower() == "true",
                )
            )

        # Load cloud-v1 environment (lab site)
        cloud_v1_key = os.getenv("UNIFI_CLOUD_V1_API_KEY") or os.getenv("UNIFI_CLOUD_API_KEY")
        cloud_site_lab = os.getenv("UNIFI_CLOUD_SITE_LAB", "63be0605bc01d21891cef8df")
        if cloud_v1_key:
            environments.append(
                TestEnvironment(
                    name="unifi-cloud-v1-lab",
                    api_type="cloud-v1",
                    api_key=cloud_v1_key,
                    site_id=cloud_site_lab,
                )
            )

        # Load cloud-ea environment (lab site)
        cloud_ea_key = os.getenv("UNIFI_CLOUD_EA_API_KEY") or os.getenv("UNIFI_CLOUD_API_KEY")
        if cloud_ea_key:
            environments.append(
                TestEnvironment(
                    name="unifi-cloud-ea-lab",
                    api_type="cloud-ea",
                    api_key=cloud_ea_key,
                    site_id=cloud_site_lab,
                )
            )

        # Load cloud-v1 environment (home site)
        cloud_site_home = os.getenv("UNIFI_CLOUD_SITE_HOME", "68f9483dd8b48c07c614ff34")
        if cloud_v1_key:
            environments.append(
                TestEnvironment(
                    name="unifi-cloud-v1-home",
                    api_type="cloud-v1",
                    api_key=cloud_v1_key,
                    site_id=cloud_site_home,
                )
            )

        # Load cloud-ea environment (home site)
        if cloud_ea_key:
            environments.append(
                TestEnvironment(
                    name="unifi-cloud-ea-home",
                    api_type="cloud-ea",
                    api_key=cloud_ea_key,
                    site_id=cloud_site_home,
                )
            )

        return environments

    def register_suite(self, suite: TestSuite) -> None:
        """Register a test suite."""
        self.test_suites[suite.name] = suite

    def register_test(self, suite_name: str, test_func: Callable) -> None:
        """Register a test function to a suite."""
        if suite_name not in self.test_suites:
            raise ValueError(f"Test suite '{suite_name}' not found")
        self.test_suites[suite_name].tests.append(test_func)

    async def run_test(
        self,
        test_func: Callable,
        env: TestEnvironment,
        settings: Settings,
    ) -> TestResult:
        """
        Run a single test function.

        Args:
            test_func: Test function to execute
            env: Test environment
            settings: Settings object for the test

        Returns:
            TestResult with execution details
        """
        test_name = f"{env.name}/{test_func.__name__}"
        start_time = datetime.now()

        try:
            # Run the test
            result = await test_func(settings, env)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            if isinstance(result, dict):
                # Test returned detailed results
                return TestResult(
                    test_name=test_name,
                    status=TestStatus(result.get("status", "PASS")),
                    duration_ms=duration_ms,
                    message=result.get("message", ""),
                    details=result.get("details", {}),
                )
            else:
                # Test returned boolean or None
                status = TestStatus.PASS if result else TestStatus.FAIL
                return TestResult(
                    test_name=test_name,
                    status=status,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return TestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_ms=duration_ms,
                message=str(e),
                error=e,
            )

    async def run_suite(
        self,
        suite_name: str,
        environment_filter: list[str] | None = None,
    ) -> list[TestResult]:
        """
        Run all tests in a suite across specified environments.

        Args:
            suite_name: Name of the suite to run
            environment_filter: List of environment names to test (None = all)

        Returns:
            List of TestResult objects
        """
        if suite_name not in self.test_suites:
            raise ValueError(f"Test suite '{suite_name}' not found")

        suite = self.test_suites[suite_name]
        results = []

        # Filter environments
        envs = self.environments
        if environment_filter:
            envs = [e for e in envs if e.name in environment_filter]

        print(f"\n{'=' * 70}")
        print(f"Running Test Suite: {suite.name}")
        print(f"Description: {suite.description}")
        print(f"Environments: {', '.join(e.name for e in envs)}")
        print(f"Tests: {len(suite.tests)}")
        print(f"{'=' * 70}\n")

        for env in envs:
            settings = env.to_settings()

            # Run suite setup if defined
            if suite.setup:
                try:
                    await suite.setup(settings, env)
                except Exception as e:
                    print(f"⚠️  Suite setup failed for {env.name}: {e}")
                    continue

            # Run all tests in the suite
            for test_func in suite.tests:
                result = await self.run_test(test_func, env, settings)
                results.append(result)
                self._print_result(result)

            # Run suite teardown if defined
            if suite.teardown:
                try:
                    await suite.teardown(settings, env)
                except Exception as e:
                    print(f"⚠️  Suite teardown failed for {env.name}: {e}")

        return results

    async def run_all(
        self,
        environment_filter: list[str] | None = None,
    ) -> dict[str, list[TestResult]]:
        """
        Run all registered test suites.

        Args:
            environment_filter: List of environment names to test (None = all)

        Returns:
            Dictionary mapping suite names to their results
        """
        all_results = {}

        for suite_name in self.test_suites:
            results = await self.run_suite(suite_name, environment_filter)
            all_results[suite_name] = results
            self.results.extend(results)

        return all_results

    def _print_result(self, result: TestResult) -> None:
        """Print a single test result."""
        status_icons = {
            TestStatus.PASS: "✓",
            TestStatus.FAIL: "✗",
            TestStatus.SKIP: "⚠",
            TestStatus.ERROR: "⚠",
        }

        icon = status_icons.get(result.status, "?")
        duration = f"{result.duration_ms:.1f}ms"

        print(f"{icon} {result.test_name:<50} {result.status.value:<6} ({duration})")

        if result.message and self.verbose:
            print(f"  Message: {result.message}")

        if result.error and self.verbose:
            print(f"  Error: {type(result.error).__name__}: {result.error}")

    def print_summary(self) -> None:
        """Print test execution summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASS)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAIL)
        errors = sum(1 for r in self.results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIP)

        total_duration = sum(r.duration_ms for r in self.results)

        print(f"\n{'=' * 70}")
        print("TEST SUMMARY")
        print(f"{'=' * 70}")
        print(f"Total Tests:   {total}")
        print(
            f"Passed:        {passed} ({passed/total*100:.1f}%)"
            if total > 0
            else "Passed:        0"
        )
        print(f"Failed:        {failed}")
        print(f"Errors:        {errors}")
        print(f"Skipped:       {skipped}")
        print(f"Total Time:    {total_duration:.1f}ms ({total_duration/1000:.2f}s)")
        print(f"{'=' * 70}\n")

        # Print failed/error tests
        if failed > 0 or errors > 0:
            print("FAILURES AND ERRORS:")
            print("-" * 70)
            for result in self.results:
                if result.status in [TestStatus.FAIL, TestStatus.ERROR]:
                    print(f"✗ {result.test_name}")
                    if result.message:
                        print(f"  {result.message}")
            print()

    def export_results(self, output_file: Path) -> None:
        """Export test results to JSON file."""
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "environments": [e.name for e in self.environments],
            "results": [
                {
                    "test_name": r.test_name,
                    "status": r.status.value,
                    "duration_ms": r.duration_ms,
                    "message": r.message,
                    "error": str(r.error) if r.error else None,
                    "details": r.details,
                }
                for r in self.results
            ],
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(output, indent=2))
        print(f"Results exported to: {output_file}")


# Convenience decorator for registering tests
def test(suite_name: str):
    """
    Decorator to register a test function.

    Usage:
        @test("topology")
        async def test_get_network_topology(settings, env):
            # Test implementation
            return {"status": "PASS", "message": "All nodes retrieved"}
    """

    def decorator(func):
        func._test_suite = suite_name
        return func

    return decorator
