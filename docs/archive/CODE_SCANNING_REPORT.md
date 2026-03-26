# Code Scanning Report

**Generated:** 2026-01-24
**Total Open Issues:** 141
**Repository:** enuno/unifi-mcp-server

## Executive Summary

The repository has 141 open code scanning alerts across three scanning tools:

- **CodeQL:** 70 issues (code quality & security)
- **Trivy:** 68 issues (container & dependency vulnerabilities)
- **osv-scanner:** 3 issues (dependency vulnerabilities)

### Severity Breakdown

| Severity | Count | Percentage |
|----------|-------|------------|
| Error    | 35    | 24.8%      |
| Warning  | 18    | 12.8%      |
| Note     | 88    | 62.4%      |

---

## Critical Issues (Error Severity - 35 total)

### 1. Clear-text Logging of Sensitive Data (28 occurrences)

**Rule:** `py/clear-text-logging-sensitive-data`
**Severity:** Error
**Impact:** High - Sensitive data exposure in logs

**Affected Files:**

- `src/tools/client_management.py` (multiple locations)
- `src/tools/clients.py` (lines 45, 55)
- `src/tools/device_control.py`
- `src/tools/dpi.py`

**Issue:** The code logs sensitive information (marked as "private" by CodeQL data flow analysis) in clear text. This could expose:

- Client MAC addresses
- Device identifiers
- Network configuration details
- User information

**Recommendation:**

- Implement log sanitization for sensitive fields
- Use structured logging with field masking
- Add a logging utility that redacts sensitive data

**Example Fix:**

```python
# Before (unsafe)
logger.info(f"Client data: {client_data}")

# After (safe)
sanitized_data = sanitize_sensitive_fields(client_data)
logger.info(f"Client data: {sanitized_data}")
```

### 2. Wrong Named Argument in Function Calls (4 occurrences)

**Rule:** `py/call/wrong-named-argument`
**Severity:** Error
**Impact:** Medium - Runtime errors, incorrect behavior

**Affected File:** `src/tools/backups.py` (lines 154, 348, 443, 589)

**Issue:** Calls to `log_audit()` function use `error=...` parameter, but the function signature doesn't accept this parameter.

**Current Signature:**

```python
def log_audit(
    operation: str,
    parameters: dict[str, Any],
    result: str,
    user: str | None = None,
    site_id: str | None = None,
    dry_run: bool = False,
    log_file: str | Path | None = None,
) -> None:
```

**Recommendation:**
Two options:

1. **Add `error` parameter to `log_audit()` signature** (preferred):

   ```python
   def log_audit(
       operation: str,
       parameters: dict[str, Any],
       result: str,
       error: str | None = None,  # Add this
       user: str | None = None,
       ...
   ```

2. **Include error in parameters dict**:

   ```python
   log_audit(
       operation="backup",
       parameters={"error": str(e), ...},
       result="failed"
   )
   ```

### 3. Clear-text Storage of Sensitive Data (1 occurrence)

**Rule:** `py/clear-text-storage-sensitive-data`
**Severity:** Error
**Impact:** Medium - Data persistence security

**Affected File:** `src/utils/audit.py`

**Recommendation:**

- Encrypt sensitive data before writing to audit logs
- Use environment-specific encryption keys
- Consider using secrets management system

### 4. CVE-2026-0861: glibc Integer Overflow (2 occurrences)

**Rule:** `CVE-2026-0861`
**Severity:** Error
**Impact:** High - Heap corruption vulnerability

**Affected:** `library/unifi-mcp-server` (compiled binary)

**Issue:** Integer overflow in `memalign()` can lead to heap corruption.

**Recommendation:**

- Update glibc to patched version (2.40 or later)
- Rebuild the binary with updated system libraries
- This is a container/system-level fix

---

## Warning Issues (18 total)

### Container/System CVEs (15 occurrences)

**Trivy-detected vulnerabilities in system libraries:**

| CVE | Component | Count | Severity | Description |
|-----|-----------|-------|----------|-------------|
| CVE-2025-14104 | util-linux | 9 | Warning | Heap buffer overread in setpwnam() |
| CVE-2026-0915 | glibc | 2 | Warning | Information disclosure via network query |
| CVE-2025-15281 | glibc | 2 | Warning | wordexp uninitialized memory |
| CVE-2025-8869 | pip | 1 | Warning | Missing checks on symbolic link extraction |
| CVE-2025-7709 | sqlite | 1 | Warning | Integer overflow in FTS5 |

**Recommendation:**

- Update base container image to latest stable version
- Use distroless or minimal base images
- Implement container scanning in CI/CD pipeline

### MCP SDK Vulnerabilities (3 occurrences)

**Affected:** `.claude/skills/mcp-builder/scripts/requirements.txt`

| CVE | Description |
|-----|-------------|
| CVE-2025-66416 | MCP Python SDK - DNS rebinding protection not enabled by default |
| CVE-2025-53366 | FastMCP validation error leading to DoS |
| CVE-2025-53365 | Unhandled exception in HTTP transport leading to DoS |

**Recommendation:**

- Update MCP SDK to latest patched version
- Enable DNS rebinding protection explicitly:

  ```python
  from mcp import Server
  server = Server(enable_dns_rebinding_protection=True)
  ```

- Add error handling for HTTP transport exceptions

---

## Note Issues (88 total)

### Code Quality Issues (36 occurrences)

| Issue | Count | Files |
|-------|-------|-------|
| Module imported with both `import` and `import from` | 22 | Various |
| Unused local variables | 9 | Various |
| Unused imports | 3 | Various |
| Empty except blocks | 2 | Various |

**Recommendation:**

- Run automated linting: `ruff check --fix .`
- Enable pre-commit hooks to prevent these issues
- Use `# noqa` comments for intentional exceptions

### Historical CVEs (52 occurrences)

**Legacy vulnerabilities in container base image:**

- CVE-2022-0563 (util-linux, 9 occurrences)
- CVE-2025-6141 (ncurses, 4 occurrences)
- CVE-2024-56433 (shadow-utils, 2 occurrences)
- CVE-2023-31439 (systemd, 2 occurrences)
- CVE-2023-31438 (systemd, 2 occurrences)
- Various temp CVEs and older issues (33 occurrences)

**Recommendation:**

- Update to latest LTS base image (Ubuntu 24.04, Alpine 3.20, etc.)
- Most of these are in system utilities not used by the Python application
- Consider minimal runtime image (distroless/scratch-based)

---

## Prioritized Action Plan

### Immediate (This Week)

1. **Fix Wrong Argument Errors** (4 fixes)
   - Update `log_audit()` signature in `src/utils/audit.py`
   - Add `error: str | None = None` parameter
   - Update all 4 call sites in `src/tools/backups.py`
   - **Effort:** 30 minutes
   - **Impact:** Prevents runtime errors

2. **Implement Log Sanitization** (28 fixes)
   - Create `sanitize_sensitive_data()` utility function
   - Update logging calls in:
     - `src/tools/client_management.py`
     - `src/tools/clients.py`
     - `src/tools/device_control.py`
     - `src/tools/dpi.py`
   - **Effort:** 4-6 hours
   - **Impact:** Prevents sensitive data leaks

### Short-term (This Month)

3. **Update MCP SDK** (3 fixes)
   - Update to latest MCP Python SDK version
   - Enable DNS rebinding protection
   - Add transport error handling
   - Update `.claude/skills/mcp-builder/scripts/requirements.txt`
   - **Effort:** 1-2 hours
   - **Impact:** Fixes DoS vulnerabilities

4. **Code Quality Cleanup** (36 fixes)
   - Run `ruff check --fix .` to auto-fix import/variable issues
   - Configure pre-commit hooks
   - Add linting to CI/CD pipeline
   - **Effort:** 2-3 hours
   - **Impact:** Improves maintainability

### Medium-term (Next Quarter)

5. **Container Security Updates** (67+ fixes)
   - Audit current container base image
   - Migrate to minimal/distroless base image
   - Update all system dependencies
   - Implement Trivy scanning in CI
   - **Effort:** 8-16 hours
   - **Impact:** Eliminates system-level CVEs

6. **Audit Log Encryption** (1 fix)
   - Implement encryption for sensitive data in audit logs
   - Use environment-specific keys
   - Add secure storage backend
   - **Effort:** 4-8 hours
   - **Impact:** Compliance and data protection

---

## Automation Recommendations

### CI/CD Integration

Add to GitHub Actions workflow:

```yaml
name: Security Scanning

on: [push, pull_request]

jobs:
  codeql:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: python
      - uses: github/codeql-action/analyze@v3

  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'  # Fail on critical/high

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff
      - run: ruff check .
```

### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key
```

---

## Summary Statistics

### By Tool

- **CodeQL:** 70 issues (50% code quality, 50% security)
- **Trivy:** 68 issues (mostly container CVEs)
- **osv-scanner:** 3 issues (MCP SDK vulnerabilities)

### Quick Wins (Low Effort, High Impact)

1. Fix wrong argument errors (4 fixes, 30 min)
2. Run ruff auto-fix (22 fixes, 5 min)
3. Update MCP SDK (3 fixes, 1 hour)

**Total Quick Wins:** 29 issues resolved (~2 hours effort)

### Estimated Total Effort

- Critical fixes: 8-10 hours
- All code-level fixes: 16-24 hours
- Container/system fixes: 24-40 hours
- **Total:** 40-74 hours (1-2 weeks of dedicated effort)

---

## Next Steps

1. **Create GitHub Issues** for each category of fixes
2. **Assign priority labels** (P0, P1, P2)
3. **Create fix branches** for immediate items
4. **Schedule security review** after critical fixes
5. **Document security practices** in SECURITY.md

---

**Report Generated By:** Claude Code
**Contact:** See CONTRIBUTING.md for security issue reporting
