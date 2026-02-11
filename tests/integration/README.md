# UniFi MCP Server - Integration Test Framework

Comprehensive testing framework for running real-world integration tests against UniFi Cloud and Local Gateway APIs.

## Features

- **Multi-Environment Support**: Test against multiple UniFi environments (cloud, local lab, home, etc.)
- **API Mode Testing**: Validate functionality across cloud-v1, cloud-ea, and local API modes
- **Test Suite Organization**: Modular test suites for different tool categories
- **Detailed Reporting**: Pass/fail/skip statistics, timing data, and error details
- **Regression Testing**: Run all tests before releases to catch breaking changes
- **JSON Export**: Export results for CI/CD integration

## Setup

### 1. Configure Test Environments

Copy the example environment file and configure your UniFi credentials:

```bash
cp tests/integration/.env.example tests/integration/.env
```

Edit `.env` and add your credentials:

```bash
# UniFi Lab Environment (Local API)
UNIFI_LAB_API_KEY=P-la_4yXTA1sS6lFZs4VaoRgwoBXtAxi
UNIFI_LAB_HOST=10.2.0.1
UNIFI_LAB_PORT=443
UNIFI_LAB_VERIFY_SSL=false

# UniFi Home Environment (Local API)
UNIFI_HOME_API_KEY=9csiHHSfPIxp1Y7mINjMi2Af28QjOdV1
UNIFI_HOME_HOST=192.168.2.1
UNIFI_HOME_PORT=443
UNIFI_HOME_VERIFY_SSL=false

# UniFi Cloud Environment
UNIFI_CLOUD_API_KEY=your-cloud-key-here
UNIFI_CLOUD_API_TYPE=cloud-v1
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install python-dotenv  # If not already installed
```

## Running Tests

### Run All Tests on All Environments

```bash
python tests/integration/run_all_tests.py
```

### Run Tests on Specific Environment

```bash
# Test only on lab environment
python tests/integration/run_all_tests.py --env unifi-lab

# Test only on home environment
python tests/integration/run_all_tests.py --env unifi-home

# Test only on cloud
python tests/integration/run_all_tests.py --env unifi-cloud
```

### Run Specific Test Suite

```bash
# Run only topology tests
python tests/integration/run_all_tests.py --suite topology

# Run firewall tests on lab environment
python tests/integration/run_all_tests.py --suite firewall --env unifi-lab
```

### Verbose Output

```bash
python tests/integration/run_all_tests.py --verbose
```

### Export Results

```bash
# Export to JSON file
python tests/integration/run_all_tests.py --export test_results.json

# Export with verbose output
python tests/integration/run_all_tests.py --verbose --export results/$(date +%Y%m%d_%H%M%S).json
```

### Dry Run

See what tests would be run without executing them:

```bash
python tests/integration/run_all_tests.py --dry-run
```

## Test Suite Structure

### Available Test Suites

1. **Topology Suite** (`test_topology_suite.py`)
   - Tests network topology retrieval and visualization tools
   - Validates topology export in JSON, GraphML, and DOT formats
   - Verifies device connections and port mappings

2. **Firewall Suite** (Coming soon)
   - Firewall rule management
   - Zone-based policies
   - Traffic filtering

3. **QoS Suite** (Coming soon)
   - QoS profile management
   - Smart Queue Management
   - Traffic routing

4. **Backup Suite** (Coming soon)
   - Configuration backup and restore
   - Auto-backup scheduling

## Writing New Tests

### Create a New Test Suite

1. Create a new file in `tests/integration/`:

```python
# tests/integration/test_myfeature_suite.py
from tests.integration.test_harness import TestSuite
from src.tools import myfeature

async def test_my_feature(settings, env):
    """Test my feature."""
    result = await myfeature.do_something(
        site_id=env.site_id,
        settings=settings
    )

    assert isinstance(result, dict), "Result must be a dictionary"

    return {
        "status": "PASS",
        "message": "Feature works correctly",
        "details": result
    }

def create_myfeature_suite() -> TestSuite:
    """Create the myfeature test suite."""
    return TestSuite(
        name="myfeature",
        description="My Feature Tools - description here",
        tests=[
            test_my_feature,
        ],
    )
```

2. Register the suite in `run_all_tests.py`:

```python
from tests.integration.test_myfeature_suite import create_myfeature_suite

def discover_test_suites():
    suites = []
    suites.append(create_topology_suite())
    suites.append(create_myfeature_suite())  # Add your suite
    return suites
```

### Test Function Format

Test functions should:

- Be async functions
- Accept `settings` and `env` parameters
- Return a dictionary with `status`, `message`, and optional `details`
- Use assertions to validate behavior

```python
async def test_something(settings, env):
    """Test description."""
    try:
        result = await some_function(settings=settings)

        # Validate result
        assert isinstance(result, dict), "Must return dict"
        assert "field" in result, "Must contain field"

        return {
            "status": "PASS",
            "message": "Test passed",
            "details": {"key": "value"}
        }
    except AssertionError as e:
        return {"status": "FAIL", "message": str(e)}
    except Exception as e:
        return {"status": "ERROR", "message": f"{type(e).__name__}: {e}"}
```

### Test Status Values

- `PASS`: Test succeeded
- `FAIL`: Test failed assertion (expected failure)
- `SKIP`: Test skipped (precondition not met)
- `ERROR`: Unexpected error occurred

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run integration tests
        env:
          UNIFI_LAB_API_KEY: ${{ secrets.UNIFI_LAB_API_KEY }}
          UNIFI_LAB_HOST: ${{ secrets.UNIFI_LAB_HOST }}
        run: |
          python tests/integration/run_all_tests.py \
            --env unifi-lab \
            --export test_results.json

      - name: Upload test results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: test_results.json
```

## Pre-Release Checklist

Before releasing a new version:

1. **Run Full Regression Tests**:
   ```bash
   python tests/integration/run_all_tests.py --verbose --export results.json
   ```

2. **Verify All Environments**:
   - Test on local API (unifi-lab and unifi-home if available)
   - Test on cloud API (if available)

3. **Check Test Coverage**:
   - Ensure all new tools have integration tests
   - Verify existing tools still pass

4. **Review Failures**:
   - Investigate any FAIL or ERROR results
   - Update tests if behavior intentionally changed
   - Fix bugs if behavior unintentionally broke

5. **Export Results**:
   - Include test results in release notes
   - Document any known issues or limitations

## Troubleshooting

### Tests Fail with Authentication Error

- Verify API key is correct in `.env`
- Check API key has not expired
- Ensure host/IP is correct for local environments

### Tests Skip Due to Missing Devices

- Some tests require devices to be connected
- Connect test devices to your network
- Or mark tests as expected to skip in your environment

### Slow Test Execution

- Local API is faster than Cloud API
- Use `--env` flag to test one environment at a time
- Consider parallel execution for large test suites

## Best Practices

1. **Keep Tests Independent**: Each test should work regardless of other tests
2. **Use Meaningful Assertions**: Make it clear what failed and why
3. **Handle Preconditions**: Skip tests gracefully if preconditions not met
4. **Clean Up Resources**: Use setup/teardown for resource management
5. **Test Real Scenarios**: Integration tests should use real API calls
6. **Document Expectations**: Clearly document what each test validates

## Contributing

When adding new MCP tools:

1. Create integration tests in a new suite file
2. Register the suite in `run_all_tests.py`
3. Run full test suite to ensure no regressions
4. Include test results in pull request

## Support

For issues with the test framework:
- Check `.env` configuration
- Review test output with `--verbose` flag
- Check UniFi controller connectivity
- Verify API keys have required permissions
