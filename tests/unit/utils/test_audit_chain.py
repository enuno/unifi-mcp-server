"""Audit hash chain and its verifier (docs/FLEET_SCALING_PLAN.md §3.7)."""

import json
from pathlib import Path

import pytest

from src.utils.audit import GENESIS_HASH, INSTANCE_ID, AuditLogger, record_hash
from src.utils.audit_verify import ChainKeyMissingError, main, verify_file

KEY = "chain-test-key"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _no_env_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIFI_AUDIT_CHAIN_KEY", raising=False)
    monkeypatch.delenv("UNIFI_AUDIT_LOG_KEY", raising=False)
    monkeypatch.delenv("UNIFI_AUDIT_ENCRYPTION_KEY", raising=False)


def _write(path: Path, count: int = 4) -> list[str]:
    logger = AuditLogger(log_file=path)
    for i in range(count):
        logger.log_operation(f"op_{i}", {"n": i}, "success")
    return path.read_text().splitlines()


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


class TestChaining:
    def test_records_form_a_chain(self, tmp_path: Path):
        path = tmp_path / "audit.log"
        _write(path, 3)

        records = _records(path)

        assert [r["seq"] for r in records] == [0, 1, 2]
        assert records[0]["prev_hash"] == GENESIS_HASH
        assert records[1]["prev_hash"] == records[0]["hash"]
        assert all(r["chain_id"] == INSTANCE_ID for r in records)
        assert all(r["hash"] == record_hash(r, None) for r in records)

    def test_hmac_when_key_configured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", KEY)
        path = tmp_path / "audit.log"
        _write(path, 1)

        record = _records(path)[0]

        assert record["hash_alg"] == "hmac-sha256"
        assert record["hash"] == record_hash(record, KEY.encode())
        assert record["hash"] != record_hash(record, None)

    def test_hash_covers_ciphertext_when_encrypted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from cryptography.fernet import Fernet

        monkeypatch.setenv("UNIFI_AUDIT_LOG_KEY", Fernet.generate_key().decode())
        path = tmp_path / "audit.log"
        _write(path, 2)

        # Verifiable without the payload key: the hash is over what is stored.
        monkeypatch.delenv("UNIFI_AUDIT_LOG_KEY")
        assert verify_file(path, None).ok
        assert _records(path)[0]["parameters_encrypted"] is True

    def test_failed_write_does_not_advance_the_chain(self, tmp_path: Path):
        path = tmp_path / "audit.log"
        logger = AuditLogger(log_file=path)
        logger.log_operation("first", {}, "success")
        path.chmod(0o400)
        try:
            logger.log_operation("lost", {}, "success")  # swallowed (non-strict)
        finally:
            path.chmod(0o600)
        logger.log_operation("second", {}, "success")

        assert [r["seq"] for r in _records(path)] == [0, 1]
        assert verify_file(path, None).ok


class TestVerify:
    def test_intact_file_verifies(self, tmp_path: Path):
        path = tmp_path / "audit.log"
        _write(path)

        report = verify_file(path, None)

        assert report.ok
        assert (report.records, report.chains, report.legacy) == (4, 1, 0)

    def test_edited_record_is_detected(self, tmp_path: Path):
        path = tmp_path / "audit.log"
        lines = _write(path)
        record = json.loads(lines[1])
        record["result"] = "failed"
        lines[1] = json.dumps(record)
        path.write_text("\n".join(lines) + "\n")

        report = verify_file(path, None)

        assert any("line 2: hash does not match" in p for p in report.problems)

    def test_deleted_record_is_detected(self, tmp_path: Path):
        path = tmp_path / "audit.log"
        lines = _write(path)
        del lines[1]
        path.write_text("\n".join(lines) + "\n")

        report = verify_file(path, None)

        assert any("expected seq 1, found 2" in p for p in report.problems)

    def test_reordered_records_are_detected(self, tmp_path: Path):
        path = tmp_path / "audit.log"
        lines = _write(path)
        lines[1], lines[2] = lines[2], lines[1]
        path.write_text("\n".join(lines) + "\n")

        assert not verify_file(path, None).ok

    def test_stripping_chain_fields_is_detected(self, tmp_path: Path):
        path = tmp_path / "audit.log"
        lines = _write(path)
        record = json.loads(lines[2])
        for name in ("chain_id", "seq", "prev_hash", "hash", "hash_alg"):
            record.pop(name)
        record["result"] = "failed"
        lines[2] = json.dumps(record)
        path.write_text("\n".join(lines) + "\n")

        report = verify_file(path, None)

        assert any("unchained record after chained ones" in p for p in report.problems)

    def test_recomputed_hash_fails_under_hmac(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Someone who can edit the file but lacks the key cannot re-seal it.
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", KEY)
        path = tmp_path / "audit.log"
        lines = _write(path)
        record = json.loads(lines[-1])
        record["result"] = "failed"
        record["hash"] = record_hash(record, b"attacker-guess")
        lines[-1] = json.dumps(record)
        path.write_text("\n".join(lines) + "\n")

        assert not verify_file(path, KEY.encode()).ok

    def test_hmac_chain_needs_the_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", KEY)
        path = tmp_path / "audit.log"
        _write(path, 1)

        with pytest.raises(ChainKeyMissingError):
            verify_file(path, None)

    def test_legacy_records_before_the_chain_are_accepted(self, tmp_path: Path):
        path = tmp_path / "audit.log"
        legacy = json.dumps({"timestamp": "t", "operation": "old", "result": "success"})
        path.write_text(legacy + "\n")
        _write(path, 2)

        report = verify_file(path, None)

        assert report.ok
        assert report.legacy == 1


class TestCli:
    def test_ok(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        path = tmp_path / "audit.log"
        _write(path, 2)

        assert main([str(path)]) == 0
        assert capsys.readouterr().out.startswith("OK: 2 record(s), 1 chain(s)")

    def test_tampered(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        path = tmp_path / "audit.log"
        lines = _write(path, 2)
        path.write_text(lines[1] + "\n")

        assert main([str(path)]) == 1
        assert "FAILED" in capsys.readouterr().out

    def test_missing_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", KEY)
        path = tmp_path / "audit.log"
        _write(path, 1)
        monkeypatch.delenv("UNIFI_AUDIT_CHAIN_KEY")

        assert main([str(path)]) == 2
        assert main([str(path), "--key", KEY]) == 0

    def test_missing_file(self, tmp_path: Path):
        assert main([str(tmp_path / "nope.log")]) == 2
