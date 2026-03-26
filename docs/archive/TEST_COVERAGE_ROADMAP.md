# Test Coverage Roadmap for v0.2.0

**Current Overall Coverage**: 36.22%
**Target Coverage**: 60-70%
**Total Tests**: 219 passing
**Last Updated**: 2025-11-19

---

## Executive Summary

This document provides a comprehensive roadmap for achieving 60-70% test coverage for the UniFi MCP Server v0.2.0 release. The strategy focuses on high-impact tools, security-critical functionality, and quick wins to maximize coverage with minimal effort.

### Current State

- **219 tests passing** (all green ✅)
- **36.22% overall coverage** across 3,701 statements
- **6 tools already at target** (≥70% coverage)
- **Estimated 40-50 hours** to reach 60% coverage
- **Estimated 60-80 hours** to reach 70% coverage

### Quick Wins (Already at Target ≥70%)

- ✅ `zbf_matrix.py`: 100.00% (20 stmts)
- ✅ `helpers.py`: 96.25% (58 stmts)
- ✅ `sites.py`: 94.64% (52 stmts)
- ✅ `networks.py`: 94.52% (63 stmts)
- ✅ `exceptions.py`: 91.18% (34 stmts)
- ✅ `logger.py`: 90.00% (26 stmts)
- ✅ `firewall_zones.py`: 87.83% (149 stmts)
- ✅ `clients.py`: 80.77% (66 stmts)
- ✅ `wifi.py`: 70.34% (170 stmts)

---

## Phase 1: High-Impact Quick Wins (Est. 8-12 hours)

### 1.1 Push Existing Tests Over 70%

#### `validators.py` - 97.14% → 100%

- **Current**: 97.14% (46 stmts, 1 miss)
- **Missing**: Line 111
- **Effort**: 15 minutes
- **Test Needed**: Edge case validation test
- **Priority**: LOW (already excellent coverage)

#### `devices.py` - 53.91% → 70%

- **Current**: 53.91% (110 stmts, 47 miss)
- **Missing Lines**: 210-232, 256-288, 316-354
- **Effort**: 2-3 hours
- **Tests Needed**:
  - `get_device_port_overrides` tests (lines 210-232)
  - `list_device_uplinks` tests (lines 256-288)
  - `get_device_radio_stats` tests (lines 316-354)
- **Priority**: HIGH (security monitoring, close to target)
- **Impact**: Large codebase, high user value

#### `audit.py` - 47.78% → 70%

- **Current**: 47.78% (66 stmts, 31 miss)
- **Missing Lines**: 58, 67-68, 73, 80, 94-120, 187-200
- **Effort**: 2-3 hours
- **Tests Needed**:
  - Audit log writing tests
  - Audit query/search tests
  - Audit filtering tests
- **Priority**: MEDIUM (security critical)
- **Impact**: Security audit trail validation

---

## Phase 2: Security-Critical Tools (Est. 10-15 hours)

### 2.1 Firewall Tools

#### `firewall.py` - 4.44% → 70%

- **Current**: 4.44% (130 stmts, 122 miss)
- **Missing Lines**: 34-48, 86-170, 210-307, 333-382
- **Effort**: 4-5 hours
- **Tests Needed**:
  - `create_firewall_rule` tests (CREATE with confirm/dry_run)
  - `update_firewall_rule` tests (UPDATE with validation)
  - `delete_firewall_rule` tests (DELETE with safety checks)
  - `list_firewall_rules` tests (READ operations)
  - Protocol validation (TCP, UDP, ICMP)
  - Port range validation
  - IP address/CIDR validation
  - Action validation (accept, drop, reject)
- **Priority**: CRITICAL (network security)
- **Impact**: Core firewall functionality

#### `acls.py` - 0% → 70%

- **Current**: 0.00% (117 stmts, 117 miss)
- **Effort**: 4-5 hours
- **Tests Needed**:
  - ACL creation with IP ranges
  - ACL update operations
  - ACL deletion with dependencies
  - ACL rule ordering tests
  - Protocol and port validation
- **Priority**: HIGH (access control security)
- **Impact**: Network access control

### 2.2 Client Management

#### `client_management.py` - 5.84% → 70%

- **Current**: 5.84% (132 stmts, 123 miss)
- **Missing Lines**: 40-98, 123-171, 197-257, 288-360, 389-464
- **Effort**: 3-4 hours
- **Tests Needed**:
  - `block_client` tests (safety confirmation)
  - `unblock_client` tests
  - `reconnect_client` tests
  - `forget_client` tests
  - Client authorization tests
- **Priority**: HIGH (network access control)
- **Impact**: Client security management

#### `device_control.py` - 6.31% → 70%

- **Current**: 6.31% (93 stmts, 86 miss)
- **Missing Lines**: 40-98, 126-193, 221-296
- **Effort**: 2-3 hours
- **Tests Needed**:
  - `restart_device` tests (confirm/dry_run)
  - `locate_device` tests (LED control)
  - `upgrade_device` tests (firmware safety)
  - `adopt_device` tests
  - `provision_device` tests
- **Priority**: MEDIUM (device operations)
- **Impact**: Device lifecycle management

---

## Phase 3: High-Value User Features (Est. 8-12 hours)

### 3.1 Traffic Analysis & Monitoring

#### `traffic_flows.py` - 30.13% → 70%

- **Current**: 30.13% (346 stmts, 230 miss)
- **Missing Lines**: 343-427, 445-485, 505-581, 607-673, 708-774, 809-905, 940-985, 1003-1037
- **Effort**: 5-6 hours
- **Tests Needed**:
  - `get_traffic_flows` with filters
  - `stream_traffic_flows` async generator tests
  - `get_connection_states` tests
  - `get_client_flow_aggregation` tests
  - `analyze_flow_patterns` tests
  - `detect_anomalies` tests
  - `block_flow_source_ip` tests (security)
  - Time range filtering tests
  - Protocol/application filtering
- **Priority**: HIGH (v0.2.0 feature)
- **Impact**: Network monitoring & security

### 3.2 DPI & Analytics

#### `dpi.py` - 0% → 70%

- **Current**: 0.00% (85 stmts, 85 miss)
- **Effort**: 3-4 hours
- **Tests Needed**:
  - `get_dpi_statistics` tests
  - `get_top_applications` tests
  - `get_client_dpi_stats` tests
  - Application categorization tests
  - Bandwidth usage aggregation
- **Priority**: MEDIUM (analytics)
- **Impact**: Network visibility

#### `dpi_tools.py` - 0% → 70%

- **Current**: 0.00% (37 stmts, 37 miss)
- **Effort**: 1-2 hours
- **Tests Needed**:
  - DPI category management
  - Application fingerprinting
  - Traffic classification
- **Priority**: LOW (utility functions)
- **Impact**: DPI support functionality

### 3.3 Network Configuration

#### `network_config.py` - 3.72% → 70%

- **Current**: 3.72% (128 stmts, 121 miss)
- **Missing Lines**: 58-146, 192-295, 321-370
- **Effort**: 4-5 hours
- **Tests Needed**:
  - `create_network` tests (VLAN, DHCP, gateway)
  - `update_network` tests (modify settings)
  - `delete_network` tests (dependency checks)
  - VLAN ID validation
  - Subnet/CIDR validation
  - DHCP range validation
  - DNS configuration tests
- **Priority**: MEDIUM (infrastructure)
- **Impact**: Network provisioning

#### `port_forwarding.py` - 0% → 70%

- **Current**: 0.00% (70 stmts, 70 miss)
- **Effort**: 2-3 hours
- **Tests Needed**:
  - `create_port_forward` tests
  - `delete_port_forward` tests
  - `list_port_forwards` tests
  - Port validation (1-65535)
  - Protocol validation (TCP/UDP)
  - Destination IP validation
  - Conflict detection
- **Priority**: MEDIUM (user-requested feature)
- **Impact**: Port forwarding management

---

## Phase 4: Extended Features (Est. 10-15 hours)

### 4.1 Site Management

#### `site_manager.py` - 0% → 65%

- **Current**: 0.00% (77 stmts, 77 miss)
- **Effort**: 4-5 hours
- **Tests Needed**:
  - Cloud API authentication (OAuth/SSO)
  - Multi-site operations
  - Site health aggregation
  - Cross-site client search
  - Internet health metrics
  - Vantage Point data retrieval
- **Priority**: MEDIUM (v0.2.0 planned)
- **Impact**: Multi-site management

### 4.2 Utility Features

#### `vouchers.py` - 0% → 70%

- **Current**: 0.00% (78 stmts, 78 miss)
- **Effort**: 2-3 hours
- **Tests Needed**:
  - `create_voucher` tests
  - `list_vouchers` tests
  - `delete_voucher` tests
  - Voucher expiration validation
  - Usage limit validation
- **Priority**: LOW (guest access)
- **Impact**: Guest WiFi management

#### `wans.py` - 0% → 70%

- **Current**: 0.00% (13 stmts, 13 miss)
- **Effort**: 30 minutes
- **Tests Needed**:
  - WAN interface listing
  - WAN failover tests
  - WAN statistics
- **Priority**: LOW (simple, small file)
- **Impact**: WAN monitoring

#### `application.py` - 0% → 70%

- **Current**: 0.00% (12 stmts, 12 miss)
- **Effort**: 30 minutes
- **Tests Needed**:
  - Application discovery
  - Application metadata
- **Priority**: LOW (utility)
- **Impact**: Application information

---

## Recommended Execution Order

### Sprint 1: Quick Wins & Security (Week 1-2, 15-20 hours)

1. ✅ Fix failing tests (COMPLETED)
2. `devices.py` → 70% (2-3 hours)
3. `firewall.py` → 70% (4-5 hours)
4. `client_management.py` → 70% (3-4 hours)
5. `device_control.py` → 70% (2-3 hours)
6. `audit.py` → 70% (2-3 hours)

**Expected Coverage After Sprint 1**: ~45-48%

### Sprint 2: High-Value Features (Week 3-4, 12-15 hours)

7. `traffic_flows.py` → 70% (5-6 hours)
8. `network_config.py` → 70% (4-5 hours)
9. `port_forwarding.py` → 70% (2-3 hours)
10. `dpi.py` → 70% (3-4 hours)

**Expected Coverage After Sprint 2**: ~55-58%

### Sprint 3: Reach 60% Target (Week 5, 8-10 hours)

11. `acls.py` → 70% (4-5 hours)
12. `site_manager.py` → 65% (4-5 hours)

**Expected Coverage After Sprint 3**: ~60-63%

### Sprint 4: Reach 70% Target (Optional, Week 6, 6-8 hours)

13. `vouchers.py` → 70% (2-3 hours)
14. `wans.py` → 70% (30 min)
15. `application.py` → 70% (30 min)
16. `dpi_tools.py` → 70% (1-2 hours)
17. `validators.py` → 100% (15 min)

**Expected Coverage After Sprint 4**: ~68-72%

---

## Test Coverage Templates

### Standard Test Template

```python
"""Unit tests for [module_name] tools."""

from unittest.mock import AsyncMock, patch
import pytest
from src.tools.[module] import [function_name]
from src.utils.exceptions import ValidationError, ResourceNotFoundError

@pytest.fixture
def mock_settings(monkeypatch):
    """Create mock settings for testing."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud")
    return Settings()

class Test[FunctionName]:
    """Test suite for [function_name]."""

    @pytest.mark.asyncio
    async def test_success_case(self, mock_settings):
        """Test successful operation."""
        with patch("src.tools.[module].UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = True
            mock_instance.[method].return_value = {"data": [...]}
            mock_client.return_value = mock_instance

            result = await [function_name]([params], mock_settings)

            assert result[...] == expected
            mock_instance.[method].assert_called_once()

    @pytest.mark.asyncio
    async def test_without_confirmation(self, mock_settings):
        """Test that operation requires confirmation."""
        with pytest.raises(ValidationError, match="confirmation"):
            await [function_name]([params], confirm=False, settings=mock_settings)

    @pytest.mark.asyncio
    async def test_dry_run(self, mock_settings):
        """Test dry run mode."""
        result = await [function_name]([params], confirm=True, dry_run=True, settings=mock_settings)
        assert result["dry_run"] is True
        assert "payload" in result

    @pytest.mark.asyncio
    async def test_not_found(self, mock_settings):
        """Test resource not found scenario."""
        with patch("src.tools.[module].UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = {"data": []}
            mock_client.return_value = mock_instance

            with pytest.raises(ResourceNotFoundError):
                await [function_name]([params], mock_settings)
```

### Mutating Operation Test Checklist

For tools that modify configuration (CREATE/UPDATE/DELETE):

- ✅ Test successful operation
- ✅ Test without confirmation (should raise ValidationError)
- ✅ Test dry_run mode (should not execute)
- ✅ Test with invalid parameters (validation errors)
- ✅ Test resource not found
- ✅ Test duplicate resource (for create)
- ✅ Test audit logging
- ✅ Test with minimal parameters
- ✅ Test with full parameters
- ✅ Test edge cases (empty strings, None values)

### Read-Only Operation Test Checklist

For tools that only query data (LIST/GET):

- ✅ Test successful retrieval
- ✅ Test with pagination (limit/offset)
- ✅ Test with filters
- ✅ Test empty results
- ✅ Test resource not found
- ✅ Test invalid site_id
- ✅ Test invalid parameters

---

## Coverage Calculation

### Current Coverage by Category

| Category | Current | Target | Tools |
|----------|---------|--------|-------|
| **Models** | 88.5% | ✅ | All Pydantic models |
| **Utils** | 67.4% | ✅ | validators, helpers, logger, exceptions |
| **Core Tools** | 42.1% | 70% | devices, clients, networks, sites |
| **Security** | 12.3% | 70% | firewall, acls, client_mgmt, device_ctrl |
| **Advanced** | 8.6% | 70% | traffic_flows, dpi, port_fwd, site_mgr |
| **Extended** | 0.0% | 65% | vouchers, wans, application |
| **Resources** | 0.0% | 60% | MCP resources (sites, devices, clients, networks) |
| **Infrastructure** | 0.0% | 50% | cache, webhooks, main |

### Projected Coverage by Sprint

| Sprint | Hours | Coverage | Delta |
|--------|-------|----------|-------|
| Current | - | 36.2% | - |
| Sprint 1 | 15-20 | 45-48% | +9-12% |
| Sprint 2 | 12-15 | 55-58% | +10% |
| Sprint 3 | 8-10 | 60-63% | +5% |
| Sprint 4 | 6-8 | 68-72% | +8-9% |

---

## Risk Factors & Mitigation

### High Risk

- **Traffic Flows Complexity** (346 statements)
  - Mitigation: Break into smaller test modules
  - Focus on critical paths first (filtering, aggregation)

- **Site Manager OAuth** (Cloud API authentication)
  - Mitigation: Mock OAuth flow carefully
  - May need separate integration tests

### Medium Risk

- **Firewall Rule Validation** (Complex rulesets)
  - Mitigation: Use parameterized tests
  - Create comprehensive fixture data

- **Network Configuration** (DHCP, DNS, VLAN interdependencies)
  - Mitigation: Test each component independently
  - Mock network dependencies

### Low Risk

- **Simple CRUD Operations** (vouchers, wans)
  - Mitigation: Follow standard test template
  - Copy-paste from existing tests

---

## Success Metrics

### Quantitative

- ✅ 60% overall coverage (minimum acceptable)
- ✅ 70% overall coverage (target)
- ✅ 100% of security-critical tools at 70%+
- ✅ 90% of Phase 1 tools (devices, clients, networks, sites) at 70%+
- ✅ Zero failing tests
- ✅ All tests run in <10 seconds

### Qualitative

- ✅ All mutating operations have safety tests (confirm, dry_run)
- ✅ All tools have validation error tests
- ✅ All tools have "not found" error tests
- ✅ All pagination is tested
- ✅ All filters are tested
- ✅ Edge cases covered (empty, None, invalid)

---

## Maintenance Plan

### Ongoing (Post v0.2.0)

1. **New Features**: Require 70% coverage before merge
2. **Bug Fixes**: Add regression test for each bug
3. **Refactoring**: Maintain or improve coverage
4. **Weekly**: Run full test suite in CI/CD
5. **Monthly**: Review coverage report for gaps

### Coverage Gates

- **PR Merge**: No decrease in coverage allowed
- **Release**: Must be at 60%+ coverage
- **Production**: Critical tools must be at 80%+

---

## Tools & Automation

### Current Setup

- ✅ pytest with pytest-asyncio
- ✅ pytest-cov for coverage
- ✅ HTML coverage reports
- ✅ Pre-commit hooks
- ✅ CI/CD with GitHub Actions

### Recommended Additions

- ⏳ Coverage badges in README
- ⏳ Codecov integration
- ⏳ Automated coverage comments on PRs
- ⏳ Coverage trending over time
- ⏳ Mutation testing (optional)

---

## Conclusion

Reaching 60-70% test coverage for v0.2.0 is achievable with a focused 4-6 week effort (40-50 hours). The roadmap prioritizes security-critical tools, high-value user features, and tools closest to the coverage target. Following the sprint-based approach ensures steady progress and allows for adjustment based on actual time spent.

**Key Takeaways:**

1. Start with security tools (firewall, acls, client management)
2. Focus on tools with existing test infrastructure
3. Use standard test templates to accelerate development
4. Prioritize quality over quantity (70% meaningful coverage > 90% shallow)
5. Maintain coverage discipline post-v0.2.0

**Next Steps:**

1. ✅ Review and approve roadmap
2. Execute Sprint 1 (security & quick wins)
3. Measure actual time vs. estimates
4. Adjust remaining sprints based on velocity
5. Celebrate reaching 60% coverage! 🎉
