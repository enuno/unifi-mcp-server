"""Encryption of controller and cloud-account API keys stored in Postgres.

Keys are Fernet-encrypted with ``UNIFI_FLEET_CREDENTIAL_KEY`` (comma-separated,
newest first, same format as ``UNIFI_AUDIT_LOG_KEY``), so the database never
holds a usable API key. The key stays in the environment.
"""

import hashlib
import os

from cryptography.fernet import MultiFernet

from ..utils.audit_encryption import (
    TOKEN_PREFIX,
    AuditEncryptionError,
    build_cipher,
    decrypt_field,
    encrypt_field,
)
from ..utils.exceptions import ConfigurationError

#: Environment variable holding the credential encryption key(s).
CREDENTIAL_KEY_ENV = "UNIFI_FLEET_CREDENTIAL_KEY"

#: PBKDF2 salt for passphrase keys; differs from the audit key's salt so one
#: passphrase never yields the same key for both purposes.
_SALT = b"unifi-mcp-server/fleet-credentials/v1"


class CredentialCipher:
    """Encrypts and decrypts stored API keys."""

    def __init__(self, cipher: MultiFernet, fingerprint: str) -> None:
        """Wrap a cipher.

        Args:
            cipher: Encrypts with its first key, decrypts with any
            fingerprint: Identifies the current (first) key without revealing it
        """
        self._cipher = cipher
        self.fingerprint = fingerprint

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "CredentialCipher":
        """Build the cipher from ``UNIFI_FLEET_CREDENTIAL_KEY``.

        Raises:
            ConfigurationError: If the variable is unset or invalid; the
                message never includes key material
        """
        raw = (os.environ if env is None else env).get(CREDENTIAL_KEY_ENV, "")
        if not raw.strip():
            raise ConfigurationError(
                f"{CREDENTIAL_KEY_ENV} must be set when DATABASE_URL is: controller API "
                "keys are stored encrypted with it"
            )
        try:
            cipher = build_cipher(raw, CREDENTIAL_KEY_ENV, _SALT, alias=None)
        except AuditEncryptionError as e:
            raise ConfigurationError(str(e)) from e
        newest = raw.split(",")[0].strip()
        return cls(cipher, hashlib.sha256(newest.encode("utf-8")).hexdigest()[:12])

    def encrypt(self, secret: str) -> str:
        """Encrypt an API key under the current key."""
        return encrypt_field(self._cipher, secret)

    def decrypt(self, token: str) -> str:
        """Decrypt a stored API key with any configured key.

        Raises:
            AuditEncryptionError: If no configured key can decrypt it
        """
        value = decrypt_field(self._cipher, token)
        if not isinstance(value, str):
            raise AuditEncryptionError("Stored credential is not a string.")
        return value

    def rotate(self, token: str) -> str:
        """Re-encrypt a stored API key under the current key."""
        rotated = self._cipher.rotate(token.removeprefix(TOKEN_PREFIX).encode("ascii"))
        return TOKEN_PREFIX + rotated.decode("ascii")
