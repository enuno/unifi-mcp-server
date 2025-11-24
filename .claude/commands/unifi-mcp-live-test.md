---
description: Test UniFi MCP server across discovered environments, create GitHub issues for failures, and trigger @claude automated fix workflow
allowed-tools:
  - Read
  - Write
  - AskUserQuestion
  - Bash(git:*)
  - Bash(gh:*)
  - Bash(python:*)
  - Bash(python3:*)
  - Bash(uv:*)
  - Bash(curl:*)
  - Bash(grep:*)
  - Bash(find:*)
  - Bash(sleep:*)
  - Bash(date:*)
  - Bash(wc:*)
  - Bash(cat:*)
  - Bash(jq:*)
author: project
version: 3.0.0
---

# UniFi MCP Server - Live Environment Testing & Automated Remediation

## Purpose
Automatically discover UniFi environments from `.env`, execute comprehensive tests, sanitize results, create GitHub issues for bugs, and automatically instruct the `@claude` bot to develop and submit fixes via PRs.

**Key Features:**
- ✅ **Portable:** No hardcoded IPs/hostnames; auto-discovers from `.env`.
- ✅ **Secure:** Masks credentials and sanitizes IP addresses in logs.
- ✅ **Interactive:** Prompts user to select which discovered environments to test.
- ✅ **Automated Remediation:** Creates GitHub issues, waits for Triage Bot, and assigns `@claude` to fix, test, and PR.

---

## Phase 1: Pre-Flight Checks and Environment Discovery

### 1.1 Verify Prerequisites

```bash
echo "╔════════════════════════════════════════════════════╗"
echo "║   UNIFI MCP LIVE TEST & REMEDIATION - STARTING     ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Check Node.js
if command -v node &> /dev/null; then
  echo "✅ Node.js: $(node --version)"
else
  echo "❌ Node.js not installed"
  exit 1
fi

# Check Python/UV
if command -v python3 &> /dev/null; then
  echo "✅ Python: $(python3 --version | head -1)"
else
  echo "❌ Python3 not installed"
  exit 1
fi

# Check GitHub CLI (Critical for Phase 4 & 5)
if command -v gh &> /dev/null; then
  echo "✅ GitHub CLI: $(gh --version | head -1)"
  gh auth status &> /dev/null || { echo "❌ GitHub CLI not authenticated. Run 'gh auth login' first."; exit 1; }
else
  echo "❌ GitHub CLI not installed - required for automated remediation"
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
````

### 1.2 Discover Test Environments from .env

```bash
echo "Discovering test environments from .env..."

if [ ! -f .env ]; then
  echo "❌ .env file not found. Please create one based on .env.example."
  exit 1
fi

# Initialize discovery variables
HAS_CLOUD=false
HAS_LOCAL=false
HAS_AUTH=false

# Check Cloud
if grep -q "^UNIFI_HOST=" .env; then
  CLOUD_HOST=$(grep "^UNIFI_HOST=" .env | cut -d= -f2 | tr -d '"' | tr -d "'")
  if [ ! -z "${CLOUD_HOST}" ] && [ "${CLOUD_HOST}" != "your-host-here" ]; then
    echo "✅ Found Cloud API configuration: ${CLOUD_HOST}"
    HAS_CLOUD=true
  fi
fi

# Check Local
if grep -q "^UNIFI_LOCAL_HOST=" .env; then
  LOCAL_HOST=$(grep "^UNIFI_LOCAL_HOST=" .env | cut -d= -f2 | tr -d '"' | tr -d "'")
  if [ ! -z "${LOCAL_HOST}" ] && [ "${LOCAL_HOST}" != "your-host-here" ]; then
    # Get SSL setting
    LOCAL_SSL="false"
    grep -q "^UNIFI_LOCAL_VERIFY_SSL=true" .env && LOCAL_SSL="true"
    echo "✅ Found Local Gateway configuration: ${LOCAL_HOST} (SSL: ${LOCAL_SSL})"
    HAS_LOCAL=true
  fi
fi

# Check Auth
if (grep -q "^UNIFI_API_KEY=" .env && [ $(grep "^UNIFI_API_KEY=" .env | cut -d= -f2 | wc -c) -gt 5 ]) || \
   (grep -q "^UNIFI_USERNAME=" .env && grep -q "^UNIFI_PASSWORD=" .env); then
  echo "✅ Authentication configured"
  HAS_AUTH=true
fi

if [ "${HAS_CLOUD}" = "false" ] && [ "${HAS_LOCAL}" = "false" ]; then
  echo "❌ No valid environments found in .env"
  exit 1
fi

if [ "${HAS_AUTH}" = "false" ]; then
  echo "❌ No valid authentication found in .env"
  exit 1
fi
```

### 1.3 Interactive Selection & Session Setup

```bash
echo ""
echo "Select Environments to Test:"
echo "------------------------------"

ENVS_TO_TEST=()

if [ "${HAS_CLOUD}" = "true" ]; then
  read -p "Test Cloud API? (y/n): " TEST_CLOUD
  if [[ "${TEST_CLOUD}" =~ ^[Yy]$ ]]; then
    ENVS_TO_TEST+=("cloud:${CLOUD_HOST}")
  fi
fi

if [ "${HAS_LOCAL}" = "true" ]; then
  MASKED_IP=$(echo "${LOCAL_HOST}" | awk -F. '{print $1"."$2".x.x"}')
  read -p "Test Local Gateway (${MASKED_IP})? (y/n): " TEST_LOCAL
  if [[ "${TEST_LOCAL}" =~ ^[Yy]$ ]]; then
    ENVS_TO_TEST+=("local:${LOCAL_HOST}:${LOCAL_SSL}")
  fi
fi

if [ ${#ENVS_TO_TEST[@]} -eq 0 ]; then
  echo "❌ No environments selected."
  exit 1
fi

# Create Session
TEST_SESSION_ID=$(date +%Y%m%d-%H%M%S)
TEST_DIR="test-results/${TEST_SESSION_ID}"
mkdir -p "${TEST_DIR}/issues"

# Update .gitignore safely
if ! grep -q "^test-results/" .gitignore 2>/dev/null; then
  echo "test-results/" >> .gitignore
  echo "✅ Added test-results/ to .gitignore"
fi

echo "✅ Session ${TEST_SESSION_ID} initialized in ${TEST_DIR}"
```

-----

## Phase 2: Environment Testing

```bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 2: Executing Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create the Python Test Script
cat > "${TEST_DIR}/test_runner.py" <<'PYEOF'
import asyncio
import json
import sys
import os
import re
from datetime import datetime

# Add src to path
sys.path.insert(0, os.getcwd())

async def run_tests():
    from src.config.config import Settings, APIType
    # Import tools - using correct function names that actually exist
    from src.tools import sites, devices, clients, wifi

    try:
        settings = Settings()
    except Exception as e:
        return {"status": "fatal", "error": f"Config load failed: {str(e)}", "tests": []}

    env_name = os.environ.get("TEST_ENV_NAME", "unknown")
    results = {
        "environment": env_name,
        "timestamp": datetime.now().isoformat(),
        "api_type": settings.api_type.value,
        "tests": []
    }

    # Define tools to test (Read-Only)
    # Using default site for tests that require site_id
    # Note: site_manager and some network tools are Cloud API only
    tools = [
        ("list_sites", sites.list_sites, {}),
        ("list_wlans", wifi.list_wlans, {"site_id": settings.default_site}),
        ("list_active_clients", clients.list_active_clients, {"site_id": settings.default_site}),
        ("search_devices", devices.search_devices, {"site_id": settings.default_site, "query": ""}),
    ]

    # Add Cloud-specific tests
    if settings.api_type == APIType.CLOUD:
        from src.tools import site_manager, networks
        tools.extend([
            ("list_all_sites", site_manager.list_all_sites_aggregated, {}),
            ("list_vlans", networks.list_vlans, {}),
        ])

    for tool_name, func, params in tools:
        print(f"Testing {tool_name}...", end=" ", flush=True)
        t_res = {"tool": tool_name, "params": params, "status": "unknown"}
        
        try:
            start = asyncio.get_event_loop().time()
            res = await func(settings=settings, **params)
            duration = (asyncio.get_event_loop().time() - start) * 1000
            
            print(f"✅ ({int(duration)}ms)")
            t_res["status"] = "success"
            t_res["duration_ms"] = round(duration, 1)
            
        except Exception as e:
            err_msg = str(e)
            # Sanitize IPs
            err_msg = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', 'x.x.x.x', err_msg)
            print(f"❌ {err_msg}")
            t_res["status"] = "error"
            t_res["error"] = err_msg
            t_res["error_type"] = type(e).__name__
            
        results["tests"].append(t_res)

    return results

if __name__ == "__main__":
    try:
        output = asyncio.run(run_tests())
        with open(sys.argv[1], 'w') as f:
            json.dump(output, f, indent=2)
    except Exception as e:
        print(f"Fatal runner error: {e}")
        sys.exit(1)
PYEOF

# Run Tests for each Environment
for ENV_CONFIG in "${ENVS_TO_TEST[@]}"; do
  IFS=':' read -ra PARTS <<< "${ENV_CONFIG}"
  TYPE="${PARTS[0]}"
  HOST="${PARTS[1]}"
  
  if [ "$TYPE" == "cloud" ]; then
    NAME="Cloud_API"
    export UNIFI_API_TYPE="cloud"
    export UNIFI_HOST="$HOST"
    unset UNIFI_LOCAL_HOST
  else
    NAME="Local_Gateway"
    SSL="${PARTS[2]}"
    export UNIFI_API_TYPE="local"
    export UNIFI_LOCAL_HOST="$HOST"
    export UNIFI_LOCAL_VERIFY_SSL="$SSL"
    unset UNIFI_HOST
  fi
  
  export TEST_ENV_NAME="$NAME"
  RESULTS_FILE="${TEST_DIR}/${NAME}-results.json"
  
  echo "--> Testing Environment: $NAME ($HOST)"
  
  # Check Connectivity
  if [ "$TYPE" == "cloud" ]; then URL="https://$HOST"; else URL="https://$HOST"; fi
  OPTS=""
  [ "$SSL" == "false" ] && OPTS="-k"
  
  if curl $OPTS -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$URL" | grep -qE "200|401|403"; then
     python3 "${TEST_DIR}/test_runner.py" "$RESULTS_FILE"
  else
     echo "❌ Connectivity failed to $HOST. Skipping tools test."
     echo '{"tests": [], "status": "connectivity_fail"}' > "$RESULTS_FILE"
  fi
  echo ""
done
```

-----

## Phase 3: Error Analysis & GitHub Issue Creation

```bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 3 & 4: Analysis & Automated Issue Creation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Ensure clean slate for created issues list
> "${TEST_DIR}/issues/created_ids.txt"

# Iterate over all result files
for RESULT_FILE in "${TEST_DIR}"/*-results.json; do
  [ -e "$RESULT_FILE" ] || continue
  
  ENV_NAME=$(basename "$RESULT_FILE" -results.json)
  
  # Extract errors using jq (requires jq, fallback to grep if needed, but jq is safer)
  # We assume jq is available as per allowed-tools, or we use a python one-liner helper
  
  python3 -c "
import json, sys, os
try:
    with open('$RESULT_FILE') as f: data = json.load(f)
    tests = data.get('tests', [])
    for t in tests:
        if t['status'] == 'error':
            print(f\"{t['tool']}|{t['error']}\")
except: pass
" | while IFS='|' read -r TOOL ERROR_MSG; do
  
    echo "⚠️  Bug detected: $TOOL in $ENV_NAME"
    
    # Check for existing duplicate issues
    SEARCH_QUERY="[Bug] $TOOL fails on $ENV_NAME in:title state:open label:mcp-testing"
    EXISTING=$(gh issue list --search "$SEARCH_QUERY" --json number --jq '.[0].number')
    
    if [ ! -z "$EXISTING" ]; then
      echo "   ⏭️  Issue already exists: #$EXISTING. Skipping."
    else
      # Create New Issue
      TITLE="[Bug] $TOOL fails on $ENV_NAME"
      BODY="## Bug Description
The MCP tool \`$TOOL\` failed when tested against **$ENV_NAME**.

## Error Message
\`\`\`
$ERROR_MSG
\`\`\`

## Metadata
- **Session:** $TEST_SESSION_ID
- **Environment:** $ENV_NAME
- **Date:** $(date)

**Automated Report via Unifi MCP Live Test**"

      echo "   📝 Creating GitHub Issue..."
      NEW_ISSUE_URL=$(gh issue create --title "$TITLE" --body "$BODY" --label "bug,mcp-testing,automated,needs-triage" --json url --jq '.url')
      NEW_ISSUE_NUM=$(basename "$NEW_ISSUE_URL")
      
      echo "   ✅ Created Issue #$NEW_ISSUE_NUM"
      echo "$NEW_ISSUE_NUM" >> "${TEST_DIR}/issues/created_ids.txt"
    fi
  done
done
```

-----

## Phase 4: Triage Bot Integration & Claude Assignment

```bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 5: Triage & remediation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ! -s "${TEST_DIR}/issues/created_ids.txt" ]; then
  echo "✅ No new issues created. Skipping triage workflow."
else
  ISSUE_COUNT=$(wc -l < "${TEST_DIR}/issues/created_ids.txt")
  echo "⏳ Waiting 60 seconds for Triage Bot to analyze $ISSUE_COUNT new issue(s)..."
  sleep 60
  
  while read ISSUE_NUM; do
    echo "Processing Issue #$ISSUE_NUM..."
    
    # Check for Triage Bot response
    # We look for comments from typical bot names
    BOT_RESPONDED=$(gh issue view "$ISSUE_NUM" --json comments --jq '.comments[] | select(.author.login == "github-actions[bot]" or .author.login == "claude-triage-bot") | .body' | wc -l)
    
    if [ "$BOT_RESPONDED" -gt 0 ]; then
       echo "   ✅ Triage Bot has responded."
       
       # INSTRUCTION STEP: Assign to @claude with specific prompt
       echo "   🤖 Assigning to @claude for fix..."
       
       PROMPT="**ACTION REQUIRED** @claude
       
Please handle this issue following this workflow:
1. **Create a Branch**: Create a new git branch dedicated to this issue.
2. **Develop Fix**: Analyze the error log above and implement a fix in the code.
3. **Test**: Verify the fix works.
4. **Submit PR**: Submit a Pull Request for human review and merging.

Status: Ready for development."

       # Post the instruction comment
       gh issue comment "$ISSUE_NUM" --body "$PROMPT"
       
       # Attempt assignment (may fail depending on org permissions, but comment triggers the bot)
       gh issue edit "$ISSUE_NUM" --add-assignee "claude" 2>/dev/null || true
       
       echo "   🚀 Remediation workflow triggered for #$ISSUE_NUM"
    else
       echo "   ⚠️  No Triage Bot response detected yet. Skipping auto-assignment."
    fi
    
  done < "${TEST_DIR}/issues/created_ids.txt"
fi
```

-----

## Phase 5: Summary Report

```bash
echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║             TEST SESSION COMPLETE                  ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "Session ID: $TEST_SESSION_ID"
echo "Artifacts:  $TEST_DIR"
echo ""
echo "Issues Created:"
if [ -s "${TEST_DIR}/issues/created_ids.txt" ]; then
  cat "${TEST_DIR}/issues/created_ids.txt" | while read id; do echo " - #$id (Remediation Triggered)"; done
else
  echo " - None"
fi
echo ""
