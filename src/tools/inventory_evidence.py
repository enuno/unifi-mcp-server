"""Bounded, read-only inventory and explicit topology evidence (EV-03)."""

import asyncio
from datetime import UTC, datetime
from typing import Any

from src.api.client import UniFiClient
from src.config import APIType, Settings
from src.models.evidence import (
    ClientEvidence,
    DeviceEvidence,
    EvidenceRelationship,
    EvidenceScope,
    EvidenceSection,
    InventoryData,
    InventoryEvidence,
)
from src.utils.exceptions import (
    APIError,
    AuthenticationError,
    ResourceNotFoundError,
    ValidationError,
)
from src.utils.tool_kind import read_tool
from src.utils.validators import validate_path_segment, validate_site_id


def _row_id(row: dict[str, Any]) -> str | None:
    """Use the Integration API id or its documented legacy alias."""
    value = row.get("id") or row.get("_id")
    return value if isinstance(value, str) and value else None


async def _collect_section(
    client: UniFiClient, endpoint: str, *, max_records: int, max_pages: int
) -> tuple[list[dict[str, Any]], EvidenceSection]:
    """Read at most max_pages of a single Integration API collection."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pages = 0
    for page in range(max_pages):
        try:
            response = await client.get(
                f"{endpoint}?offset={page * max_records}&limit={max_records}"
            )
        except AuthenticationError:
            raise
        except ResourceNotFoundError:
            return rows, EvidenceSection(
                status="unavailable", count=len(rows), pages=pages, truncated=bool(rows)
            )
        except NotImplementedError:
            return rows, EvidenceSection(
                status="unsupported", count=len(rows), pages=pages, truncated=bool(rows)
            )
        except Exception:
            return rows, EvidenceSection(
                status="partial" if rows else "failed",
                count=len(rows),
                pages=pages,
                truncated=bool(rows),
                reason="collection_error",
            )
        data = (
            response
            if isinstance(response, list)
            else response.get("data") if isinstance(response, dict) else None
        )
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            return rows, EvidenceSection(
                status="partial" if rows else "failed",
                count=len(rows),
                pages=pages,
                truncated=bool(rows),
                reason="invalid_response",
            )
        pages += 1
        if not data:
            break
        # A controller that ignores pagination must not silently repeat rows or
        # be declared complete. No raw payload is ever returned or logged.
        selected = data[:max_records]
        # Real device lists can omit id. Preserve the rows but stop paging:
        # without IDs a controller ignoring offsets cannot be detected.
        if any(_row_id(row) is None for row in selected):
            rows.extend(selected)
            return rows, EvidenceSection(
                status="partial",
                count=len(rows),
                pages=pages,
                truncated=len(data) >= max_records,
                reason="missing_identity",
            )
        ids = [_row_id(row) for row in selected]
        if any(not value or value in seen for value in ids) or len(set(ids)) != len(ids):
            return rows, EvidenceSection(
                status="partial",
                count=len(rows),
                pages=pages,
                truncated=True,
                reason="repeated_page",
            )
        rows.extend(selected)
        seen.update(value for value in ids if value is not None)
        if len(data) < max_records:
            break
        if len(data) > max_records or page == max_pages - 1:
            return rows, EvidenceSection(
                status="partial", count=len(rows), pages=pages, truncated=True, reason="page_limit"
            )
    return rows, EvidenceSection(status="ok" if rows else "empty", count=len(rows), pages=pages)


@read_tool
async def collect_inventory_topology(
    site_id: str,
    settings: Settings,
    max_records: int = 50,
    max_pages: int = 2,
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    """Collect bounded, minimized inventory and explicit uplink evidence.

    Only a single environment-backed local controller is supported. The tool
    performs two Integration API reads concurrently, with a capped page size,
    page count and cooperative deadline (cleanup may extend elapsed time).
    It does not enrich every device, infer
    missing links, perform scans or write controller state. A full-page final
    response remains conservatively marked truncated, even if it was exact.

    Args:
        site_id: Site name or UUID, resolved on the configured controller
        settings: Controller-bound settings supplied by the tool router
        max_records: Records per page and section (1–100)
        max_pages: Maximum pages per section (1–5)
        timeout_seconds: Cooperative collection budget (1–30 seconds)

    Returns:
        Schema-v1 evidence dict with per-section status and allowlisted data
    """
    site_id = validate_site_id(site_id)
    if settings.api_type != APIType.LOCAL or settings.database_url or settings.mixed_mode:
        raise ValidationError(
            "Inventory evidence requires a single environment-backed local controller"
        )
    if (
        not isinstance(max_records, int)
        or isinstance(max_records, bool)
        or not 1 <= max_records <= 100
    ):
        raise ValidationError("max_records must be between 1 and 100")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or not 1 <= max_pages <= 5:
        raise ValidationError("max_pages must be between 1 and 5")
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= 30
    ):
        raise ValidationError("timeout_seconds must be between 1 and 30")

    started = datetime.now(UTC)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    async with UniFiClient(settings) as client:
        try:
            async with asyncio.timeout_at(deadline):
                await client.authenticate()
                resolved = validate_site_id(await client.resolve_site_id(site_id))
        except TimeoutError:
            raise APIError("Inventory evidence collection deadline exceeded") from None
        tasks = {
            section: asyncio.create_task(
                _collect_section(
                    client,
                    settings.get_integration_path(f"sites/{resolved}/{section}"),
                    max_records=max_records,
                    max_pages=max_pages,
                )
            )
            for section in ("devices", "clients")
        }
        try:
            done, pending = await asyncio.wait(
                tasks.values(), timeout=max(0, deadline - loop.time())
            )
            for task in pending:
                task.cancel()
            if pending:
                cancel_started = loop.time()
                await asyncio.gather(*pending, return_exceptions=True)
                if loop.time() - cancel_started > min(0.25, timeout_seconds * 0.1):
                    raise APIError(
                        "Inventory evidence collection deadline exceeded during cancellation"
                    )
            # Never return a partial response after a systemic authorization error.
            for task in done:
                if not task.cancelled() and isinstance(task.exception(), AuthenticationError):
                    raise AuthenticationError("Inventory evidence access denied") from None
            results: dict[str, tuple[list[dict[str, Any]], EvidenceSection]] = {}
            for section, task in tasks.items():
                if task in done:
                    results[section] = task.result()
                else:
                    results[section] = (
                        [],
                        EvidenceSection(status="failed", count=0, pages=0, reason="timeout"),
                    )
        finally:
            # Parent cancellation must not leave controller reads running.
            for task in tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)

    device_rows, device_section = results["devices"]
    client_rows, client_section = results["clients"]
    devices: list[DeviceEvidence] = []
    clients: list[ClientEvidence] = []
    links: list[EvidenceRelationship] = []
    warnings: list[str] = ["non_atomic_collection"]
    # API ids can be MAC addresses on some surfaces. Keep raw IDs only in this
    # collection's transient join map; never serialize them in the envelope.
    device_refs: dict[str, str] = {}
    for row in device_rows:
        raw_id = _row_id(row)
        if raw_id is None:
            device_section.status = "partial"
            device_section.reason = "missing_identity"
            state = row.get("state")
            devices.append(
                DeviceEvidence(
                    id=f"device:{len(devices) + 1}",
                    state=state if state in ("ONLINE", "OFFLINE") else "UNKNOWN",
                )
            )
            continue
        try:
            device_id = validate_path_segment(raw_id, "device ID")
            if device_id != raw_id:
                raise ValidationError("Device ID changed during validation")
        except (KeyError, ValidationError):
            device_section.status = "partial"
            device_section.reason = "invalid_response"
            continue
        if device_id in device_refs:
            device_section.status = "partial"
            device_section.reason = "invalid_response"
            continue
        state = row.get("state")
        ref = f"device:{len(devices) + 1}"
        devices.append(
            DeviceEvidence(id=ref, state=state if state in ("ONLINE", "OFFLINE") else "UNKNOWN")
        )
        device_refs[device_id] = ref
    for row in client_rows:
        ref = f"client:{len(clients) + 1}"
        clients.append(ClientEvidence(ref=ref))
        uplink = row.get("uplinkDeviceId")
        if isinstance(uplink, str):
            if uplink in device_refs:
                links.append(EvidenceRelationship(source=ref, target=device_refs[uplink]))
            elif "unresolved_uplink" not in warnings:
                warnings.append("unresolved_uplink")
    for row in device_rows:
        uplink = row.get("uplink")
        target = uplink.get("deviceId") if isinstance(uplink, dict) else None
        source = _row_id(row)
        if isinstance(source, str) and isinstance(target, str):
            if source in device_refs and target in device_refs:
                links.append(
                    EvidenceRelationship(source=device_refs[source], target=device_refs[target])
                )
            elif "unresolved_uplink" not in warnings:
                warnings.append("unresolved_uplink")

    device_section.count = len(devices)
    client_section.count = len(clients)
    sections = {"devices": device_section, "clients": client_section}
    complete = all(s.status in ("ok", "empty") and not s.truncated for s in sections.values())
    envelope = InventoryEvidence(
        scope=EvidenceScope(site_id=resolved),
        collection_started_at=started,
        collection_completed_at=datetime.now(UTC),
        completeness="complete" if complete else "partial",
        sections=sections,
        data=InventoryData(devices=devices, clients=clients),
        relationships=links,
        warnings=warnings,
    )
    return envelope.model_dump(mode="json")
