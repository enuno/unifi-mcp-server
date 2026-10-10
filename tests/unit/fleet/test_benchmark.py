"""Phase 3 targets on a simulated fleet (scripts/benchmark_fleet.py at small scale).

Request counts are deterministic; latency is not asserted (the fakeredis server
shares the test process, so cache latency here is not representative).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("fakeredis")

_spec = importlib.util.spec_from_file_location(
    "benchmark_fleet", Path(__file__).parents[3] / "scripts" / "benchmark_fleet.py"
)
benchmark = importlib.util.module_from_spec(_spec)
sys.modules["benchmark_fleet"] = benchmark  # dataclasses look the module up
_spec.loader.exec_module(benchmark)

CONTROLLERS, REPEATS = 40, 5


@pytest.fixture(scope="module")
def results():
    import asyncio

    return asyncio.run(benchmark.run_all(CONTROLLERS, REPEATS, latency=0.001, concurrency=20))


def test_baseline_probes_on_every_call(results):
    baseline = results["baseline"]

    assert baseline.probes == baseline.calls == CONTROLLERS * REPEATS


def test_pool_probes_once_per_controller(results):
    assert results["pool"].probes == CONTROLLERS
    assert results["pool"].requests == CONTROLLERS * REPEATS + CONTROLLERS


def test_cache_saves_at_least_80_percent_of_controller_requests(results):
    saved = 1 - results["pool+cache"].requests / results["baseline"].requests

    assert saved >= 0.80


async def test_a_pool_smaller_than_the_fleet_still_probes_once_per_controller():
    result = await benchmark.run_mode(
        "pool", controllers=CONTROLLERS, repeats=3, latency=0.001, concurrency=20, max_open=8
    )

    assert result.probes == CONTROLLERS
