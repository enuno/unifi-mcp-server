"""The configured audit log path must win over the memoized default.

``get_audit_logger`` memoizes one logger for the process. Whoever calls it
first decides the file, and a caller that passes no path gets the relative
``audit.log`` fallback. In a container the working directory is typically a
read-only root filesystem, so that fallback cannot be written: every audit
record fails with ``[Errno 30] Read-only file system``.

A fleet deployment survives this because ``src/fleet/db/audit_store.install``
replaces the file with a Postgres sink. A file-based (non-fleet) deployment
has no such escape, so a no-argument first call silently discards the
operator's configured path and loses the audit trail.
"""

import json
import threading
from pathlib import Path

import pytest

import src.utils.audit as audit_module


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Give each test a clean process-global logger."""
    audit_module._audit_logger = None
    yield
    audit_module._audit_logger = None


def test_a_configured_path_replaces_the_memoized_default(tmp_path: Path) -> None:
    """A later call carrying the configured path must retarget the logger."""
    # main.py reaches get_audit_logger() with no argument before the
    # settings-aware call in audit_store.install.
    first = audit_module.get_audit_logger()
    assert first.log_file == Path("audit.log")

    configured = tmp_path / "logs" / "audit.log"
    second = audit_module.get_audit_logger(configured)

    assert second.log_file == configured, (
        "the configured audit path was discarded; records would go to the "
        "read-only working directory"
    )


def test_retargeting_keeps_the_same_logger_and_its_wiring(tmp_path: Path) -> None:
    """Retargeting must not rebuild the logger.

    ``main.py`` assigns ``.forwarder`` and ``audit_store.install`` assigns
    ``.sink`` on the instance it gets back. Replacing the object on a later
    call would silently drop the SIEM forwarder and the Postgres sink.
    """
    first = audit_module.get_audit_logger()
    sentinel_sink = object()
    sentinel_forwarder = object()
    first.sink = sentinel_sink
    first.forwarder = sentinel_forwarder

    second = audit_module.get_audit_logger(tmp_path / "audit.log")

    assert second is first, "the audit logger must stay a singleton"
    assert second.sink is sentinel_sink, "retargeting dropped the Postgres sink"
    assert second.forwarder is sentinel_forwarder, "retargeting dropped the SIEM forwarder"


def test_a_retargeted_logger_can_actually_be_written(tmp_path: Path) -> None:
    """The retargeted path must exist and accept a record."""
    audit_module.get_audit_logger()
    configured = tmp_path / "nested" / "audit.log"

    logger = audit_module.get_audit_logger(configured)
    logger.log_operation(
        operation="test_operation",
        parameters={"site_id": "default"},
        result="success",
    )

    assert configured.exists(), "the configured audit file was never created"
    assert "test_operation" in configured.read_text()


def test_omitting_the_path_keeps_the_configured_one(tmp_path: Path) -> None:
    """A later no-argument call must not undo the configured path."""
    configured = tmp_path / "audit.log"
    audit_module.get_audit_logger(configured)

    assert audit_module.get_audit_logger().log_file == configured


def test_a_direct_construction_still_defaults() -> None:
    """Constructing AuditLogger directly keeps its documented default."""
    assert audit_module.AuditLogger().log_file == Path("audit.log")


def test_concurrent_first_callers_get_one_logger(tmp_path: Path) -> None:
    """A racing first call must not build a second instance.

    Two concurrent first callers each constructing a logger would leave the
    loser's ``sink`` and ``forwarder`` assignments on a discarded object.
    """
    seen: list[audit_module.AuditLogger] = []
    start = threading.Barrier(8)

    def grab() -> None:
        start.wait()
        seen.append(audit_module.get_audit_logger(tmp_path / "audit.log"))

    threads = [threading.Thread(target=grab) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len({id(logger) for logger in seen}) == 1, "more than one audit logger was built"


def test_retargeting_under_concurrent_writes_keeps_the_chain_intact(tmp_path: Path) -> None:
    """A retarget must not split the hash chain of an in-flight write.

    ``_write`` resolves the chain key from ``self.log_file`` and then opens
    ``self.log_file``, both under ``_chain_lock``. A retarget that does not
    take that lock can land between the two, sealing a record against the
    old file's chain and appending it to the new file.
    """
    first = tmp_path / "first" / "audit.log"
    second = tmp_path / "second" / "audit.log"
    logger = audit_module.get_audit_logger(first)

    stop = threading.Event()

    def write_records() -> None:
        while not stop.is_set():
            logger.log_operation(
                operation="concurrent_write",
                parameters={"site_id": "default"},
                result="success",
            )

    writers = [threading.Thread(target=write_records) for _ in range(4)]
    for writer in writers:
        writer.start()
    try:
        for _ in range(40):
            logger.retarget(second)
            logger.retarget(first)
    finally:
        stop.set()
        for writer in writers:
            writer.join()

    # Every record must carry the seq and prev_hash of the file it landed in.
    for path in (first, second):
        if not path.exists():
            continue
        previous: dict | None = None
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if previous is not None:
                assert record["seq"] == previous["seq"] + 1, (
                    f"hash chain split in {path.parent.name}: seq jumped "
                    f"from {previous['seq']} to {record['seq']}"
                )
                assert record["prev_hash"] == previous["hash"], (
                    f"hash chain split in {path.parent.name}: prev_hash "
                    "does not match the preceding record"
                )
            previous = record
