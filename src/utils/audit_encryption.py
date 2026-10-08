"""At-rest encryption for audit log records.

Issue #22 (CodeQL ``py/clear-text-storage-sensitive-data``): audit records
persist operation parameters and controller error text to disk in plaintext.
This module provides optional, operator-controlled Fernet (AES-128-CBC +
HMAC) encryption for the sensitive *payload* fields of a record while leaving
metadata (timestamp, operation, result) readable so logs stay filterable
without the key.

Design properties:

- **Opt-in and backward compatible.** With no key configured, nothing here
  activates and the on-disk format is byte-identical to the historical
  plaintext format.
- **Encryption complements redaction.** Callers must still run
  :func:`src.utils.sanitize.sanitize_credentials` first; this module
  encrypts the already-redacted payload, so a decrypt yields exactly the
  redacted record an operator would see today.
- **Rotation without data loss.** The key setting accepts a comma-separated
  list, newest first (``MultiFernet`` semantics): writes always use the
  newest key, reads try every configured key in turn, so retiring a key
  does not destroy the historical trail.
- **Two key shapes.** A 44-character urlsafe-base64 ``Fernet.generate_key()``
  value is used directly; any other string is treated as a passphrase and
  stretched with PBKDF2-HMAC-SHA256 before use.
- **Key hygiene.** The key material is never logged, never written to the
  audit file, and never included in exception messages — errors name the
  environment variable only.

Operators rotate by generating a new key and listing ``new,old`` in the
environment variable; entries written under the old key remain readable.
"""

import base64
import binascii
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

#: Canonical environment variable holding the audit-log encryption key(s).
ENV_VAR = "UNIFI_AUDIT_LOG_KEY"

#: Accepted alias, matching the name discussed on issue #22. Used only when
#: the canonical variable is unset.
ENV_VAR_ALIAS = "UNIFI_AUDIT_ENCRYPTION_KEY"

#: Marker prefix stored in encrypted fields so readers can distinguish
#: ciphertext from historical plaintext without consulting configuration.
TOKEN_PREFIX = "fernet:v1:"  # nosec B105 — format marker, not a password

#: Fixed salt for passphrase-based keys. A fixed salt permits offline
#: brute-force of a *known ciphertext* given a weak passphrase, which is why
#: passphrases must be high-entropy; raw Fernet keys (the recommended form)
#: are unaffected. The audit file itself is mode 0600, limiting ciphertext
#: availability to the owner.
_KDF_SALT = b"unifi-mcp-server/audit-log/v1"

#: PBKDF2 iterations. Tracks cryptography's own Fernet-recommended work
#: factor class (~600k, OWASP-aligned for SHA-256).
_KDF_ITERATIONS = 600_000


class AuditEncryptionError(Exception):
    """Raised when audit encryption cannot be initialised or used."""


def _load_single_key(secret: str) -> Fernet:
    """Build a ``Fernet`` from one key entry.

    A 44-char urlsafe-base64 value is a raw Fernet key and is used verbatim;
    anything else is treated as a passphrase and derived.

    Args:
        secret: One non-empty entry from the key environment variable.

    Returns:
        A ``Fernet`` instance for this entry.

    Raises:
        AuditEncryptionError: If the entry is empty or derivation fails.
    """
    candidate = secret.strip()
    if not candidate:
        raise AuditEncryptionError(
            f"Empty key entry in {ENV_VAR}/{ENV_VAR_ALIAS}; "
            "remove the extra comma or provide a key."
        )
    # Raw Fernet key path — Fernet validates urlsafe-b64 / 32 bytes itself.
    try:
        return Fernet(candidate.encode("utf-8"))
    except (ValueError, TypeError, binascii.Error):
        pass
    # Passphrase path: stretch to a 32-byte key.
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KDF_SALT,
        iterations=_KDF_ITERATIONS,
    )
    derived = base64.urlsafe_b64encode(kdf.derive(candidate.encode("utf-8")))
    return Fernet(derived)


def resolve_audit_cipher(env: dict[str, str] | None = None) -> MultiFernet | None:
    """Resolve the audit-log cipher from the environment.

    Reads ``UNIFI_AUDIT_LOG_KEY`` (falling back to
    ``UNIFI_AUDIT_ENCRYPTION_KEY``), splitting on commas. The first entry is
    the *write* key; all entries are tried on read.

    Args:
        env: Environment mapping to read from (defaults to ``os.environ``).
            Injectable for testing.

    Returns:
        A ``MultiFernet`` over the configured keys, or ``None`` when no key
        is configured — the caller must then preserve historical plaintext
        behaviour.

    Raises:
        AuditEncryptionError: If a key entry is invalid. The message names
            the environment variable but never includes key material.
    """
    source = os.environ if env is None else env
    raw = source.get(ENV_VAR)
    if raw is None:
        raw = source.get(ENV_VAR_ALIAS)
    if raw is None or not raw.strip():
        return None

    entries = raw.split(",")
    try:
        keys = [_load_single_key(entry) for entry in entries]
    except AuditEncryptionError:
        raise
    except Exception as exc:  # pragma: no cover - defensive: never leak key material
        raise AuditEncryptionError(
            f"Invalid audit encryption key in {ENV_VAR}: {type(exc).__name__}"
        ) from exc
    return MultiFernet(keys)


def encrypt_field(cipher: MultiFernet, value: Any) -> str:
    """Encrypt one JSON-serialisable payload field.

    Args:
        cipher: The resolved ``MultiFernet``.
        value: Any JSON-serialisable value (typically the already-redacted
            ``parameters`` dict or an ``error`` string).

    Returns:
        A prefixed Fernet token string safe to embed in the JSON-lines
        audit record.
    """
    plaintext = json.dumps(value, sort_keys=True).encode("utf-8")
    return TOKEN_PREFIX + cipher.encrypt(plaintext).decode("ascii")


def decrypt_field(cipher: MultiFernet, token: str) -> Any:
    """Decrypt one payload field produced by :func:`encrypt_field`.

    Args:
        cipher: The resolved ``MultiFernet`` (any configured key may match,
            which is what makes rotation non-destructive).
        token: The stored token, including the ``fernet:v1:`` prefix.

    Returns:
        The original JSON value.

    Raises:
        AuditEncryptionError: If the token is malformed or no configured
            key can decrypt it.
    """
    if not token.startswith(TOKEN_PREFIX):
        raise AuditEncryptionError("Not an encrypted audit field (missing prefix).")
    try:
        plaintext = cipher.decrypt(token[len(TOKEN_PREFIX) :].encode("ascii"))
    except InvalidToken as exc:
        raise AuditEncryptionError(
            "Audit field cannot be decrypted with any configured key."
        ) from exc
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise AuditEncryptionError(
            f"Malformed encrypted audit field: {type(exc).__name__}"
        ) from exc
    return json.loads(plaintext.decode("utf-8"))
