# UniFi MCP Server - Testing Coverage Plan

**📋 Version Correction Notice**: v0.2.0 was published prematurely on 2025-11-17. The current stable release is v0.1.4 (identical code). References to "v0.2.0 features" in this document refer to features being developed for the true v0.2.0 release targeted for Q1 2025.

## Executive Summary

This document outlines the comprehensive testing strategy for the UniFi MCP Server, with a focus on achieving 80%+ code coverage across all modules. As of November 2025, significant progress has been made on new v0.2.0 features, with a current overall coverage of **34.10%**.

## Current Status (November 2025)

### Completed ✅

#### Phase 1: New v0.2.0 Models (100% Coverage)

- **File**: `tests/unit/test_new_models.py`
- **Tests**: 36 comprehensive tests
- **Coverage**: 100% for all new models
- **Models Covered**:
  - Zone-Based Firewall (ZBF): `ZonePolicy`, `ApplicationBlockRule`, `ZonePolicyMatrix`, `ZoneNetworkAssignment`
  - Traffic Flows: `TrafficFlow`, `FlowStatistics`, `FlowRisk`, `FlowView`
  - Site Manager: `SiteHealthSummary`, `InternetHealthMetrics`, `CrossSiteStatistics`, `VantagePoint`

#### Phase 2: ZBF Tools & Infrastructure (80%+ Coverage)

- **File**: `tests/unit/test_zbf_tools.py`
- **Tests**: 22 comprehensive tests
- **Coverage**:
  - `firewall_zones.py`: 82.68%
  - `zbf_matrix.py`: 79.47%
- **Infrastructure Added**:
  - Created `audit_action()` async function in `src/utils/audit.py`
  - Enhanced error handling and validation testing
  - Dry-run and confirmation testing patterns

#### Phase 3: Traffic Flow Tools (86%+ Coverage)

- **File**: `tests/unit/test_traffic_flow_tools.py`
- **Tests**: 16 comprehensive tests
- **Coverage**: `traffic_flows.py`: 86.62%
- **Functions Tested**:
  - Traffic flow retrieval with filters
  - Flow statistics and aggregations
  - Top flows analysis
  - Risk assessments
  - Historical trends
  - Complex filtering with fallback logic

### Overall Metrics

```
Total Tests: 179 passing
Overall Coverage: 34.10%
Files with 100% Coverage: 12 (all models)
```

## Remaining Work to Achieve 80% Coverage

### Priority 1: New Feature Tools (Critical)

#### 1.1 Site Manager Tools & Resources

**Estimated Time**: 4-5 hours
**Target Coverage**: 80%+

**Files to Test**:

- `src/api/site_manager_client.py` (0% → 80%)
- `src/tools/site_manager.py` (0% → 80%)
- `src/resources/site_manager.py` (0% → 80%)

**Test File**: `tests/unit/test_site_manager_tools.py`

**Test Scenarios**:

- Multi-site health monitoring
- Cross-site statistics aggregation
- Internet health metrics retrieval
- Vantage point management
- Site-level operations
- Error handling for unavailable endpoints

### Priority 2: Existing Core Tools (Important)

#### 2.1 WiFi Management

**Estimated Time**: 3-4 hours
**Target Coverage**: 75%+

**Files**: `src/tools/wifi.py` (0% → 75%)

**Test File**: `tests/unit/test_wifi_tools.py`

**Test Scenarios**:

- SSID configuration
- WiFi network creation/modification
- Channel management
- WiFi 7 MLO configuration
- Client connection management

#### 2.2 Firewall Management

**Estimated Time**: 3-4 hours
**Target Coverage**: 75%+

**Files**: `src/tools/firewall.py` (4.44% → 75%)

**Test File**: `tests/unit/test_firewall_tools.py`

**Test Scenarios**:

- Firewall rule creation/deletion
- Rule prioritization
- Port-based filtering
- IP-based filtering
- Confirmation and dry-run modes

#### 2.3 Port Forwarding

**Estimated Time**: 2-3 hours
**Target Coverage**: 75%+

**Files**: `src/tools/port_forwarding.py` (0% → 75%)

**Test File**: `tests/unit/test_port_forwarding_tools.py`

**Test Scenarios**:

- Port forward rule creation
- NAT configuration
- Rule validation
- Conflict detection

#### 2.4 Device Control

**Estimated Time**: 2-3 hours
**Target Coverage**: 75%+

**Files**: `src/tools/device_control.py` (6.31% → 75%)

**Test File**: `tests/unit/test_device_control_tools.py`

**Test Scenarios**:

- Device adoption
- Device restart/reboot
- Device upgrade
- LED control
- Locate device

#### 2.5 Network Configuration

**Estimated Time**: 3-4 hours
**Target Coverage**: 75%+

**Files**: `src/tools/network_config.py` (3.72% → 75%)

**Test File**: `tests/unit/test_network_config_tools.py`

**Test Scenarios**:

- VLAN configuration
- DHCP settings
- DNS configuration
- Network object creation

#### 2.6 DPI & Application Control

**Estimated Time**: 3-4 hours
**Target Coverage**: 75%+

**Files**:

- `src/tools/dpi.py` (0% → 75%)
- `src/tools/dpi_tools.py` (0% → 75%)

**Test File**: `tests/unit/test_dpi_tools.py`

**Test Scenarios**:

- DPI statistics retrieval
- Application identification
- Traffic categorization
- Application blocking

#### 2.7 Additional Tools

**Estimated Time**: 4-5 hours
**Target Coverage**: 70%+

**Files**:

- `src/tools/acls.py` (0% → 70%)
- `src/tools/vouchers.py` (0% → 70%)
- `src/tools/wans.py` (0% → 70%)
- `src/tools/client_management.py` (5.84% → 70%)
- `src/tools/application.py` (0% → 70%)

### Priority 3: Core Infrastructure (Important)

#### 3.1 Webhooks

**Estimated Time**: 3-4 hours
**Target Coverage**: 80%+

**Files**:

- `src/webhooks/receiver.py` (0% → 80%)
- `src/webhooks/handlers.py` (0% → 80%)

**Test File**: `tests/unit/test_webhooks.py`

**Test Scenarios**:

- Webhook reception and parsing
- Event handling
- Signature validation
- Error handling
- Async event processing

#### 3.2 Cache Layer

**Estimated Time**: 3-4 hours
**Target Coverage**: 80%+

**Files**: `src/cache.py` (0% → 80%)

**Test File**: `tests/unit/test_cache.py`

**Test Scenarios**:

- Cache get/set operations
- TTL expiration
- Cache invalidation
- Memory management
- Thread safety

#### 3.3 Main Server

**Estimated Time**: 2-3 hours
**Target Coverage**: 70%+

**Files**: `src/main.py` (0% → 70%)

**Test File**: `tests/unit/test_main.py`

**Test Scenarios**:

- MCP server initialization
- Tool registration
- Resource registration
- Error handling
- Graceful shutdown

#### 3.4 Utilities Enhancement

**Estimated Time**: 2-3 hours
**Target Coverage**: 95%+

**Files**:

- `src/utils/audit.py` (14.44% → 95%)
- `src/utils/validators.py` (97.14% → 100%)

**Test File**: Expand existing test files

### Priority 4: Integration & Performance Tests

#### 4.1 Integration Tests

**Estimated Time**: 4-5 hours
**Target Coverage**: Critical paths

**Directory**: `tests/integration/`

**Test Files**:

- `test_zbf_integration.py` - End-to-end ZBF workflows
- `test_traffic_flows_integration.py` - Real-time flow monitoring
- `test_site_manager_integration.py` - Multi-site operations
- `test_api_integration.py` - Full API client workflows

**Test Scenarios**:

- Full ZBF policy creation → application → verification
- Traffic flow monitoring → risk detection → alerting
- Multi-site health checks → aggregation → reporting
- API authentication → request → response validation

#### 4.2 Performance Tests

**Estimated Time**: 3-4 hours
**Target**: Benchmark and optimize

**Directory**: `tests/performance/`

**Test Files**:

- `test_traffic_flow_performance.py` - Real-time data processing
- `test_cache_performance.py` - Cache efficiency
- `test_rate_limiting.py` - Rate limiter stress tests
- `test_concurrent_operations.py` - Concurrent API calls

**Performance Targets**:

- Traffic flow processing: >1000 flows/second
- Cache hit rate: >90%
- Rate limiter accuracy: ±5%
- API response time: <100ms (p95)

## Implementation Guidelines

### Test Structure

All unit tests should follow this structure:

```python
"""Unit tests for [module name]."""

from unittest.mock import AsyncMock, patch
import pytest
from src.config import Settings
from src.tools import module_name

@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings for testing."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud")
    return Settings()

class TestModuleName:
    """Test suite for module functionality."""

    @pytest.mark.asyncio
    async def test_function_name(self, mock_settings: Settings) -> None:
        """Test [specific scenario]."""
        # Arrange
        # Act
        # Assert
```

### Testing Best Practices

1. **Mock External Dependencies**: Always mock API clients and external services
2. **Test Error Paths**: Include tests for error handling and edge cases
3. **Use Fixtures**: Leverage pytest fixtures for reusable test data
4. **Async Testing**: Use `@pytest.mark.asyncio` for async functions
5. **Assertions**: Be specific with assertions, check all relevant fields
6. **Documentation**: Each test should have a clear docstring
7. **Coverage**: Aim for 80%+ line coverage, 70%+ branch coverage
8. **Authentication**: Mock `is_authenticated` property appropriately

### Running Tests

```bash
# Run all tests with coverage
pytest tests/unit/ --cov=src --cov-report=term-missing --cov-report=html

# Run specific test file
pytest tests/unit/test_zbf_tools.py -v

# Run tests with specific marker
pytest -m "not slow" tests/

# Run with coverage threshold
pytest --cov=src --cov-fail-under=80
```

## Success Metrics

### Coverage Targets

| Component | Current | Target | Priority |
|-----------|---------|--------|----------|
| **New v0.2.0 Models** | 100% | 100% | ✅ Done |
| **New v0.2.0 Tools** | 82% | 85% | High |
| **Site Manager** | 0% | 80% | Critical |
| **Existing Tools** | 15% | 75% | High |
| **Core Infrastructure** | 10% | 80% | Medium |
| **Webhooks** | 0% | 80% | Medium |
| **Cache** | 0% | 80% | Medium |
| **Integration Tests** | 0% | Critical Paths | Low |
| **Performance Tests** | 0% | Benchmarks | Low |
| **Overall Project** | 34% | 80% | **Goal** |

### Quality Gates

- [ ] All unit tests passing
- [ ] 80%+ overall code coverage
- [ ] 90%+ coverage for new v0.2.0 features
- [ ] 75%+ coverage for existing tools
- [ ] All integration tests passing
- [ ] Performance benchmarks documented
- [ ] No critical security vulnerabilities
- [ ] All pre-commit hooks passing

## Timeline Estimate

| Phase | Description | Time | Cumulative |
|-------|-------------|------|------------|
| **Completed** | Models + ZBF + Traffic Flows | 8h | 8h |
| **Priority 1** | Site Manager | 5h | 13h |
| **Priority 2** | Existing Tools (WiFi, Firewall, etc.) | 20h | 33h |
| **Priority 3** | Infrastructure (Webhooks, Cache, Main) | 10h | 43h |
| **Priority 4** | Integration & Performance | 8h | 51h |
| **Total** | Complete testing coverage | **51h** | - |

**Note**: Times are estimates and may vary based on complexity and issues encountered.

## Continuous Integration

### GitHub Actions Workflow

The project uses GitHub Actions for CI/CD with the following checks:

- **Code Quality**: Black, isort, Ruff, MyPy
- **Testing**: Pytest with coverage reporting
- **Security**: Bandit, Safety, detect-secrets
- **Coverage**: Codecov integration (target: 80%)

All tests must pass before merging to main branch.

## Documentation Updates Required

As testing progresses, update the following documentation:

1. **README.md**: Add testing section with coverage badge
2. **CONTRIBUTING.md**: Update testing guidelines
3. **API.md**: Add tested endpoint examples
4. **DEVELOPMENT_PLAN.md**: Mark testing milestones as complete

## Conclusion

This testing plan provides a comprehensive roadmap to achieve 80%+ code coverage for the UniFi MCP Server. The phased approach prioritizes new v0.2.0 features while ensuring existing functionality remains well-tested. With an estimated 51 hours of work, the project can achieve enterprise-grade test coverage.

### Next Steps

1. ✅ Complete Site Manager tools testing (Priority 1)
2. Implement existing tools tests (Priority 2)
3. Add infrastructure tests (Priority 3)
4. Create integration and performance tests (Priority 4)
5. Update documentation with coverage results
6. Set up automated coverage reporting

---

**Last Updated**: November 1, 2025
**Current Coverage**: 34.10%
**Target Coverage**: 80%+
**Status**: Phase 1-3 Complete (New v0.2.0 Features)
