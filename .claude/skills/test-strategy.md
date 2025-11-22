---
name: test-strategy
description: Use this skill when you need to improve test coverage for a specific module or implement tests for untested code. The skill analyzes coverage gaps, suggests specific test scenarios, and guides through test-driven development workflows for the UniFi MCP Server project.
---

# Test Strategy Skill

## Purpose
Guide the creation of high-quality tests for UniFi MCP Server modules to achieve the 60-70% coverage target outlined in TEST_COVERAGE_ROADMAP.md. This skill provides intelligent test recommendations based on coverage analysis, UniFi API patterns, and existing test infrastructure.

## When to Use This Skill
- Implementing Sprint 1-4 of TEST_COVERAGE_ROADMAP.md
- A module has coverage below 70%
- Writing tests for new tools or features
- Need guidance on what test scenarios to write
- Unsure how to mock UniFi API responses
- Want to follow TDD (Test-Driven Development) approach

## Phase 1: Coverage Analysis

### Step 1: Identify Target Module
Ask the user which module they want to improve, or analyze recent coverage reports to recommend priorities.

**Priority Modules (from TEST_COVERAGE_ROADMAP.md Sprint 1):**
- `src/tools/clients.py` - Currently 15.91%, Target: 70%
- `src/tools/networks.py` - Currently 19.83%, Target: 70%
- `src/tools/sites.py` - Currently 25.00%, Target: 70%

### Step 2: Analyze Current Coverage
Run coverage analysis to identify:
- Uncovered lines
- Untested code paths
- Missing edge case tests
- Functions with no tests

```bash
pytest tests/unit/test_[module].py --cov=src/tools/[module] --cov-report=term-missing
```

### Step 3: Categorize Missing Tests
Classify untested code into categories:
- **Happy path tests** - Normal operation scenarios
- **Error handling tests** - Exception and error cases
- **Edge case tests** - Boundary conditions, empty inputs, null values
- **Integration tests** - API client interactions
- **Async behavior tests** - Proper async/await handling

## Phase 2: Test Scenario Design

### Design Principles
Based on existing tests in the codebase:

1. **Use pytest fixtures** - Leverage conftest.py fixtures
2. **Mock UniFi API responses** - Don't call real API in unit tests
3. **Test async functions** - Use pytest.mark.asyncio
4. **Validate Pydantic models** - Test data validation
5. **Test error handling** - Ensure proper exceptions raised
6. **Test caching** - If Redis caching enabled
7. **Test safety mechanisms** - confirm=True, dry_run=True flags

### Test Template Structure

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.tools.[module] import [function_name]
from src.models.[model] import [Model]

@pytest.mark.asyncio
@pytest.mark.unit
async def test_[function_name]_success(mock_unifi_client):
    """Test [function_name] with valid inputs - happy path."""
    # Arrange
    mock_unifi_client.request.return_value = {
        "data": [...]  # Mock API response
    }

    # Act
    result = await [function_name](
        site_id="default",
        param="value"
    )

    # Assert
    assert result is not None
    assert isinstance(result, list)
    mock_unifi_client.request.assert_called_once_with(
        "GET",
        "/api/s/default/endpoint",
        params={"param": "value"}
    )

@pytest.mark.asyncio
@pytest.mark.unit
async def test_[function_name]_handles_api_error(mock_unifi_client):
    """Test [function_name] handles API errors gracefully."""
    # Arrange
    mock_unifi_client.request.side_effect = Exception("API Error")

    # Act & Assert
    with pytest.raises(Exception, match="API Error"):
        await [function_name](site_id="default")

@pytest.mark.asyncio
@pytest.mark.unit
async def test_[function_name]_validates_inputs():
    """Test [function_name] validates input parameters."""
    # Test invalid inputs
    with pytest.raises(ValueError):
        await [function_name](site_id="")  # Empty site_id
```

### Common Mock API Response Patterns

**Device List Response:**
```python
{
    "data": [
        {
            "_id": "device-id-123",
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "Test Device",
            "type": "uap",
            "state": 1,
            "model": "U6-Lite"
        }
    ]
}
```

**Client List Response:**
```python
{
    "data": [
        {
            "_id": "client-id-456",
            "mac": "11:22:33:44:55:66",
            "hostname": "test-client",
            "ip": "192.168.1.100",
            "network_id": "network-123"
        }
    ]
}
```

**Network List Response:**
```python
{
    "data": [
        {
            "_id": "network-789",
            "name": "LAN",
            "purpose": "corporate",
            "vlan": 1,
            "ip_subnet": "192.168.1.0/24"
        }
    ]
}
```

## Phase 3: Test Implementation Guidance

### Step 1: Create Test File Structure
If test file doesn't exist, create it:

```python
"""Unit tests for [module] tools."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.tools.[module] import (
    function1,
    function2,
    function3
)

# Test class organization
class TestFunction1:
    """Tests for function1."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success(self, mock_unifi_client):
        """Test successful execution."""
        pass

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_error_handling(self, mock_unifi_client):
        """Test error handling."""
        pass
```

### Step 2: Implement Tests Incrementally
Follow TDD cycle:
1. **Red** - Write failing test
2. **Green** - Make test pass
3. **Refactor** - Improve code while keeping tests passing

Run tests frequently:
```bash
pytest tests/unit/test_[module].py -v
```

### Step 3: Verify Coverage Improvement
After implementing tests, verify coverage increased:

```bash
pytest tests/unit/test_[module].py --cov=src/tools/[module] --cov-report=term-missing --cov-report=html
```

Check HTML report for detailed line-by-line coverage:
```bash
open htmlcov/index.html
```

## Phase 4: Test Quality Checklist

Before marking tests complete, verify:

- [ ] All functions have at least one test
- [ ] Happy path scenarios covered
- [ ] Error handling tested
- [ ] Edge cases tested (empty inputs, None values, invalid types)
- [ ] Async behavior tested correctly (await, asyncio patterns)
- [ ] Pydantic model validation tested
- [ ] Mock API responses realistic and complete
- [ ] Tests follow existing conventions (pytest.mark.unit, async patterns)
- [ ] Test names are descriptive
- [ ] Coverage increased by at least 40-50 percentage points
- [ ] All tests pass: `pytest tests/unit/test_[module].py -v`
- [ ] No linting errors: `ruff check tests/unit/test_[module].py`
- [ ] Formatted correctly: `black tests/unit/test_[module].py`

## Phase 5: Sprint Progress Tracking

### Sprint 1 (Weeks 1-2) - Foundation Modules
**Target**: 40-50% coverage increase per module

- [ ] `src/tools/clients.py` (15.91% → 70%)
  - [ ] list_clients test scenarios
  - [ ] get_client test scenarios
  - [ ] search_clients test scenarios
  - [ ] get_client_statistics test scenarios
- [ ] `src/tools/networks.py` (19.83% → 70%)
  - [ ] list_networks test scenarios
  - [ ] get_network test scenarios
  - [ ] get_network_statistics test scenarios
- [ ] `src/tools/sites.py` (25.00% → 70%)
  - [ ] list_sites test scenarios
  - [ ] get_site test scenarios
  - [ ] get_site_statistics test scenarios

### Sprint 2-4
See TEST_COVERAGE_ROADMAP.md for full sprint details.

## Reference Files

Load these files for context when needed:

- `TEST_COVERAGE_ROADMAP.md` - Sprint plan and coverage targets
- `tests/conftest.py` - Pytest fixtures and configuration
- `tests/unit/test_zbf_tools.py` - Example of high-coverage tests (84.13%)
- `tests/unit/test_traffic_flow_tools.py` - Example of comprehensive tests (86.62%)
- `AGENTS.md` - Testing requirements and standards
- `pyproject.toml` - Pytest configuration and coverage settings

## Common Testing Patterns

### Mocking UniFi API Client

```python
@pytest.fixture
def mock_unifi_client():
    """Mock UniFi API client for testing."""
    client = AsyncMock()
    client.request = AsyncMock()
    return client
```

### Testing Cached Responses

```python
@pytest.mark.asyncio
async def test_caching_behavior(mock_unifi_client, mock_cache):
    """Test that responses are cached correctly."""
    # First call - should hit API
    result1 = await function(site_id="default")
    mock_unifi_client.request.assert_called_once()

    # Second call - should use cache
    result2 = await function(site_id="default")
    mock_unifi_client.request.assert_called_once()  # Still once

    assert result1 == result2
```

### Testing Safety Mechanisms

```python
@pytest.mark.asyncio
async def test_requires_confirmation(mock_unifi_client):
    """Test that destructive operations require confirm=True."""
    with pytest.raises(ValueError, match="confirm=True"):
        await delete_something(site_id="default", id="123", confirm=False)
```

## Success Metrics

Track progress toward goals:
- **Module Coverage**: Track coverage % increase
- **Test Count**: Number of new tests added
- **Sprint Progress**: Modules completed per sprint
- **Overall Coverage**: Project-wide coverage trend (36% → 60-70%)

Use `/unifi-mcp-test-coverage` slash command to run coverage analysis and track progress.

## Tips for Effective Testing

1. **Start with the easiest tests first** - Build confidence and momentum
2. **Use existing tests as templates** - Copy patterns from high-coverage modules
3. **Test one thing at a time** - Small, focused tests are better than large complex ones
4. **Mock at the right level** - Mock the UniFi API client, not internal functions
5. **Test behavior, not implementation** - Focus on what the function does, not how
6. **Run tests frequently** - Catch issues early
7. **Use descriptive test names** - Test name should explain what's being tested
8. **Follow AAA pattern** - Arrange, Act, Assert

## Integration with Other Tools

- **Before**: Use `tool-design-reviewer` skill to ensure tool is well-designed for testing
- **During**: Use `/test` slash command to run tests frequently
- **After**: Use `/lint` and `/format` to ensure code quality
- **Documentation**: Use `api-doc-generator` to update docs after adding tests
