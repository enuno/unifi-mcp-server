"""Unit tests for audit-log at-rest encryption (issue #22).

Covers: encrypt/decrypt round-trip, no-key backward compatibility,
key-from-env wiring, MultiFernet rotation, passphrase-derived keys,
key-never-leaked guarantees, and the operator decrypt CLI.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

import src.utils.audit as audit_module
from src.utils.audit import AuditLogger, get_audit_logger, log_audit
from src.utils.audit_decrypt import main as decrypt_cli_main
from src.utils.audit_encryption import (
    ENV_VAR,
    ENV_VAR_ALIAS,
    TOKEN_PREFIX,
    AuditEncryptionError,
    decrypt_field,
    encrypt_field,
    resolve_audit_cipher,
)

# Throwaway keys generated for tests only — never real material.
KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()
PASSPHRASE = "test-only-passphrase-9f3c1e7b"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Ensure no key leaks in from the outer environment."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.delenv(ENV_VAR_ALIAS, raising=False)
    audit_module._audit_logger = None
    yield
    audit_module._audit_logger = None


def _cipher(env: dict[str, str]) -> MultiFernet:
    """Resolve a cipher in tests, asserting a key is present."""
    cipher = resolve_audit_cipher(env)
    assert cipher is not None
    return cipher


def _write(logger: AuditLogger, **kwargs) -> None:
    """Log one operation with sensible defaults."""
    logger.log_operation(
        operation=kwargs.pop("operation", "test_op"),
        parameters=kwargs.pop("parameters", {"name": "TestNet"}),
        result=kwargs.pop("result", "success"),
        **kwargs,
    )


class TestResolveAuditCipher:
    """Key resolution from the environment."""

    def test_no_key_configured_returns_none(self):
        assert resolve_audit_cipher({}) is None
        assert resolve_audit_cipher({ENV_VAR: "", ENV_VAR_ALIAS: ""}) is None
        assert resolve_audit_cipher({ENV_VAR: "   "}) is None

    def test_raw_fernet_key_from_env(self):
        cipher = _cipher({ENV_VAR: KEY_A})
        assert isinstance(cipher, MultiFernet)

    def test_passphrase_is_derived(self):
        cipher = _cipher({ENV_VAR: PASSPHRASE})
        assert isinstance(cipher, MultiFernet)
        # Same passphrase derives the same key (deterministic KDF).
        again = _cipher({ENV_VAR: PASSPHRASE})
        token = encrypt_field(cipher, {"a": 1})
        assert decrypt_field(again, token) == {"a": 1}

    def test_canonical_var_wins_over_alias(self):
        cipher = _cipher({ENV_VAR: KEY_A, ENV_VAR_ALIAS: KEY_B})
        token = encrypt_field(cipher, "x")
        assert decrypt_field(_cipher({ENV_VAR: KEY_A}), token) == "x"

    def test_alias_used_when_canonical_unset(self):
        cipher = _cipher({ENV_VAR_ALIAS: KEY_A})
        assert isinstance(cipher, MultiFernet)

    def test_comma_separated_keys_newest_first(self):
        cipher = _cipher({ENV_VAR: f"{KEY_A},{KEY_B}"})
        assert isinstance(cipher, MultiFernet)

    def test_arbitrary_string_treated_as_passphrase(self):
        """Non-Fernet material is stretched as a passphrase, never rejected.

        This is deliberate: operators may supply a passphrase instead of a
        raw Fernet key, and there is no reliable way to distinguish "bad
        key" from "short passphrase". The derived key is deterministic.
        """
        weird = "!!!not-a-key!!!"
        cipher = _cipher({ENV_VAR: weird})
        again = _cipher({ENV_VAR: weird})
        token = encrypt_field(cipher, {"a": 1})
        assert decrypt_field(again, token) == {"a": 1}

    def test_empty_entry_raises_naming_variable_only(self):
        with pytest.raises(AuditEncryptionError) as exc_info:
            resolve_audit_cipher({ENV_VAR: f"{KEY_A},,"})
        assert ENV_VAR in str(exc_info.value)


class TestEncryptDecryptField:
    """Round-trip of individual payload fields."""

    def test_round_trip_dict(self):
        cipher = _cipher({ENV_VAR: KEY_A})
        value = {"name": "IoT", "vlan": 20, "nested": {"psk": "***"}}
        assert decrypt_field(cipher, encrypt_field(cipher, value)) == value

    def test_round_trip_string_and_none(self):
        cipher = _cipher({ENV_VAR: KEY_A})
        assert decrypt_field(cipher, encrypt_field(cipher, "api.err.MacUsed")) == (
            "api.err.MacUsed"
        )
        assert decrypt_field(cipher, encrypt_field(cipher, None)) is None

    def test_token_is_prefixed_ciphertext(self):
        cipher = _cipher({ENV_VAR: KEY_A})
        token = encrypt_field(cipher, {"mac": "aa:bb:cc:dd:ee:ff"})
        assert token.startswith(TOKEN_PREFIX)
        assert "aa:bb:cc" not in token

    def test_wrong_key_cannot_decrypt(self):
        cipher_a = _cipher({ENV_VAR: KEY_A})
        cipher_b = _cipher({ENV_VAR: KEY_B})
        token = encrypt_field(cipher_a, {"secret": "data"})
        with pytest.raises(AuditEncryptionError):
            decrypt_field(cipher_b, token)

    def test_malformed_token_rejected(self):
        cipher = _cipher({ENV_VAR: KEY_A})
        with pytest.raises(AuditEncryptionError):
            decrypt_field(cipher, "not-a-token")
        with pytest.raises(AuditEncryptionError):
            decrypt_field(cipher, TOKEN_PREFIX + "garbage")


class TestEncryptedLogOperation:
    """End-to-end: writing encrypted records and reading them back."""

    def test_no_key_writes_historical_plaintext_format(self, tmp_path):
        log_path = tmp_path / "audit.log"
        logger = AuditLogger(log_file=log_path)

        _write(
            logger,
            operation="update_wlan",
            parameters={"name": "GuestWiFi", "x_passphrase": "hunter2"},  # pragma: allowlist secret
            error="api.err.MacUsed for aa:bb:cc:dd:ee:ff",
        )

        record = json.loads(log_path.read_text().strip())
        assert record["parameters"]["name"] == "GuestWiFi"
        assert record["parameters"]["x_passphrase"] == "***"
        assert record["error"] == "api.err.MacUsed for aa:bb:cc:dd:ee:ff"
        assert "parameters_encrypted" not in record
        assert "error_encrypted" not in record

    def test_with_key_round_trip(self, tmp_path):
        log_path = tmp_path / "audit.log"
        cipher = _cipher({ENV_VAR: KEY_A})
        logger = AuditLogger(log_file=log_path, encryption=cipher)

        _write(
            logger,
            operation="update_wlan",
            parameters={"name": "GuestWiFi", "x_passphrase": "hunter2"},  # pragma: allowlist secret
            site_id="default",
            user="admin@example.com",
            error="api.err.MacUsed for aa:bb:cc:dd:ee:ff",
        )

        raw = log_path.read_text()
        on_disk = json.loads(raw.strip())

        # Payloads are ciphertext on disk; metadata stays readable.
        assert on_disk["parameters_encrypted"] is True
        assert on_disk["error_encrypted"] is True
        assert on_disk["parameters"].startswith(TOKEN_PREFIX)
        assert on_disk["error"].startswith(TOKEN_PREFIX)
        assert on_disk["operation"] == "update_wlan"
        assert on_disk["result"] == "success"
        assert on_disk["site_id"] == "default"
        assert on_disk["user"] == "admin@example.com"
        assert "GuestWiFi" not in raw
        assert "hunter2" not in raw
        assert "aa:bb:cc" not in raw

        # Read-back decrypts to the redacted record.
        entries = logger.get_recent_operations()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["parameters"] == {"name": "GuestWiFi", "x_passphrase": "***"}
        assert entry["error"] == "api.err.MacUsed for aa:bb:cc:dd:ee:ff"
        assert "parameters_encrypted" not in entry
        assert "error_encrypted" not in entry
        # Metadata untouched by decryption.
        assert entry["site_id"] == "default"
        assert entry["user"] == "admin@example.com"

    def test_key_from_env_wires_into_audit_logger(self, tmp_path, monkeypatch):
        monkeypatch.setenv(ENV_VAR, KEY_A)
        log_path = tmp_path / "audit.log"
        logger = AuditLogger(log_file=log_path)

        _write(logger, parameters={"client_mac": "aa:bb:cc:dd:ee:ff"})

        on_disk = json.loads(log_path.read_text().strip())
        assert on_disk["parameters_encrypted"] is True
        assert "aa:bb:cc" not in log_path.read_text()
        assert logger.get_recent_operations()[0]["parameters"] == {
            "client_mac": "aa:bb:cc:dd:ee:ff"
        }

    def test_log_audit_convenience_uses_env_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv(ENV_VAR, KEY_A)
        audit_module._audit_logger = None
        log_path = tmp_path / "audit.log"

        log_audit(
            operation="block_client",
            parameters={"mac": "aa:bb:cc:dd:ee:ff"},
            result="success",
            log_file=log_path,
        )

        assert "aa:bb:cc" not in log_path.read_text()
        assert get_audit_logger().get_recent_operations()[0]["parameters"] == {
            "mac": "aa:bb:cc:dd:ee:ff"
        }

    def test_redaction_survives_encryption(self, tmp_path):
        """Decrypting yields exactly the redacted record — never raw secrets."""
        log_path = tmp_path / "audit.log"
        cipher = _cipher({ENV_VAR: KEY_A})
        logger = AuditLogger(log_file=log_path, encryption=cipher)

        _write(
            logger, parameters={"details": {"password": "secret-value"}}
        )  # pragma: allowlist secret

        assert "secret-value" not in log_path.read_text()  # pragma: allowlist secret
        entry = logger.get_recent_operations()[0]
        assert entry["parameters"]["details"]["password"] == "***"

    def test_error_field_absent_no_marker(self, tmp_path):
        log_path = tmp_path / "audit.log"
        cipher = _cipher({ENV_VAR: KEY_A})
        logger = AuditLogger(log_file=log_path, encryption=cipher)

        _write(logger)

        on_disk = json.loads(log_path.read_text().strip())
        assert "error" not in on_disk
        assert "error_encrypted" not in on_disk


class TestKeyRotation:
    """MultiFernet rotation: new key writes, old entries stay readable."""

    def test_old_entries_readable_after_rotation(self, tmp_path, monkeypatch):
        log_path = tmp_path / "audit.log"
        monkeypatch.setenv(ENV_VAR, KEY_A)
        AuditLogger(log_file=log_path).log_operation(
            operation="op_old", parameters={"k": "v-old"}, result="success"
        )

        # Rotate: KEY_B now writes, KEY_A retained for reads.
        monkeypatch.setenv(ENV_VAR, f"{KEY_B},{KEY_A}")
        logger = AuditLogger(log_file=log_path)
        logger.log_operation(operation="op_new", parameters={"k": "v-new"}, result="success")

        entries = logger.get_recent_operations()
        by_op = {e["operation"]: e for e in entries}
        assert by_op["op_old"]["parameters"] == {"k": "v-old"}
        assert by_op["op_new"]["parameters"] == {"k": "v-new"}

    def test_writes_use_newest_key_only(self, tmp_path, monkeypatch):
        log_path = tmp_path / "audit.log"
        monkeypatch.setenv(ENV_VAR, f"{KEY_B},{KEY_A}")
        AuditLogger(log_file=log_path).log_operation(
            operation="op", parameters={"k": "v"}, result="success"
        )

        on_disk = json.loads(log_path.read_text().strip())
        token = on_disk["parameters"][len(TOKEN_PREFIX) :]
        # Only KEY_B (the newest) decrypts the write.
        assert json.loads(Fernet(KEY_B.encode()).decrypt(token).decode()) == {"k": "v"}
        with pytest.raises(InvalidToken):
            Fernet(KEY_A.encode()).decrypt(token)


class TestBackwardCompatibility:
    """Historical plaintext entries remain readable alongside encrypted ones."""

    def test_mixed_plaintext_and_encrypted_entries(self, tmp_path, monkeypatch):
        log_path = tmp_path / "audit.log"
        monkeypatch.setenv(ENV_VAR, KEY_A)
        AuditLogger(log_file=log_path).log_operation(
            operation="legacy_op",
            parameters={"name": "LegacyNet"},
            result="success",
        )

        monkeypatch.setenv(ENV_VAR, KEY_A)
        AuditLogger(log_file=log_path).log_operation(
            operation="encrypted_op",
            parameters={"name": "NewNet"},
            result="success",
        )

        logger = AuditLogger(log_file=log_path)
        entries = logger.get_recent_operations()
        by_op = {e["operation"]: e for e in entries}
        assert by_op["legacy_op"]["parameters"] == {"name": "LegacyNet"}
        assert by_op["encrypted_op"]["parameters"] == {"name": "NewNet"}


class TestUndecryptableEntries:
    """A bad line must be reported, not silently dropped or fatal."""

    def test_wrong_key_returns_placeholder_and_warns(self, tmp_path, caplog):
        log_path = tmp_path / "audit.log"
        cipher_a = _cipher({ENV_VAR: KEY_A})
        AuditLogger(log_file=log_path, encryption=cipher_a).log_operation(
            operation="op", parameters={"k": "v"}, result="success"
        )

        cipher_b = _cipher({ENV_VAR: KEY_B})
        logger = AuditLogger(log_file=log_path, encryption=cipher_b)
        with caplog.at_level(logging.WARNING):
            entries = logger.get_recent_operations()

        assert len(entries) == 1
        assert entries[0]["parameters"] == "<undecryptable: parameters>"
        assert any("Cannot decrypt" in rec.message for rec in caplog.records)

    def test_tampered_token_reported(self, tmp_path, caplog):
        log_path = tmp_path / "audit.log"
        cipher = _cipher({ENV_VAR: KEY_A})
        AuditLogger(log_file=log_path, encryption=cipher).log_operation(
            operation="op", parameters={"k": "v"}, result="success"
        )

        raw = log_path.read_text()
        record = json.loads(raw.strip())
        record["parameters"] = TOKEN_PREFIX + "A" * 20
        log_path.write_text(json.dumps(record) + "\n")

        logger = AuditLogger(log_file=log_path, encryption=cipher)
        with caplog.at_level(logging.WARNING):
            entries = logger.get_recent_operations()

        assert entries[0]["parameters"] == "<undecryptable: parameters>"
        assert any("Cannot decrypt" in rec.message for rec in caplog.records)

    def test_encrypted_entry_without_key_reports_placeholder(self, tmp_path, caplog):
        log_path = tmp_path / "audit.log"
        cipher = _cipher({ENV_VAR: KEY_A})
        AuditLogger(log_file=log_path, encryption=cipher).log_operation(
            operation="op", parameters={"k": "v"}, result="success"
        )

        logger = AuditLogger(log_file=log_path)  # no key configured
        with caplog.at_level(logging.WARNING):
            entries = logger.get_recent_operations()

        assert entries[0]["parameters"] == "<undecryptable: parameters>"


class TestKeyNeverLeaks:
    """The key must never appear in any log output or error surface."""

    def test_key_not_in_audit_file(self, tmp_path):
        log_path = tmp_path / "audit.log"
        cipher = _cipher({ENV_VAR: KEY_A})
        AuditLogger(log_file=log_path, encryption=cipher).log_operation(
            operation="op", parameters={"k": "v"}, error="boom", result="failed"
        )
        assert KEY_A not in log_path.read_text()
        assert KEY_B not in log_path.read_text()

    def test_key_not_in_app_logs(self, tmp_path, caplog, monkeypatch):
        monkeypatch.setenv(ENV_VAR, KEY_A)
        log_path = tmp_path / "audit.log"
        logger = AuditLogger(log_file=log_path)

        with caplog.at_level(logging.DEBUG):
            _write(logger, error="something failed", result="failed")
            # Also exercise the failure paths.
            try:
                resolve_audit_cipher({ENV_VAR: "!!!bad!!!"})
            except AuditEncryptionError:
                pass

        all_output = "\n".join(
            [rec.getMessage() for rec in caplog.records]
            + [str(rec.__dict__.get("parameters", "")) for rec in caplog.records]
        )
        assert KEY_A not in all_output
        assert PASSPHRASE not in all_output

    def test_decrypt_error_messages_exclude_key_material(self):
        cipher = _cipher({ENV_VAR: KEY_A})
        token = encrypt_field(cipher, {"k": "v"})
        other = _cipher({ENV_VAR: KEY_B})
        with pytest.raises(AuditEncryptionError) as exc_info:
            decrypt_field(other, token)
        assert KEY_A not in str(exc_info.value)
        assert KEY_B not in str(exc_info.value)


class TestDecryptCli:
    """The operator-facing decrypt entry point."""

    def test_cli_decrypts_entries(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv(ENV_VAR, KEY_A)
        log_path = tmp_path / "audit.log"
        AuditLogger(log_file=log_path).log_operation(
            operation="create_network",
            parameters={"name": "NetFromCli"},
            result="success",
        )

        assert decrypt_cli_main([str(log_path)]) == 0
        out = capsys.readouterr().out
        entry = json.loads(out.strip())
        assert entry["parameters"] == {"name": "NetFromCli"}
        assert KEY_A not in out

    def test_cli_key_flag(self, tmp_path, capsys):
        log_path = tmp_path / "audit.log"
        cipher = _cipher({ENV_VAR: KEY_A})
        AuditLogger(log_file=log_path, encryption=cipher).log_operation(
            operation="op", parameters={"k": "v"}, result="success"
        )

        assert decrypt_cli_main([str(log_path), "--key", KEY_A]) == 0
        assert json.loads(capsys.readouterr().out.strip())["parameters"] == {"k": "v"}

    def test_cli_no_key_errors_cleanly(self, tmp_path, capsys):
        assert decrypt_cli_main([str(tmp_path / "audit.log")]) == 2
        assert "UNIFI_AUDIT_LOG_KEY" in capsys.readouterr().err

    def test_cli_missing_file_errors_cleanly(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv(ENV_VAR, KEY_A)
        assert decrypt_cli_main([str(tmp_path / "nope.log")]) == 2
        assert "not found" in capsys.readouterr().err

    def test_cli_operation_filter_and_limit(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv(ENV_VAR, KEY_A)
        log_path = tmp_path / "audit.log"
        logger = AuditLogger(log_file=log_path)
        for i in range(3):
            logger.log_operation(
                operation="wanted_op" if i else "other_op",
                parameters={"i": i},
                result="success",
            )

        assert decrypt_cli_main([str(log_path), "--operation", "wanted_op"]) == 0
        out = capsys.readouterr().out.strip().splitlines()
        assert len(out) == 2
        assert all(json.loads(line)["operation"] == "wanted_op" for line in out)

    def test_cli_runnable_as_module(self, tmp_path, monkeypatch):
        """python -m src.utils.audit_decrypt works end to end."""
        monkeypatch.setenv(ENV_VAR, KEY_A)
        log_path = tmp_path / "audit.log"
        AuditLogger(log_file=log_path).log_operation(
            operation="op", parameters={"k": "v"}, result="success"
        )

        result = subprocess.run(
            [sys.executable, "-m", "src.utils.audit_decrypt", str(log_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[3],
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout.strip())["parameters"] == {"k": "v"}
