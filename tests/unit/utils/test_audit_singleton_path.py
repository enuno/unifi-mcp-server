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

from pathlib import Path

import pytest

import src.utils.audit as audit_module
from src.utils.audit import AuditLogger, get_audit_logger


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
    first = get_audit_logger()
    assert first.log_file == Path("audit.log")

    configured = tmp_path / "logs" / "audit.log"
    second = get_audit_logger(configured)

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
    first = get_audit_logger()
    sentinel_sink = object()
    sentinel_forwarder = object()
    first.sink = sentinel_sink
    first.forwarder = sentinel_forwarder

    second = get_audit_logger(tmp_path / "audit.log")

    assert second is first, "the audit logger must stay a singleton"
    assert second.sink is sentinel_sink, "retargeting dropped the Postgres sink"
    assert second.forwarder is sentinel_forwarder, "retargeting dropped the SIEM forwarder"


def test_a_retargeted_logger_can_actually_be_written(tmp_path: Path) -> None:
    """The retargeted path must exist and accept a record."""
    get_audit_logger()
    configured = tmp_path / "nested" / "audit.log"

    logger = get_audit_logger(configured)
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
    get_audit_logger(configured)

    assert get_audit_logger().log_file == configured


def test_a_direct_construction_still_defaults(tmp_path: Path) -> None:
    """Constructing AuditLogger directly keeps its documented default."""
    assert AuditLogger().log_file == Path("audit.log")
