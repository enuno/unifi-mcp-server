# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

**Note:** As this project is in early development (pre-1.0), we recommend always using the latest version.

## Reporting a Vulnerability

We take the security of the UniFi MCP Server seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### Please DO NOT

- Open a public GitHub issue for security vulnerabilities
- Disclose the vulnerability publicly before it has been addressed
- Exploit the vulnerability beyond the minimum necessary to demonstrate the issue

### Please DO

**Report security vulnerabilities via GitHub Security Advisories:**

1. Go to the repository's Security tab
2. Click "Report a vulnerability"
3. Fill out the vulnerability report form with as much detail as possible

**Alternatively, you can email the maintainers directly at:**

- Use [GitHub Security Advisories](https://github.com/enuno/unifi-mcp-server/security/advisories) to report vulnerabilities

### What to Include in Your Report

Please include the following information in your report:

- **Description:** A clear description of the vulnerability
- **Impact:** What an attacker could achieve by exploiting this vulnerability
- **Reproduction Steps:** Step-by-step instructions to reproduce the vulnerability
- **Affected Versions:** Which versions of the project are affected
- **Suggested Fix:** If you have suggestions for how to fix the vulnerability, please include them
- **Your Contact Information:** So we can follow up with questions if needed

### Example Report

```
**Vulnerability Type:** API Key Exposure

**Description:**
The application logs UniFi API keys in plain text when debug
logging is enabled, potentially exposing sensitive authentication information.

**Impact:**
An attacker with access to log files could retrieve the UniFi API key
and gain unauthorized access to the UniFi Cloud API and network infrastructure.

**Reproduction Steps:**
1. Enable debug logging in the configuration
2. Start the MCP server
3. Examine the log output - API key appears in plain text

**Affected Versions:** 0.1.0 - 0.1.3

**Suggested Fix:**
Implement API key masking in the logging module to redact sensitive
information before writing to logs. Show only first 8 characters or use
placeholder text like "API key: ********".
```

## Response Timeline

We aim to respond to security vulnerability reports according to the following timeline:

- **Initial Response:** Within 48 hours of receiving the report
- **Vulnerability Assessment:** Within 7 days, we will provide an assessment of the vulnerability
- **Fix Development:** Critical vulnerabilities will be addressed within 30 days
- **Public Disclosure:** After a fix is released and users have had time to update (typically 7-14 days)

## Security Best Practices for Contributors

### Credential Management

**NEVER commit credentials or secrets to the repository:**

- **UniFi API keys** (primary authentication method)
- Passwords
- Private keys
- Certificates
- OAuth tokens
- Session tokens
- Encryption keys
- Database connection strings
- Any `.env` files containing secrets

**DO use environment variables or secure secret management:**

```python
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    """Application settings loaded from environment."""

    unifi_api_key: SecretStr = Field(..., description="UniFi API Key from unifi.ui.com")
    unifi_api_type: str = Field(default="cloud", description="API type: cloud or local")
    unifi_host: str = Field(default="api.ui.com", description="API host")
    unifi_port: int = Field(default=443, description="API port")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Usage with automatic masking
settings = Settings()
# API key is automatically masked when printed
print(f"Using host: {settings.unifi_host}")  # Safe
print(f"API key: {settings.unifi_api_key}")  # Outputs: **********
```

### UniFi API Key Security

**Obtaining API Keys Securely:**

1. Log in to [UniFi Site Manager](https://unifi.ui.com)
2. Navigate to Settings → Control Plane → Integrations
3. Create API Key with a descriptive name
4. **Copy the key immediately** - it's only shown once
5. Store in a password manager or secure secret management system

**API Key Best Practices:**

```python
# ❌ NEVER hardcode API keys
api_key = "abc123def456..."

# ❌ NEVER log full API keys
logging.debug(f"Using API key: {api_key}")

# ✅ DO load from environment
api_key = os.getenv("UNIFI_API_KEY")

# ✅ DO mask in logs (show first 8 chars only)
logging.debug(f"Using API key: {api_key[:8]}..." if api_key else "not set")

# ✅ DO use SecretStr for automatic masking
from pydantic import SecretStr
api_key = SecretStr(os.getenv("UNIFI_API_KEY"))
```

**API Key Rotation:**

- Rotate API keys every 90 days or sooner
- Immediately rotate if a key is exposed or compromised
- Use separate keys for development, staging, and production
- Revoke old keys after rotation
- Document key rotation procedures in your runbooks

**Secure Storage Options:**

- Environment variables (`.env` file, never committed)
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- Google Cloud Secret Manager
- Password managers (1Password, LastPass, etc.)

### Input Validation

Always validate and sanitize user inputs:

```python
from pydantic import BaseModel, validator, Field

class DeviceConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    mac_address: str

    @validator('mac_address')
    def validate_mac(cls, v):
        # Validate MAC address format
        import re
        if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', v):
            raise ValueError('Invalid MAC address format')
        return v.lower()
```

### API Security

**Authentication:**

- Always use HTTPS for API communications (required for UniFi Cloud API)
- Use API key authentication via `X-API-Key` header
- No session management needed (stateless authentication)
- Store API keys securely using environment variables or secret management

**API Key Headers:**

```python
import httpx
from pydantic import SecretStr

async def make_api_request(api_key: SecretStr, endpoint: str):
    """Make authenticated request to UniFi API."""
    headers = {
        "X-API-Key": api_key.get_secret_value(),  # Only expose when needed
        "Accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.ui.com/v1/{endpoint}",
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
```

**Rate Limiting:**

- Respect UniFi API rate limits (100 req/min EA, 10k req/min v1)
- Implement client-side rate limiting
- Add exponential backoff for 429 (rate limit) errors
- Cache frequently accessed data to reduce API calls

**Rate Limit Implementation Example:**

```python
import asyncio
from datetime import datetime, timedelta

class APIRateLimiter:
    """Enforce rate limits for UniFi API."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = []

    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        now = datetime.now()

        # Remove old requests
        self.requests = [req for req in self.requests if req > now - self.window]

        # Wait if at limit
        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] + self.window - now).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.requests.append(now)
```

**Error Handling:**

- Never expose API keys in error messages
- Log errors securely without exposing secrets
- Provide user-friendly error messages

```python
import logging

# ❌ BAD - Exposes API key
logging.error(f"Failed to connect with API key: {api_key}")

# ❌ BAD - Shows partial key (still risky)
logging.error(f"Auth failed with key: {api_key[:16]}...")

# ✅ GOOD - No key exposure
logging.error(f"Authentication failed for host '{host}'. Check your UNIFI_API_KEY.")

# ✅ GOOD - Redacted for debugging
logging.debug(f"API key configured: {'yes' if api_key else 'no'}")
```

### Dependency Security

**Regular Updates:**

- Keep all dependencies up to date
- Review security advisories for dependencies
- Use automated dependency scanning tools

**Vulnerability Scanning:**

Our CI/CD pipeline includes automated security scanning:

```bash
# Check for known vulnerabilities in dependencies
safety check

# Security linting with Bandit
bandit -r src/

# Docker image scanning
trivy image unifi-mcp-server:latest
```

**Manual Security Checks:**

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run security checks
safety check
bandit -r src/ -f json -o bandit-report.json

# Check for outdated packages with vulnerabilities
pip list --outdated
```

### AI-Specific Security Considerations

When using AI coding assistants:

1. **Review All AI-Generated Code:** Never merge AI-generated code without human review
2. **Validate Security-Critical Code:** Extra scrutiny for authentication, authorization, and data handling
3. **Test Generated Code:** Ensure comprehensive test coverage for AI contributions
4. **Audit AI Permissions:** Limit AI assistant access to only necessary resources
5. **Monitor AI Changes:** Track and review all AI-contributed changes in version control

See `AI_GIT_PRACTICES.md` and `AGENTS.md` for additional AI security guidelines.

### Docker Security

**Image Security:**

- Use official base images from trusted sources
- Keep base images updated
- Run containers as non-root users
- Scan images for vulnerabilities

**Example Secure Dockerfile:**

```dockerfile
FROM python:3.10-slim

# Create non-root user
RUN useradd -m -u 1000 mcpuser

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=mcpuser:mcpuser . .

# Switch to non-root user
USER mcpuser

# Run application
CMD ["python", "src/main.py"]
```

## Security Features

### Current Security Features

- **API Key Authentication:** Stateless authentication via official UniFi Cloud API
- **Environment-based Configuration:** API keys stored in environment variables, not in code
- **Secret Masking:** Pydantic SecretStr automatically masks sensitive values
- **Type Safety:** Pydantic models enforce data validation
- **Async Security:** Non-blocking I/O prevents certain timing attacks
- **HTTPS-Only:** Secure communication with UniFi Cloud API (TLS 1.2+)
- **Pre-commit Hooks:** Automated secret detection before commits using detect-secrets
- **Dependency Scanning:** Automated vulnerability scanning with Safety and Bandit
- **Container Security:** Docker images scanned with Trivy
- **Input Validation:** All user inputs validated with Pydantic models
- **Audit Log Encryption:** Optional Fernet at-rest encryption of audit payload fields (`UNIFI_AUDIT_LOG_KEY`), with non-destructive key rotation
- **Wrapper-Level Audit:** Every mutating tool call is recorded by the tool wrapper (an `attempt` record before the controller is contacted, then the outcome), along with denied calls and server start, naming the caller and target controller. If the attempt record cannot be written, the call is refused (`UNIFI_AUDIT_FAIL_CLOSED`, default on). With `UNIFI_AUDIT_READS=true`, read calls get the same two records (principal, tool, arguments, outcome; never the response), so a read-only deployment can see what a token read
- **Encrypted Controller Credentials:** With the Postgres fleet registry, controller and cloud-account API keys are Fernet-encrypted with `UNIFI_FLEET_CREDENTIAL_KEY` before they reach the database; the key never does. The server refuses to start without it, a key that cannot decrypt a credential skips that controller instead of failing the fleet, and `rotate_fleet_credentials` re-encrypts under a new key
- **Role-Based Access Control:** With the fleet registry, callers use server-issued API tokens (only SHA-256 hashes stored, 90-day default lifetime) with a role (`viewer`, `operator`, `admin`, `fleet-admin`) that grants tool risk tiers, optionally narrowed by tool-module patterns and controller labels. Enforcement happens in the tool wrapper before any controller is contacted, and every refusal is audited. Revocation takes effect within 30 seconds; a database error refuses the token. `MCP_AUTH_TOKEN` and stdio remain break-glass `fleet-admin` callers, flagged in audit records. With or without the registry, an `MCP_AUTH_TOKEN` entry written `<role>:<token>` (for example `viewer:<token>`) gets that role and the same tier enforcement
- **Append-Only Postgres Audit Store:** With DATABASE_URL, audit records go to `audit_log`, where a trigger refuses UPDATE, DELETE and TRUNCATE for every role, and each server's hash chain is kept with its head in `audit_chain_heads`. `verify_audit_chain` and `search_audit_log` are `fleet-admin` tools, and every query is audited
- **Tamper-Evident Audit Log:** Records are hash-chained, HMAC-keyed with `UNIFI_AUDIT_CHAIN_KEY`; `python -m src.utils.audit_verify` detects edited, deleted, inserted and reordered records, and with an anchored head (`--head`, or `--anchors` for the SIEM's anchor events) also records removed from the end. `verify_audit_chain` checks each Postgres chain against its `audit_chain_heads` entry (a chain with records but no head is reported too), so deleting the newest records, a whole chain or the whole table is caught, and checks every searchable column (operation, result, principal, controller, time, seq, hash) against the sealed record, so a record cannot be hidden from `search_audit_log` by editing its columns. A drill (`tests/unit/fleet/test_drill_tamper.py`) makes each of these changes as the database superuser with triggers disabled and expects every one to be caught

- **Debug Passthrough Behind `DEBUG`:** `debug_api_request` (raw GET or DELETE to any controller endpoint) is registered only when `DEBUG` is truthy. It goes through the same tool wrapper as every other tool: `UNIFI_READ_ONLY` removes it, `UNIFI_DRY_RUN` previews it, every call needs the `destructive` tier and is audited, and a DELETE needs `confirm=true`. The endpoint must be a controller-relative path; absolute and scheme-relative URLs are refused so the API key never leaves for another host. Leave `DEBUG` unset in production

### Phase 4 Mutating Tools Safety Mechanisms

**All mutating tools (Phase 4) implement comprehensive safety features:**

1. **Confirmation Requirement:**

   ```python
   # ❌ WILL FAIL - Missing confirmation
   await create_firewall_rule(site_id="default", name="test", action="drop")

   # ✅ WORKS - With confirmation
   await create_firewall_rule(site_id="default", name="test", action="drop", confirm=True)
   ```

2. **Dry Run Mode:**

   ```python
   # Preview changes without executing
   result = await create_network(
       site_id="default",
       name="Guest",
       vlan_id=100,
       subnet="192.168.100.0/24",
       dry_run=True  # No actual changes made
   )
   # Returns: {"dry_run": True, "would_create": {...}}
   ```

3. **Audit Logging:**
   - Every mutating call, every refused call and server start are recorded by
     the tool wrapper in `UNIFI_AUDIT_LOG_PATH` (default `audit.log`), or in
     Postgres with the fleet registry
   - Each record names the principal, tool, tier, controller, site, the
     credential-redacted arguments and the outcome
   - Format: JSON lines, hash-chained; file created mode 0600 (owner-readable only)
   - Reads are not recorded unless refused. Set `UNIFI_AUDIT_READS=true` to
     record them too: an `attempt` and an outcome record per read, with the
     arguments but never the response, so client lists and device inventory
     stay out of the audit store. Without it, a read-only deployment writes
     no record of what a token read, and a leaked bearer can pull the whole
     inventory unseen. `UNIFI_AUDIT_FAIL_CLOSED` then applies to reads as
     well. Expect two records per read; size rotation and retention for it
   - Controller and HTTP error text is redacted before it is stored:
     credential-named values (`"x_passphrase": "..."`, `?apikey=...`,
     `X-API-KEY: ...`), `Bearer` tokens and `user:password@` in URLs become
     `***`. Identifiers such as the MAC in `api.err.MacUsed` stay readable,
     as they do in `parameters`. The match is by key name, so a secret the
     controller quotes without its key name is not caught; set
     `UNIFI_AUDIT_LOG_KEY` as well if error text can carry one

   **Three different records.** The server writes three things that can look
   like an audit trail. Only the first is one:

   | | MCP audit log | A2A audit facility | Application log |
   |---|---|---|---|
   | Source | Tool wrapper (`src/utils/audit.py`) | `/a2a/delegate` handler (`src/a2a/audit.py`) | Python `logging`, `LOG_LEVEL` |
   | Where | `UNIFI_AUDIT_LOG_PATH`, or Postgres `audit_log` with `DATABASE_URL` | `logs/a2a-audit.jsonl` plus an in-memory list | stdout/stderr |
   | Covers | Mutating, refused and (with `UNIFI_AUDIT_READS`) read MCP tool calls; admin and system events | A2A delegations only; MCP tool calls never appear here | Whatever the code logs |
   | Redaction | Credentials redacted in arguments and error text; payload encryption with `UNIFI_AUDIT_LOG_KEY` | None: parameters and the tool **result** are written as received | Not guaranteed |
   | Tamper evidence | Hash chain (HMAC with `UNIFI_AUDIT_CHAIN_KEY`), append-only table, `audit_verify` | None | None |
   | SIEM export | Yes, `UNIFI_AUDIT_SIEM_TARGETS` | No | Only through your log shipper |
   | Fail closed | Yes, `UNIFI_AUDIT_FAIL_CLOSED` | No, a failed write is logged and the call goes ahead | No |

   Use the MCP audit log as evidence of who did what. The A2A file holds tool
   results and is not redacted, so protect it like the controller data it
   contains, or keep `/a2a/*` unexposed. The application log is for
   operating the server and carries a one-line `AUDIT:` summary per record,
   which is no substitute for the record itself.

4. **Audit Log Encryption (issue #22):**

   Audit records contain operation parameters and controller error text that
   can carry sensitive identifiers (MAC addresses, IPs, client names, site
   UUIDs) and, despite credential redaction, benefit from confidentiality at
   rest. Operators can enable at-rest encryption of the sensitive payload
   fields by setting `UNIFI_AUDIT_LOG_KEY`:

   ```bash
   # Generate a key
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

   # Configure (comma-separated, NEWEST first, for rotation)
   UNIFI_AUDIT_LOG_KEY=gAAAA...,gAAAA...-old
   ```

   **What is encrypted vs. what stays readable:**

   | Field | Treatment | Why |
   |-------|-----------|-----|
   | `parameters` | encrypted (after credential redaction) | carries request payloads |
   | `error` | encrypted | controller errors quote offending values (MACs, IDs) back |
   | `timestamp`, `operation`, `result`, `dry_run`, `site_id`, `user` | plaintext | filtering/pagination must work without the key |

   **Guarantees and behavior:**

   - **Backward compatible.** With no key configured, the on-disk format is
     byte-identical to historical plaintext records. Encryption only
     activates when a key is present.
   - **Redaction first, encryption second.** `sanitize_credentials()` runs
     before encryption, so a decrypted entry is exactly the redacted record
     an operator would see today. Encryption complements redaction; it never
     replaces or weakens it.
   - **Non-destructive rotation.** `MultiFernet` semantics: the newest key
     writes, all listed keys are tried on read. Retiring a key never
     destroys the historical trail. Pre-existing plaintext entries stay
     readable after enabling encryption.
   - **Fail closed on misconfiguration.** A configured-but-unusable key
     raises `AuditEncryptionError` at logger creation instead of silently
     writing plaintext the operator believed was encrypted.
   - **Key hygiene.** The key is never written to the audit file, never
     logged, and never included in exception messages (errors name the
     environment variable only). Store it in a secrets manager; never
     commit it.
   - **Undecryptable entries are reported, not dropped.** A record that no
     configured key can decrypt (e.g. after key loss) surfaces as a
     `<undecryptable: field>` placeholder with a logged warning; the rest of
     the trail remains intact.

   **Decrypting a log file** (operators / forensics):

   ```bash
   UNIFI_AUDIT_LOG_KEY=... python -m src.utils.audit_decrypt /var/log/unifi-mcp/audit.log
   # filters: --operation create_wlan --limit 50
   ```

   Key shape: a 44-character urlsafe-base64 `Fernet.generate_key()` value is
   used directly; any other string is treated as a passphrase and stretched
   with PBKDF2-HMAC-SHA256 (600k iterations, fixed application salt) — use
   high-entropy passphrases. `UNIFI_AUDIT_ENCRYPTION_KEY` is accepted as a
   legacy alias when the primary variable is unset.

   **Tamper evidence:** every record carries `chain_id`, `seq`, `prev_hash`
   and `hash`, an HMAC-SHA256 over the stored record keyed by
   `UNIFI_AUDIT_CHAIN_KEY` (plain SHA-256 when unset). Each server process
   writes its own chain. The hash covers the stored, possibly encrypted,
   record, so verifying needs the chain key but not the payload key:

   ```bash
   UNIFI_AUDIT_CHAIN_KEY=... python -m src.utils.audit_verify /var/log/unifi-mcp/audit.log
   ```

   Removing the last records of a chain is not detectable from the file
   alone. Pass a head recorded elsewhere and the chain must end exactly
   there:

   ```bash
   python -m src.utils.audit_verify audit.log --head CHAIN_ID:SEQ:HASH
   ```

   In Postgres, `verify_audit_chain` compares every chain with its
   `audit_chain_heads` entry. Someone with write access to the database could
   rewrite the records and that table together; only a head kept off the
   server catches that, which is what the SIEM anchors below are for. Use a
   different value from the payload key and keep it in your secret manager,
   never in the repository.

   **SIEM export and anchors:** set `UNIFI_AUDIT_SIEM_TARGETS` to copy every
   stored record (the encrypted-payload form, exactly as written) to one or
   more destinations. Targets require `UNIFI_AUDIT_CHAIN_KEY`, and the server
   refuses to start without it: an unkeyed SHA-256 chain can be recomputed by
   whoever edits the records, so the copy and the anchors the SIEM keeps
   would prove nothing.

   | Target | Format |
   |---|---|
   | `syslog+tls://host:6514` | RFC 5424 over TLS with octet-counted framing (RFC 5425), facility local0; `syslog+tcp://` sends without TLS (warned about unless loopback) |
   | `https://host/path` | JSON array POST, signed: `X-UniFi-MCP-Signature: sha256=HMAC(secret, "<X-UniFi-MCP-Timestamp>.<body>")` with `UNIFI_AUDIT_SIEM_WEBHOOK_SECRET` (required); `http://` only to loopback |
   | `otlp+https://collector:4318` | OpenTelemetry logs (OTLP/HTTP JSON, `/v1/logs`); extra headers from `UNIFI_AUDIT_SIEM_OTLP_HEADERS`; `otlp+http://` warned about unless loopback |

   Delivery never blocks a tool call. Records wait in an on-disk buffer per
   target (directory 0700, files 0600, `UNIFI_AUDIT_SIEM_BUFFER_DIR`,
   default `siem-buffer` next to the audit log) and are retried with backoff
   up to 60 s. The buffer survives a restart; past
   `UNIFI_AUDIT_SIEM_BUFFER_MAX_MB` the oldest records are dropped and
   counted in a warning. Delivery is at least once, so deduplicate on
   `event_id`. Verify targets with `UNIFI_AUDIT_SIEM_CA_FILE` for a private
   CA. Records are only exported once stored, so a record the server refused
   to write is never sent.

   Every `UNIFI_AUDIT_SIEM_ANCHOR_SECONDS` (default 300) and on shutdown, the
   server also sends an `anchor` event per chain that moved: `chain_id`,
   `seq` and `hash` of its latest record. Anchors are tracked per target, so a
   target that missed one (a failed write, or its buffer dropping it over the
   cap) gets it again at the next interval. Export the anchors from the SIEM as
   JSON lines (or a JSON array) and check a log against them (a file with no
   anchor events is an error, not a pass):

   ```bash
   UNIFI_AUDIT_CHAIN_KEY=... python -m src.utils.audit_verify audit.log --anchors anchors.jsonl
   ```

   Records rewritten together with their heads in Postgres no longer match
   the anchor the SIEM holds, and the drill in `test_drill_tamper.py` shows
   it. Records written after the last anchor are covered by the next one, so
   keep the interval short enough for your needs.

   **Retention:** with `UNIFI_AUDIT_RETENTION_DAYS` set, run the retention job
   as the schema owner (it uses `MIGRATION_DATABASE_URL` when set), for example
   daily from cron or a Kubernetes CronJob:

   ```bash
   python -m src.fleet.cli audit-retention            # dry run: what would go
   python -m src.fleet.cli audit-retention --confirm  # archive, then delete
   ```

   It refuses to delete anything unless the whole store verifies. Expired
   records go to a gzip archive in `UNIFI_AUDIT_ARCHIVE_DIR` (default
   `audit-archive` next to the audit log; directory 0700, files 0600) with a
   manifest, both written to disk before the delete commits. Move archives to
   storage of their own; check one with:

   ```bash
   UNIFI_AUDIT_CHAIN_KEY=... python -m src.utils.audit_verify \
     audit-before-....jsonl.gz --manifest audit-before-....jsonl.gz.manifest.json
   ```

   `audit_archives` records where each chain was cut, so `verify_audit_chain`
   keeps checking what remains and reports archive rows that were removed.
   The append-only trigger allows a DELETE only by the table's owner inside
   the retention transaction; the server itself never deletes audit records.
   The run's `audit_retention` admin event is written in the same
   transaction as the delete, the job needs no controller credentials
   (no `UNIFI_API_KEY`), and `UNIFI_READ_ONLY` refuses `--confirm`.

   **JSONL rotation and retention:** without Postgres, set
   `UNIFI_AUDIT_LOG_ROTATE_MB` and the server renames the full audit file to
   `audit.log.<UTC time>Z` and starts a new one; the hash chain continues
   across files, so verify them together, oldest first (`[0-9]*` matches
   only the rotated files, not the checkpoint file retention adds). Rotation
   renames the file, so it must live in a writable directory: in Docker,
   mount a directory and point `UNIFI_AUDIT_LOG_PATH` into it rather than
   mounting the file itself:

   ```bash
   python -m src.utils.audit_verify /var/log/unifi-mcp/audit.log.[0-9]* /var/log/unifi-mcp/audit.log
   ```

   Retention removes rotated files whose records are all past
   `UNIFI_AUDIT_RETENTION_DAYS` (never the file being written), after the
   same verify-then-archive steps, and records where each chain was cut in
   `audit.log.checkpoints.jsonl`:

   ```bash
   python -m src.utils.audit_retention /var/log/unifi-mcp/audit.log --confirm
   python -m src.utils.audit_verify /var/log/unifi-mcp/audit.log.[0-9]* /var/log/unifi-mcp/audit.log \
     --checkpoints /var/log/unifi-mcp/audit.log.checkpoints.jsonl
   ```

   Whoever can rewrite the log can rewrite the checkpoint file too, so keep
   the archives (or the SIEM copy) on storage the server cannot change.

   **Least-privilege database role (optional):** the server needs no DDL and
   no UPDATE/DELETE on the audit table. Run migrations as the schema owner
   (`MIGRATION_DATABASE_URL`) and point `DATABASE_URL` at a role granted only
   what it uses:

   ```sql
   CREATE ROLE unifi_mcp_runtime LOGIN PASSWORD '...';
   GRANT SELECT, INSERT, UPDATE ON credentials, cloud_accounts, controllers, api_tokens
     TO unifi_mcp_runtime;
   GRANT SELECT, INSERT ON audit_log TO unifi_mcp_runtime;
   GRANT SELECT, INSERT, UPDATE ON audit_chain_heads TO unifi_mcp_runtime;
   GRANT SELECT ON audit_archives TO unifi_mcp_runtime;
   GRANT USAGE ON SEQUENCE audit_log_id_seq TO unifi_mcp_runtime;
   GRANT SELECT ON unifi_mcp_alembic_version TO unifi_mcp_runtime;
   -- Workers replace each controller's site and device snapshots.
   GRANT SELECT, INSERT, UPDATE, DELETE ON sites, device_inventory TO unifi_mcp_runtime;
   ```

   The Ansible playbook (`deploy/ansible/`) creates this role and these grants
   when it runs Postgres itself.

   The append-only trigger then backs up the missing grants rather than
   being the only control.

5. **Input Validation:**
   - All parameters validated before execution
   - Type checking via Pydantic models
   - Custom validators for MAC addresses, IPs, VLANs, etc.
   - Raises `ValidationError` for invalid inputs

**Mutating Tool Categories:**

- **Firewall Management:** `create_firewall_rule`, `update_firewall_rule`, `delete_firewall_rule`
- **Network Configuration:** `create_network`, `update_network`, `delete_network`
- **Device Control:** `restart_device`, `locate_device`, `upgrade_device`
- **Client Management:** `block_client`, `unblock_client`, `reconnect_client`

**Audit Log Example:**

```json
{
  "timestamp": "2025-10-18T10:30:00Z",
  "operation": "create_firewall_rule",
  "parameters": {"site_id": "default", "name": "Block SSH", "action": "drop"},
  "result": "success",
  "dry_run": false,
  "site_id": "default"
}
```

### Planned Security Enhancements

- [x] Audit logging for all mutating operations (✅ Phase 4)
- [x] At-rest encryption of audit-log payload fields, key rotation via MultiFernet (✅ issue #22)
- [x] Confirmation requirements for dangerous operations (✅ Phase 4)
- [x] Dry-run mode for safe testing (✅ Phase 4)
- [ ] Role-based access control (RBAC) for MCP tools
- [ ] API key rotation automation
- [ ] Request signing for additional security
- [ ] IP allowlist/denylist support
- [ ] Webhook signature verification
- [ ] Enhanced monitoring and alerting for suspicious activity
- [ ] Security headers for HTTP responses
- [ ] Support for multiple API keys with different scopes

## Security Audit History

| Date       | Type          | Findings | Status   |
|------------|---------------|----------|----------|
| 2025-10-17 | Initial Setup | N/A      | Baseline |

## Compliance and Standards

This project strives to follow:

- **OWASP Top 10:** Web application security best practices
- **CWE Top 25:** Common weakness enumeration
- **NIST Guidelines:** Cybersecurity framework recommendations
- **Secure Coding Standards:** For Python development

## Security Contacts

For security-related questions or concerns:

- **Security Reports:** Use [GitHub Security Advisories](https://github.com/enuno/unifi-mcp-server/security/advisories)
- **Project Issues:** [GitHub Issues](https://github.com/enuno/unifi-mcp-server/issues)

## Acknowledgments

We appreciate the security research community and recognize contributors who responsibly disclose vulnerabilities:

{/*Add acknowledged security researchers here*/}

## Additional Resources

- [OWASP Python Security](https://owasp.org/www-project-python-security/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)

---

**Last Updated:** 2026-03-17

Thank you for helping keep UniFi MCP Server and its users safe!

## Known Dependabot Alerts (Non-Impacting)

None. As of 2026-03-17, all known vulnerabilities have been resolved by upgrading
dependencies (authlib, fastmcp, PyJWT, black, nltk) and diskcache has been removed
from the dependency tree entirely (fastmcp 3.x no longer depends on it).
