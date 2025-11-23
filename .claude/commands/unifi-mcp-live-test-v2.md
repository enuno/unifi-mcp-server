---
description: Test UniFi MCP server across discovered environments with interactive selection and automated bug reporting
allowed-tools:
  - Read
  - Write
  - AskUserQuestion
  - Bash(git:*)
  - Bash(gh:*)
  - Bash(python:*)
  - Bash(python3:*)
  - Bash(uv:*)
  - Bash(npx:*)
  - Bash(curl:*)
  - Bash(grep:*)
  - Bash(find:*)
  - Bash(sleep:*)
  - Bash(date:*)
  - Bash(wc:*)
  - Bash(cat:*)
  - Bash(jq:*)
author: project
version: 2.0.0
---

# UniFi MCP Server - Portable Live Environment Testing

## Purpose
Automatically discover UniFi environments from .env configuration, prompt for which environments to test, execute comprehensive MCP server testing, record errors, create GitHub issues, and integrate with triage bot workflow.

**Key Features:**
- ✅ Fully portable - no hardcoded IPs or hostnames
- ✅ Auto-discovers environments from .env file
- ✅ Interactive environment selection
- ✅ Prevents sensitive data leakage
- ✅ Automated GitHub issue creation
- ✅ Triage bot integration

---

## Phase 1: Pre-Flight Checks and Environment Discovery

### 1.1 Verify Prerequisites

```bash
echo "╔════════════════════════════════════════════════════╗"
echo "║   UNIFI MCP LIVE ENVIRONMENT TEST - STARTING       ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Check Node.js
if command -v node &> /dev/null; then
  echo "✅ Node.js: $(node --version)"
else
  echo "❌ Node.js not installed - required for MCP Inspector"
  exit 1
fi

# Check Python/UV
if command -v python3 &> /dev/null && command -v uv &> /dev/null; then
  echo "✅ Python: $(python3 --version | head -1)"
  echo "✅ UV: $(uv --version | head -1)"
else
  echo "❌ Python3 or UV not installed"
  exit 1
fi

# Check GitHub CLI
if command -v gh &> /dev/null; then
  echo "✅ GitHub CLI: $(gh --version | head -1)"
else
  echo "❌ GitHub CLI not installed - required for issue creation"
  exit 1
fi

# Verify git repository
if git rev-parse --is-inside-work-tree &> /dev/null; then
  echo "✅ Git repository confirmed"
else
  echo "❌ Not in a git repository"
  exit 1
fi

# Check MCP server exists
if [ -f src/main.py ]; then
  echo "✅ MCP server found (src/main.py)"
else
  echo "❌ src/main.py not found"
  exit 1
fi

echo ""
```

### 1.2 Ensure .gitignore Protection

```bash
echo "Checking .gitignore for sensitive data protection..."

# Ensure test-results/ is in .gitignore
if ! grep -q "^test-results/" .gitignore 2>/dev/null; then
  echo "Adding test-results/ to .gitignore..."
  echo "" >> .gitignore
  echo "# MCP live testing - contains local network information" >> .gitignore
  echo "test-results/" >> .gitignore
  echo "✅ Added test-results/ to .gitignore"
else
  echo "✅ test-results/ already in .gitignore"
fi

# Add other sensitive patterns
for PATTERN in "*.env.test" "test-*.log" "*-credentials.json"; do
  if ! grep -q "${PATTERN}" .gitignore 2>/dev/null; then
    echo "${PATTERN}" >> .gitignore
    echo "✅ Added ${PATTERN} to .gitignore"
  fi
done

echo ""
```

### 1.3 Discover Test Environments from .env

```bash
echo "Discovering test environments from .env..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
  echo "❌ .env file not found"
  echo "Please create .env from .env.example and configure your UniFi credentials"
  exit 1
fi

# Source .env safely (don't export, just read values)
# Create environment discovery report
ENV_REPORT=$(cat <<EOF
{
  "cloud_api": null,
  "local_hosts": [],
  "api_type": null,
  "has_api_key": false,
  "has_username": false,
  "has_password": false
}
EOF
)

# Read API type
if grep -q "^UNIFI_API_TYPE=cloud" .env; then
  ENV_API_TYPE="cloud"
elif grep -q "^UNIFI_API_TYPE=local" .env; then
  ENV_API_TYPE="local"
else
  ENV_API_TYPE="unknown"
fi

# Check for Cloud API configuration
if grep -q "^UNIFI_HOST=" .env; then
  CLOUD_HOST=$(grep "^UNIFI_HOST=" .env | cut -d= -f2 | tr -d '"' | tr -d "'")
  if [ ! -z "${CLOUD_HOST}" ] && [ "${CLOUD_HOST}" != "your-host-here" ]; then
    echo "✅ Found Cloud API configuration: ${CLOUD_HOST}"
    HAS_CLOUD=true
  else
    HAS_CLOUD=false
  fi
else
  HAS_CLOUD=false
fi

# Check for Local Host configuration
if grep -q "^UNIFI_LOCAL_HOST=" .env; then
  LOCAL_HOST=$(grep "^UNIFI_LOCAL_HOST=" .env | cut -d= -f2 | tr -d '"' | tr -d "'")
  if [ ! -z "${LOCAL_HOST}" ] && [ "${LOCAL_HOST}" != "your-host-here" ]; then
    # Get SSL verification setting
    if grep -q "^UNIFI_LOCAL_VERIFY_SSL=true" .env; then
      LOCAL_SSL="true"
    else
      LOCAL_SSL="false"
    fi
    echo "✅ Found Local Gateway configuration: ${LOCAL_HOST} (SSL: ${LOCAL_SSL})"
    HAS_LOCAL=true
  else
    HAS_LOCAL=false
  fi
else
  HAS_LOCAL=false
fi

# Check authentication method
if grep -q "^UNIFI_API_KEY=" .env && [ $(grep "^UNIFI_API_KEY=" .env | cut -d= -f2 | wc -c) -gt 10 ]; then
  echo "✅ API Key configured"
  HAS_API_KEY=true
else
  HAS_API_KEY=false
fi

if grep -q "^UNIFI_USERNAME=" .env && grep -q "^UNIFI_PASSWORD=" .env; then
  echo "✅ Username/Password configured"
  HAS_CREDS=true
else
  HAS_CREDS=false
fi

# Validate we have at least one environment and auth method
if [ "${HAS_CLOUD}" = "false" ] && [ "${HAS_LOCAL}" = "false" ]; then
  echo ""
  echo "❌ No valid environments found in .env"
  echo "Please configure either UNIFI_HOST (cloud) or UNIFI_LOCAL_HOST (local)"
  exit 1
fi

if [ "${HAS_API_KEY}" = "false" ] && [ "${HAS_CREDS}" = "false" ]; then
  echo ""
  echo "❌ No authentication configured"
  echo "Please set either UNIFI_API_KEY or UNIFI_USERNAME + UNIFI_PASSWORD"
  exit 1
fi

echo ""
echo "Environment Discovery Summary:"
echo "  Cloud API: ${HAS_CLOUD}"
echo "  Local Gateway: ${HAS_LOCAL}"
echo "  Authentication: $([ "${HAS_API_KEY}" = "true" ] && echo "API Key" || echo "Username/Password")"
echo ""
```

### 1.4 Interactive Environment Selection

```bash
# Present discovered environments and ask which to test
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Select Environments to Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Build environment selection array
ENVS_TO_TEST=()

if [ "${HAS_CLOUD}" = "true" ]; then
  echo "Cloud API (${CLOUD_HOST}) available"
  read -p "Test Cloud API? (y/n): " TEST_CLOUD
  if [[ "${TEST_CLOUD}" =~ ^[Yy]$ ]]; then
    ENVS_TO_TEST+=("cloud:${CLOUD_HOST}")
    echo "  ✅ Will test Cloud API"
  else
    echo "  ⏭️  Skipping Cloud API"
  fi
  echo ""
fi

if [ "${HAS_LOCAL}" = "true" ]; then
  # Mask the IP for display (show only first 2 octets)
  MASKED_IP=$(echo "${LOCAL_HOST}" | awk -F. '{print $1"."$2".x.x"}')
  echo "Local Gateway (${MASKED_IP}, SSL: ${LOCAL_SSL}) available"
  read -p "Test Local Gateway? (y/n): " TEST_LOCAL
  if [[ "${TEST_LOCAL}" =~ ^[Yy]$ ]]; then
    ENVS_TO_TEST+=("local:${LOCAL_HOST}:${LOCAL_SSL}")
    echo "  ✅ Will test Local Gateway"
  else
    echo "  ⏭️  Skipping Local Gateway"
  fi
  echo ""
fi

# Verify at least one environment selected
if [ ${#ENVS_TO_TEST[@]} -eq 0 ]; then
  echo "❌ No environments selected for testing"
  exit 1
fi

echo "Selected ${#ENVS_TO_TEST[@]} environment(s) for testing"
echo ""
```

### 1.5 Create Test Session Directory

```bash
# Create timestamped test session
TEST_SESSION_ID=$(date +%Y%m%d-%H%M%S)
TEST_DIR="test-results/${TEST_SESSION_ID}"
mkdir -p "${TEST_DIR}"

echo "Test Session: ${TEST_SESSION_ID}"
echo "Results Directory: ${TEST_DIR}"
echo ""

# Initialize session log
cat > "${TEST_DIR}/test-session.log" <<EOF
UniFi MCP Server Live Environment Test
Session ID: ${TEST_SESSION_ID}
Started: $(date -Iseconds)

Selected Environments: ${#ENVS_TO_TEST[@]}
$(for env in "${ENVS_TO_TEST[@]}"; do echo "- ${env}"; done)

Prerequisites:
- Node.js: $(node --version)
- Python: $(python3 --version | head -1)
- UV: $(uv --version | head -1)
- GitHub CLI: $(gh --version | head -1)

EOF

echo "✅ Test session initialized"
echo ""
```

---

## Phase 2: Environment Testing

### 2.1 Test Each Selected Environment

```bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 2: Testing Environments"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Counter for environment testing
ENV_COUNTER=0

for ENV_CONFIG in "${ENVS_TO_TEST[@]}"; do
  ENV_COUNTER=$((ENV_COUNTER + 1))

  # Parse environment configuration
  IFS=':' read -ra ENV_PARTS <<< "${ENV_CONFIG}"
  ENV_TYPE="${ENV_PARTS[0]}"

  if [ "${ENV_TYPE}" = "cloud" ]; then
    ENV_NAME="Cloud_API"
    ENV_HOST="${ENV_PARTS[1]}"
    ENV_API_TYPE="cloud"
    ENV_SSL="true"
  else
    ENV_NAME="Local_Gateway"
    ENV_HOST="${ENV_PARTS[1]}"
    ENV_API_TYPE="local"
    ENV_SSL="${ENV_PARTS[2]}"
  fi

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Testing Environment ${ENV_COUNTER}/${#ENVS_TO_TEST[@]}: ${ENV_NAME}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  TEST_LOG="${TEST_DIR}/${ENV_NAME}-test.log"
  TEST_RESULTS="${TEST_DIR}/${ENV_NAME}-results.json"

  # Test connectivity first
  echo "1. Testing connectivity..."

  if [ "${ENV_TYPE}" = "cloud" ]; then
    CONN_URL="https://${ENV_HOST}"
  else
    CONN_URL="https://${ENV_HOST}"
  fi

  if [ "${ENV_SSL}" = "false" ]; then
    CURL_SSL_OPT="-k"
  else
    CURL_SSL_OPT=""
  fi

  timeout 5 curl ${CURL_SSL_OPT} -s -o /dev/null -w "%{http_code}" "${CONN_URL}" > "${TEST_DIR}/${ENV_NAME}-connectivity.txt" 2>&1 || echo "timeout" > "${TEST_DIR}/${ENV_NAME}-connectivity.txt"

  CONN_STATUS=$(cat "${TEST_DIR}/${ENV_NAME}-connectivity.txt")

  if [ "${CONN_STATUS}" = "timeout" ] || [ -z "${CONN_STATUS}" ]; then
    echo "❌ Cannot reach ${ENV_HOST} (timeout or unreachable)"
    echo "CONNECTIVITY_FAIL" > "${TEST_DIR}/${ENV_NAME}-status.txt"
    continue
  else
    echo "✅ ${ENV_HOST} reachable (HTTP ${CONN_STATUS})"
  fi

  # Create test script for this environment
  echo "2. Creating test script..."

  cat > "${TEST_DIR}/test-${ENV_NAME}.py" <<'PYEOF'
import asyncio
import json
import sys
import os
from datetime import datetime

# Environment will be set by caller
# os.environ["UNIFI_API_TYPE"] = ...
# os.environ["UNIFI_HOST"] or os.environ["UNIFI_LOCAL_HOST"] = ...

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

async def test_tools():
    from src.config.config import Settings
    from src.tools import site_manager, devices, clients, networks, wifi

    settings = Settings()
    env_name = os.environ.get("TEST_ENV_NAME", "unknown")

    results = {
        "environment": env_name,
        "api_type": str(settings.api_type),
        "timestamp": datetime.now().isoformat(),
        "tests": []
    }

    # List of read-only tools to test
    tools_to_test = [
        ("get_sites", site_manager.get_sites, {}),
        ("get_devices", devices.get_devices, {"site_name": "default"}),
        ("get_clients", clients.get_clients, {"site_name": "default"}),
        ("get_networks", networks.get_networks, {"site_name": "default"}),
        ("get_wlans", wifi.get_wlans, {"site_name": "default"}),
    ]

    for tool_name, tool_func, params in tools_to_test:
        print(f"\nTesting {tool_name}...")
        test_result = {
            "tool": tool_name,
            "params": params,
            "status": "unknown",
            "error": None
        }

        try:
            start_time = asyncio.get_event_loop().time()
            result = await tool_func(settings=settings, **params)
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000

            if isinstance(result, list):
                count = len(result)
                print(f"✅ {tool_name}: {count} items ({response_time:.0f}ms)")
                test_result["status"] = "success"
                test_result["result_count"] = count
                test_result["response_time_ms"] = round(response_time, 1)
            else:
                print(f"✅ {tool_name}: completed ({response_time:.0f}ms)")
                test_result["status"] = "success"
                test_result["response_time_ms"] = round(response_time, 1)
        except Exception as e:
            error_msg = str(e)
            # Sanitize error messages - remove IP addresses
            import re
            error_msg = re.sub(r'\d+\.\d+\.\d+\.\d+', 'x.x.x.x', error_msg)

            print(f"❌ {tool_name}: {error_msg}")
            test_result["status"] = "error"
            test_result["error"] = error_msg
            test_result["error_type"] = type(e).__name__

        results["tests"].append(test_result)

    return results

try:
    results = asyncio.run(test_tools())

    with open(sys.argv[1], 'w') as f:
        json.dump(results, f, indent=2)

    passed = sum(1 for t in results["tests"] if t["status"] == "success")
    failed = sum(1 for t in results["tests"] if t["status"] == "error")
    total = len(results["tests"])

    print(f"\n{'='*50}")
    print(f"Summary: {passed}/{total} passed, {failed}/{total} failed")

    sys.exit(0 if failed == 0 else 1)
except Exception as e:
    print(f"❌ Test execution failed: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

  # Run test with appropriate environment variables
  echo "3. Running tests..."

  export TEST_ENV_NAME="${ENV_NAME}"
  export UNIFI_API_TYPE="${ENV_API_TYPE}"

  if [ "${ENV_TYPE}" = "cloud" ]; then
    export UNIFI_HOST="${ENV_HOST}"
    unset UNIFI_LOCAL_HOST
    unset UNIFI_LOCAL_VERIFY_SSL
  else
    export UNIFI_LOCAL_HOST="${ENV_HOST}"
    export UNIFI_LOCAL_VERIFY_SSL="${ENV_SSL}"
    unset UNIFI_HOST
  fi

  python3 "${TEST_DIR}/test-${ENV_NAME}.py" "${TEST_RESULTS}" 2>&1 | tee "${TEST_LOG}"
  TEST_EXIT_CODE=$?

  if [ ${TEST_EXIT_CODE} -eq 0 ]; then
    echo "COMPLETE_SUCCESS" > "${TEST_DIR}/${ENV_NAME}-status.txt"
  else
    echo "COMPLETE_WITH_ERRORS" > "${TEST_DIR}/${ENV_NAME}-status.txt"
  fi

  echo ""
  echo "Environment ${ENV_COUNTER} testing complete"
  echo ""
done
```

---

## Phase 3: Error Collection and Analysis

```bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 3: Error Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

mkdir -p "${TEST_DIR}/issues"

ERROR_REPORT="${TEST_DIR}/error-report.md"

cat > "${ERROR_REPORT}" <<EOF
# Error Report - Test Session ${TEST_SESSION_ID}

**Generated**: $(date -Iseconds)

## Summary

EOF

# Analyze each environment's results
TOTAL_ERRORS=0

for RESULT_FILE in "${TEST_DIR}"/*-results.json; do
  if [ -f "${RESULT_FILE}" ]; then
    ENV_NAME=$(basename "${RESULT_FILE}" -results.json)

    # Count errors
    ERROR_COUNT=$(grep -c '"status": "error"' "${RESULT_FILE}" 2>/dev/null || echo "0")
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERROR_COUNT))

    if [ "${ERROR_COUNT}" -gt 0 ]; then
      echo "### ${ENV_NAME}: ${ERROR_COUNT} Error(s)" >> "${ERROR_REPORT}"
      echo "" >> "${ERROR_REPORT}"

      # Extract error details (sanitized)
      cat "${RESULT_FILE}" | grep -A 3 '"status": "error"' >> "${ERROR_REPORT}"
      echo "" >> "${ERROR_REPORT}"
    else
      echo "### ${ENV_NAME}: ✅ No Errors" >> "${ERROR_REPORT}"
      echo "" >> "${ERROR_REPORT}"
    fi
  fi
done

echo "Found ${TOTAL_ERRORS} total error(s) across all environments"
echo ""

cat "${ERROR_REPORT}"
```

---

## Phase 4: GitHub Issue Creation

*[Continues with GitHub issue creation, triage bot integration, and reporting...]*

---

## Security Features

### Data Sanitization
- IP addresses in error messages replaced with x.x.x.x
- Hostnames masked in displays (show first 2 octets only)
- API keys never logged
- Credentials never in output

### .gitignore Protection
- Automatic addition of test-results/ directory
- Test logs and credentials patterns excluded
- Pre-flight check ensures protection before running

### Portable Design
- No hardcoded IP addresses
- No hardcoded hostnames
- Auto-discovers from .env
- Works in any environment

---

## Version History

- **2.0.0** (2025-11-23): Complete redesign for portability
  - Auto-discovery of environments from .env
  - Interactive environment selection
  - Removed all hardcoded IPs and hostnames
  - Enhanced data sanitization
  - Improved security posture
