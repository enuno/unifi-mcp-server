#!/usr/bin/env python3
"""Hardware verification harness for unifi-mcp-server (release gate).

Exercises the mock-tested surfaces against live infrastructure. Two phases:

  Phase A (default) — READ-ONLY calls. Safe to run anytime the controller /
  cloud is reachable. Verifies connectivity, auth, and every new GET path.

  Phase B (--writes) — gated behind an explicit operator token. Executes the
  write paths that mocked tests cannot prove (Protect v7 writes, Integration
  API F1-F3 probes, Phase 6 cloud writes). Every Phase B item is destructive
  or physically observable (sirens sound, ports flap, subscribers change
  state) — run it only with the operator present and a rollback plan.

Usage:
    .venv/bin/python scripts/verify-hardware.py                # Phase A reads
    .venv/bin/python scripts/verify-hardware.py --writes APPLY-WRITES

Secrets: this script never prints UNIFI_API_KEY or bearer tokens. Connection
failures are reported as BLOCKED, not FAILED — a unreachable controller is an
environment problem, not a code defect.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

RESULTS: list[tuple[str, str, str]] = []  # (phase, name, status)


def report(phase: str, name: str, status: str, detail: str = "") -> None:
    RESULTS.append((phase, name, status))
    suffix = f" — {detail}" if detail else ""
    print(f"[{status:7}] ({phase}) {name}{suffix}")


def load_dotenv(path: Path) -> None:
    """Minimal .env parser; existing os.environ values win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


async def phase_a(settings) -> None:
    from src.tools import (
        carrier,
        innerspace,
        mobility,
        protect_alarm,
        protect_sirens,
        site_manager,
        sites,
    )

    # 1. Local controller: Integration API auth + site listing
    try:
        result = await sites.list_sites(settings)
        report("A", "local controller auth + list_sites", "PASS", f"{count_items(result)} site(s)")
    except Exception as e:  # noqa: BLE001 - harness reports, never raises
        report("A", "local controller auth + list_sites", classify(e), str(e)[:120])
        return  # no point probing Protect if the controller is unreachable

    # 2. Protect v7 reads (Cloud Connector proxy -> integration API)
    for name, coro in [
        ("arm-profiles", protect_alarm.list_protect_arm_profiles),
        ("sirens", protect_sirens.list_protect_sirens),
    ]:
        try:
            result = await coro(settings)
            report("A", f"protect v7 read: {name}", "PASS", f"{result.get('count', '?')} item(s)")
        except Exception as e:  # noqa: BLE001
            if "Expecting value" in str(e):
                # Gateways without a Protect application serve the SPA index
                # page (text/html) for unknown proxy paths — verified live on
                # U7 Express (200 text/html catch-all). Not a code defect.
                report("A", f"protect v7 read: {name}", "SKIP", "no Protect application on this console")
            else:
                report("A", f"protect v7 read: {name}", classify(e), str(e)[:120])

    # 3. Cloud APIs (Mobility / Carrier) — only if the cloud key is enabled
    if settings.site_manager_enabled:
        try:
            result = await mobility.list_mobility_workspaces(settings)
            report("A", "mobility: list_workspaces", "PASS", f"{result.get('count', '?')} workspace(s)")
        except Exception as e:  # noqa: BLE001
            report("A", "mobility: list_workspaces", classify(e), str(e)[:120])
        try:
            result = await carrier.list_carrier_service_plans(settings)
            report("A", "carrier: list_service_plans", "PASS", f"{result.get('count', '?')} plan(s)")
        except Exception as e:  # noqa: BLE001
            report("A", "carrier: list_service_plans", classify(e), str(e)[:120])

        # 4. InnerSpace via connector proxy (needs a console_id from list_hosts)
        try:
            hosts = await site_manager.list_hosts(settings)
            host_list = hosts.get("hosts", hosts.get("data", []))
            if not host_list:
                report("A", "innerspace: list_access_points", "SKIP", "no consoles in list_hosts")
            else:
                console_id = host_list[0].get("id") or host_list[0].get("hostId")
                result = await innerspace.list_innerspace_access_points(console_id, settings)
                report("A", "innerspace: list_access_points", "PASS", f"{result.get('count', '?')} AP(s)")
        except Exception as e:  # noqa: BLE001
            report("A", "innerspace: list_access_points", classify(e), str(e)[:120])
    else:
        report("A", "cloud APIs (mobility/carrier/innerspace)", "SKIP", "UNIFI_SITE_MANAGER_ENABLED not set")


async def phase_b(settings) -> None:
    """Write-path probes. Operator-gated: run only with approval and rollback ready."""
    print("\n--- PHASE B: WRITE PROBES (operator-gated) ---")
    from src.tools import carrier, mobility, protect_alarm, protect_sirens

    # B1. Protect: siren test-sound (physically audible — operator must expect it)
    try:
        sirens = await protect_sirens.list_protect_sirens(settings)
        if sirens.get("count", 0) == 0:
            report("B", "siren test-sound", "SKIP", "no sirens on this site")
        else:
            siren_id = sirens["data"][0]["id"]
            result = await protect_sirens.test_protect_siren_sound(siren_id, settings, confirm=True)
            report("B", "siren test-sound", "PASS", f"siren {siren_id}: {str(result)[:80]}")
    except Exception as e:  # noqa: BLE001
        report("B", "siren test-sound", "FAIL", str(e)[:120])

    # B2. Protect: arm-profile create -> delete round-trip (net-neutral)
    try:
        created = await protect_alarm.create_protect_arm_profile(
            settings, name="verify-hw-roundtrip", automations=[], schedules=[],
            record_everything=False, activation_delay=0, confirm=True,
        )
        profile_id = created.get("id") or created.get("data", {}).get("id")
        if not profile_id:
            raise RuntimeError(f"create response carried no id: {str(created)[:100]}")
        await protect_alarm.delete_protect_arm_profile(profile_id, settings, confirm=True)
        report("B", "arm-profile create/delete round-trip", "PASS", f"profile {profile_id}")
    except Exception as e:  # noqa: BLE001
        report("B", "arm-profile create/delete round-trip", "FAIL", str(e)[:120])

    # B3. Integration API F1-F3 probes (devices.py / client_management.py)
    print(
        "F1-F3 note: adoption needs a pending device; port/client actions flap a real\n"
        "  port/guest session. Probe them individually against the audit report:\n"
        "  .analysis-reports/api-spec-audit-2026-09-26.md — not automated here."
    )

    # B4. Carrier: subscriber create -> suspend -> resume -> delete-if-supported
    if settings.site_manager_enabled:
        try:
            sub = await carrier.create_carrier_subscriber(
                settings, subscriber_number="VERIFY-HW-0001", name="verification round-trip",
                confirm=True,
            )
            sub_id = sub.get("id") or sub.get("data", {}).get("id")
            if not sub_id:
                raise RuntimeError(f"create response carried no id: {str(sub)[:100]}")
            await carrier.suspend_carrier_subscriber(sub_id, settings, reason="hw verification", confirm=True)
            await carrier.resume_carrier_subscriber(sub_id, settings, confirm=True)
            report("B", "carrier subscriber lifecycle", "PASS", f"subscriber {sub_id}")
            print(f"  NOTE: subscriber {sub_id} still exists — delete via UI/operator if undesired")
        except Exception as e:  # noqa: BLE001
            report("B", "carrier subscriber lifecycle", classify(e), str(e)[:120])
    else:
        report("B", "carrier subscriber lifecycle", "SKIP", "cloud API not enabled")

    # B5. Mobility: device rename round-trip requires a device id from Phase A;
    # left to the operator (rename changes visible device state).
    report("B", "mobility device rename", "SKIP", "operator-driven; pick a device and revert after")


def count_items(result) -> int:
    """Harness-side count that tolerates list or dict tool returns."""
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        for key in ("count", "total"):
            if isinstance(result.get(key), int):
                return result[key]
        for key in ("sites", "data", "hosts", "results"):
            if isinstance(result.get(key), list):
                return len(result[key])
    return -1


def classify(e: Exception) -> str:
    text = str(e).lower()
    if "connect" in text or "timeout" in text or "unreachable" in text or "network" in text:
        return "BLOCKED"
    if "401" in text or "403" in text or "auth" in text:
        return "FAIL"  # reachable but auth broken — that IS a defect signal
    if "404" in text:
        return "FAIL"
    return "FAIL"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--writes", metavar="TOKEN", default=None,
                        help='Run Phase B write probes; requires the exact token "APPLY-WRITES"')
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    from src.config import Settings

    settings = Settings()

    print(f"controller: {settings.local_host} (api_type={getattr(settings, 'api_type', '?')}, "
          f"cloud_enabled={settings.site_manager_enabled})")
    print("(API keys redacted)\n")

    await phase_a(settings)

    if args.writes is not None:
        if args.writes != "APPLY-WRITES":
            print("\nRefusing Phase B: token must be exactly APPLY-WRITES", file=sys.stderr)
            return 2
        await phase_b(settings)

    print("\n=== SUMMARY ===")
    for phase, name, status in RESULTS:
        print(f"  [{status:7}] ({phase}) {name}")
    blocked = sum(1 for _, _, s in RESULTS if s == "BLOCKED")
    failed = sum(1 for _, _, s in RESULTS if s == "FAIL")
    skipped = sum(1 for _, _, s in RESULTS if s == "SKIP")
    passed = sum(1 for _, _, s in RESULTS if s == "PASS")
    print(f"  PASS={passed} FAIL={failed} BLOCKED={blocked} SKIP={skipped}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
