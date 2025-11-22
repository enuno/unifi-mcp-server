---
name: refactor-assistant
description: Use this skill when refactoring code for better testability, maintainability, or performance. Provides guidance on identifying code smells, suggesting refactoring strategies, and preserving functionality while improving code structure. Particularly useful when improving test coverage for existing modules.
---

# Refactor Assistant Skill

## Purpose
Guide code refactoring to improve testability, maintainability, and code quality while preserving functionality. This skill helps identify refactoring opportunities, suggests improvement strategies, and ensures safe refactoring practices for the UniFi MCP Server codebase.

## When to Use This Skill
- Module has low test coverage (<40%) and is hard to test
- Code is difficult to understand or maintain
- Functions are too long or complex
- Duplicate code across multiple modules
- Poor separation of concerns
- Preparing code for new features
- Performance optimization needed
- Async/await patterns need improvement

## Phase 1: Analyze Current Code

### Step 1: Identify Refactoring Target

Ask the user what needs refactoring:

**Common Scenarios:**
1. "This module has low test coverage" → Focus on testability
2. "This function is too complex" → Focus on simplification
3. "There's duplicate code" → Focus on DRY (Don't Repeat Yourself)
4. "Performance is slow" → Focus on optimization
5. "Adding new feature is hard" → Focus on extensibility

**Gather Context:**
- Which file/function needs refactoring?
- What specific problems are you experiencing?
- What's the current test coverage?
- Are there any failing tests?
- What's the performance baseline?

### Step 2: Load and Analyze Code

Read the target file and analyze:

**Code Smell Detection:**
- [ ] **Long functions** (>50 lines)
- [ ] **Deep nesting** (>3 levels)
- [ ] **Too many parameters** (>5 parameters)
- [ ] **Duplicate code** (same logic in multiple places)
- [ ] **Magic numbers/strings** (hardcoded values)
- [ ] **Global state** (mutable globals)
- [ ] **Tight coupling** (hard to mock dependencies)
- [ ] **Inconsistent error handling**
- [ ] **Missing type hints**
- [ ] **Poor async patterns** (blocking operations in async code)

**Example Analysis:**
```python
# Before: Hard to test function
async def process_device_data(site_id: str):
    # Code smell: Hardcoded UniFi client
    client = UniFiClient(api_key=os.getenv("UNIFI_API_KEY"))

    # Code smell: Long function with multiple responsibilities
    devices = await client.request("GET", f"/api/s/{site_id}/stat/device")

    # Code smell: Duplicate logic
    for device in devices["data"]:
        if device.get("state") == 1:
            online_devices.append(device)

    # Code smell: Mixed concerns (data fetching + processing)
    stats = {
        "total": len(devices["data"]),
        "online": len(online_devices),
        "offline": len(devices["data"]) - len(online_devices)
    }

    # Code smell: Direct file I/O in business logic
    with open("device_stats.json", "w") as f:
        json.dump(stats, f)

    return stats
```

### Step 3: Measure Current State

Establish baseline metrics:

```bash
# Test coverage
pytest tests/unit/test_[module].py --cov=src/tools/[module] --cov-report=term

# Complexity (if available)
radon cc src/tools/[module].py -a

# Line count
wc -l src/tools/[module].py
```

**Document Baseline:**
- Current test coverage: X%
- Function length: Y lines
- Cyclomatic complexity: Z
- Number of dependencies: N

## Phase 2: Plan Refactoring Strategy

### Refactoring Patterns

**Pattern 1: Extract Function**

Break long functions into smaller, focused functions:

```python
# Before: Long function
async def process_devices(site_id: str):
    devices = await fetch_devices(site_id)
    online = filter_online_devices(devices)
    stats = calculate_stats(devices, online)
    save_stats(stats)
    return stats

# After: Extracted functions
async def fetch_devices(site_id: str) -> List[dict]:
    """Fetch devices from UniFi API."""
    result = await unifi_client.request("GET", f"/api/s/{site_id}/stat/device")
    return result["data"]

def filter_online_devices(devices: List[dict]) -> List[dict]:
    """Filter for online devices only."""
    return [d for d in devices if d.get("state") == 1]

def calculate_stats(devices: List[dict], online: List[dict]) -> dict:
    """Calculate device statistics."""
    return {
        "total": len(devices),
        "online": len(online),
        "offline": len(devices) - len(online)
    }

async def process_devices(site_id: str) -> dict:
    """Process device data and generate statistics."""
    devices = await fetch_devices(site_id)
    online = filter_online_devices(devices)
    stats = calculate_stats(devices, online)
    return stats
```

**Benefits:**
- Each function has single responsibility
- Easy to test independently
- Reusable components
- Clear function names document intent

**Pattern 2: Dependency Injection**

Make dependencies explicit for easier testing:

```python
# Before: Hard to test (hardcoded dependency)
async def get_devices(site_id: str):
    client = UniFiClient(api_key=os.getenv("UNIFI_API_KEY"))
    return await client.request("GET", f"/api/s/{site_id}/stat/device")

# After: Easy to test (injected dependency)
async def get_devices(
    site_id: str,
    client: UniFiClient = None
) -> List[dict]:
    """Get devices from UniFi API."""
    client = client or get_default_client()
    result = await client.request("GET", f"/api/s/{site_id}/stat/device")
    return result["data"]

# Test becomes trivial:
async def test_get_devices():
    mock_client = AsyncMock()
    mock_client.request.return_value = {"data": [...]}
    devices = await get_devices("default", client=mock_client)
    assert devices is not None
```

**Pattern 3: Extract Constants**

Replace magic numbers/strings with named constants:

```python
# Before: Magic numbers
if device["state"] == 1:
    status = "online"
elif device["state"] == 0:
    status = "offline"

# After: Named constants
DEVICE_STATE_ONLINE = 1
DEVICE_STATE_OFFLINE = 0

if device["state"] == DEVICE_STATE_ONLINE:
    status = "online"
elif device["state"] == DEVICE_STATE_OFFLINE:
    status = "offline"
```

**Pattern 4: Replace Conditional with Polymorphism**

Use strategy pattern for complex conditionals:

```python
# Before: Complex conditional
def process_device(device: dict):
    if device["type"] == "uap":
        return process_access_point(device)
    elif device["type"] == "usw":
        return process_switch(device)
    elif device["type"] == "ugw":
        return process_gateway(device)
    # ... many more types

# After: Strategy pattern
class DeviceProcessor:
    def process(self, device: dict):
        raise NotImplementedError

class AccessPointProcessor(DeviceProcessor):
    def process(self, device: dict):
        # AP-specific logic
        pass

class SwitchProcessor(DeviceProcessor):
    def process(self, device: dict):
        # Switch-specific logic
        pass

PROCESSORS = {
    "uap": AccessPointProcessor(),
    "usw": SwitchProcessor(),
    "ugw": GatewayProcessor()
}

def process_device(device: dict):
    processor = PROCESSORS.get(device["type"])
    if not processor:
        raise ValueError(f"Unknown device type: {device['type']}")
    return processor.process(device)
```

**Pattern 5: Simplify Async Patterns**

Improve async/await usage:

```python
# Before: Inefficient sequential execution
async def get_all_data(site_id: str):
    devices = await get_devices(site_id)
    clients = await get_clients(site_id)
    networks = await get_networks(site_id)
    return devices, clients, networks

# After: Efficient parallel execution
import asyncio

async def get_all_data(site_id: str):
    devices, clients, networks = await asyncio.gather(
        get_devices(site_id),
        get_clients(site_id),
        get_networks(site_id)
    )
    return devices, clients, networks
```

## Phase 3: Safe Refactoring Process

### Refactoring Workflow

**Step 1: Ensure Tests Exist**

Before refactoring, ensure tests cover current behavior:

```bash
# Run tests to establish baseline
pytest tests/unit/test_[module].py -v

# If no tests exist, write minimal tests first
# (Use test-strategy skill for guidance)
```

**Step 2: Refactor Incrementally**

Make small, focused changes:

1. **One pattern at a time** - Don't mix refactoring types
2. **Test after each change** - Ensure tests still pass
3. **Commit frequently** - Easy to rollback if needed

**Example Incremental Refactoring:**
```bash
# Step 1: Extract one function
# - Extract fetch_devices()
# - Run tests → pass ✅
# - Commit: "refactor: extract fetch_devices function"

# Step 2: Extract another function
# - Extract filter_online_devices()
# - Run tests → pass ✅
# - Commit: "refactor: extract filter_online_devices function"

# Step 3: Add type hints
# - Add type hints to extracted functions
# - Run mypy → pass ✅
# - Commit: "refactor: add type hints to device functions"
```

**Step 3: Improve Test Coverage**

After refactoring, add tests for new functions:

```python
# New tests for extracted functions
async def test_fetch_devices():
    """Test device fetching in isolation."""
    mock_client = AsyncMock()
    mock_client.request.return_value = {"data": [{"id": "1"}]}

    devices = await fetch_devices("default", client=mock_client)

    assert len(devices) == 1
    assert devices[0]["id"] == "1"

def test_filter_online_devices():
    """Test filtering logic in isolation."""
    devices = [
        {"id": "1", "state": 1},  # Online
        {"id": "2", "state": 0},  # Offline
        {"id": "3", "state": 1}   # Online
    ]

    online = filter_online_devices(devices)

    assert len(online) == 2
    assert all(d["state"] == 1 for d in online)
```

**Step 4: Verify Improvement**

Measure improvements:

```bash
# Coverage improved?
pytest tests/unit/test_[module].py --cov=src/tools/[module] --cov-report=term

# Complexity reduced?
radon cc src/tools/[module].py -a

# All quality checks pass?
black src/tools/[module].py
isort src/tools/[module].py
ruff check src/tools/[module].py
mypy src/tools/[module].py
```

## Phase 4: Common Refactoring Scenarios

### Scenario 1: Improve Testability

**Problem**: Function is hard to test due to tight coupling

**Solution**: Apply dependency injection

```python
# Before
async def tool_function(site_id: str):
    client = UniFiClient.from_env()  # Tight coupling
    result = await client.request("GET", endpoint)
    return result["data"]

# After
async def tool_function(
    site_id: str,
    client: UniFiClient = None
):
    client = client or UniFiClient.from_env()  # Injected dependency
    result = await client.request("GET", endpoint)
    return result["data"]
```

### Scenario 2: Reduce Complexity

**Problem**: Function does too many things

**Solution**: Extract functions with single responsibility

```python
# Before: One complex function
async def create_network_with_validation(
    site_id: str,
    name: str,
    vlan_id: int,
    ip_subnet: str
):
    # Validation
    if not name:
        raise ValueError("Name required")
    if not 1 <= vlan_id <= 4094:
        raise ValueError("Invalid VLAN ID")
    if not is_valid_subnet(ip_subnet):
        raise ValueError("Invalid subnet")

    # Check duplicates
    networks = await list_networks(site_id)
    if any(n["name"] == name for n in networks):
        raise ValueError("Network name exists")

    # Create network
    payload = {
        "name": name,
        "vlan": vlan_id,
        "ip_subnet": ip_subnet
    }
    result = await unifi_client.request("POST", endpoint, json=payload)
    return result["data"]

# After: Separated concerns
def validate_network_params(name: str, vlan_id: int, ip_subnet: str):
    """Validate network parameters."""
    if not name:
        raise ValueError("Name required")
    if not 1 <= vlan_id <= 4094:
        raise ValueError("Invalid VLAN ID")
    if not is_valid_subnet(ip_subnet):
        raise ValueError("Invalid subnet")

async def check_network_name_unique(site_id: str, name: str):
    """Check if network name is unique."""
    networks = await list_networks(site_id)
    if any(n["name"] == name for n in networks):
        raise ValueError(f"Network '{name}' already exists")

async def create_network_with_validation(
    site_id: str,
    name: str,
    vlan_id: int,
    ip_subnet: str
):
    """Create network with validation."""
    validate_network_params(name, vlan_id, ip_subnet)
    await check_network_name_unique(site_id, name)

    payload = {"name": name, "vlan": vlan_id, "ip_subnet": ip_subnet}
    result = await unifi_client.request("POST", endpoint, json=payload)
    return result["data"]
```

### Scenario 3: Eliminate Duplication

**Problem**: Same code pattern repeated across modules

**Solution**: Extract to utility function

```python
# Before: Duplicated in clients.py, devices.py, networks.py
async def get_clients(site_id: str):
    result = await client.request("GET", f"/api/s/{site_id}/rest/user")
    if not result.get("data"):
        return []
    return result["data"]

async def get_devices(site_id: str):
    result = await client.request("GET", f"/api/s/{site_id}/stat/device")
    if not result.get("data"):
        return []
    return result["data"]

# After: Extract common pattern to utility
async def get_unifi_data(endpoint: str, default=None):
    """Generic helper to fetch UniFi data."""
    result = await client.request("GET", endpoint)
    return result.get("data", default or [])

async def get_clients(site_id: str):
    return await get_unifi_data(f"/api/s/{site_id}/rest/user")

async def get_devices(site_id: str):
    return await get_unifi_data(f"/api/s/{site_id}/stat/device")
```

### Scenario 4: Performance Optimization

**Problem**: Slow performance due to sequential operations

**Solution**: Use asyncio.gather for parallel execution

```python
# Before: Slow sequential execution
async def get_site_overview(site_id: str):
    devices = await get_devices(site_id)  # 200ms
    clients = await get_clients(site_id)  # 200ms
    networks = await get_networks(site_id) # 200ms
    # Total: 600ms

# After: Fast parallel execution
async def get_site_overview(site_id: str):
    devices, clients, networks = await asyncio.gather(
        get_devices(site_id),
        get_clients(site_id),
        get_networks(site_id)
    )
    # Total: ~200ms
```

## Phase 5: Refactoring Checklist

### Pre-Refactoring Checklist
- [ ] Tests exist and pass
- [ ] Coverage baseline documented
- [ ] Complexity baseline documented
- [ ] Changes committed (clean working directory)
- [ ] Refactoring goal clearly defined

### During Refactoring
- [ ] Make one change at a time
- [ ] Run tests after each change
- [ ] Commit frequently with clear messages
- [ ] Preserve functionality (no behavior changes)
- [ ] Add tests for extracted functions
- [ ] Update type hints
- [ ] Update docstrings

### Post-Refactoring Checklist
- [ ] All tests pass
- [ ] Coverage improved (or maintained)
- [ ] Complexity reduced
- [ ] Code quality checks pass (black, isort, ruff, mypy)
- [ ] Documentation updated if public API changed
- [ ] Performance not degraded

## Phase 6: Risk Management

### Low-Risk Refactorings (Safe)
- Extract constants
- Rename variables/functions
- Add type hints
- Add docstrings
- Format code (black, isort)
- Extract pure functions

### Medium-Risk Refactorings (Caution)
- Extract functions with side effects
- Change function signatures
- Refactor async patterns
- Extract classes
- Merge duplicate code

### High-Risk Refactorings (Careful)
- Change data structures
- Modify error handling
- Change API contracts
- Large-scale restructuring
- Change caching behavior

**Risk Mitigation:**
- High-risk refactorings require comprehensive tests first
- Use feature flags for gradual rollout
- Maintain backward compatibility
- Have rollback plan ready

## Integration with Other Skills

- **Before refactoring**: Use `test-strategy` to ensure test coverage
- **During refactoring**: Use this skill for guidance
- **After refactoring**: Use `test-strategy` to improve coverage further
- **Quality checks**: Use `/lint`, `/format`, `/test` commands
- **Design review**: Use `tool-design-reviewer` if changing public APIs

## Reference Files

Load for context:
- `src/tools/[module].py` - Code to refactor
- `tests/unit/test_[module].py` - Existing tests
- `AGENTS.md` - Code quality standards
- `pyproject.toml` - Tool configurations (black, ruff, mypy)

## Success Metrics

Refactoring successful when:
- [ ] All tests pass
- [ ] Coverage increased (or maintained at high level)
- [ ] Complexity reduced (lower cyclomatic complexity)
- [ ] Code is easier to understand
- [ ] Functions are smaller and more focused
- [ ] No duplicate code
- [ ] Type hints complete
- [ ] Quality checks pass
- [ ] Performance not degraded (or improved)