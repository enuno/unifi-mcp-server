# CI/CD Documentation for UniFi MCP Server

## Overview

The UniFi MCP Server uses GitHub Actions for continuous integration, continuous deployment, security scanning, and automated releases. Our CI/CD pipeline emphasizes **security, quality, and reliability** with multiple layers of automated checks.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Actions Workflows                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   CI     │  │ Security │  │  Docker  │  │ Release  │   │
│  │ Pipeline │  │ Scanning │  │  Build   │  │ Pipeline │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│       │              │              │             │          │
│       ▼              ▼              ▼             ▼          │
│  • Linting      • CodeQL       • Multi-arch  • Changelog   │
│  • Testing      • Trivy        • GHCR Push   • Git Tags    │
│  • Coverage     • Bandit       • Latest Tag  • GitHub      │
│  • Type Check   • Safety       • Version Tag   Release     │
│                 • Secrets                                    │
└─────────────────────────────────────────────────────────────┘
```

## Workflows

### 1. CI Pipeline (`.github/workflows/ci.yml`)

**Trigger:** Push to any branch, Pull Requests

**Jobs:**

#### a. Lint (`lint`)
- **Runs:** Python code quality checks
- **Tools:**
  - `black --check` - Code formatting verification
  - `isort --check` - Import sorting verification
  - `ruff check` - Fast Python linter (replaces flake8, pylint)
  - `mypy` - Static type checking
- **Matrix:** Python 3.10, 3.11, 3.12
- **Fail Fast:** No (runs all Python versions even if one fails)

```yaml
lint:
  runs-on: ubuntu-latest
  strategy:
    matrix:
      python-version: ["3.10", "3.11", "3.12"]
    fail-fast: false
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install uv
      run: curl -LsSf https://astral.sh/uv/install.sh | sh
    - name: Install dependencies
      run: uv pip install -e ".[dev]"
    - name: Run black
      run: black --check src/ tests/
    - name: Run isort
      run: isort --check src/ tests/
    - name: Run ruff
      run: ruff check src/ tests/
    - name: Run mypy
      run: mypy src/
```

#### b. Test (`test`)
- **Runs:** Unit tests with coverage reporting
- **Tools:**
  - `pytest` - Test runner
  - `pytest-asyncio` - Async test support
  - `pytest-cov` - Coverage measurement
- **Coverage Targets:**
  - Overall: 80% (enforced)
  - New code: 90% (enforced via `--cov-fail-under`)
- **Artifacts:** HTML coverage report (30-day retention)

```yaml
test:
  runs-on: ubuntu-latest
  strategy:
    matrix:
      python-version: ["3.10", "3.11", "3.12"]
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: uv pip install -e ".[dev]"
    - name: Run tests with coverage
      run: |
        pytest tests/unit/ \
          --cov=src \
          --cov-report=html \
          --cov-report=term-missing \
          --cov-fail-under=80 \
          -v
    - name: Upload coverage report
      uses: actions/upload-artifact@v4
      if: matrix.python-version == '3.11'
      with:
        name: coverage-report
        path: htmlcov/
        retention-days: 30
```

#### c. Integration Tests (`integration`)
- **Runs:** Integration tests requiring external services
- **When:** Only on `main` branch or when labeled `run-integration`
- **Services:**
  - Redis (for cache testing)
  - Mock UniFi controller (Docker container)
- **Environment:** Full environment variables loaded

```yaml
integration:
  runs-on: ubuntu-latest
  if: github.ref == 'refs/heads/main' || contains(github.event.pull_request.labels.*.name, 'run-integration')
  services:
    redis:
      image: redis:7-alpine
      ports:
        - 6379:6379
      options: >-
        --health-cmd "redis-cli ping"
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
  steps:
    - uses: actions/checkout@v4
    - name: Run integration tests
      run: pytest tests/integration/ -v
      env:
        REDIS_HOST: localhost
        REDIS_PORT: 6379
```

### 2. Security Scanning (`.github/workflows/security.yml`)

**Trigger:** Push to `main`, Pull Requests, Scheduled (weekly on Mondays)

**Jobs:**

#### a. CodeQL Analysis (`codeql`)
- **Language:** Python
- **Scans:** Source code for security vulnerabilities
- **Queries:** `security-extended` (GitHub's advanced query suite)
- **Results:** Uploaded to GitHub Security tab

```yaml
codeql:
  runs-on: ubuntu-latest
  permissions:
    security-events: write
    contents: read
  steps:
    - uses: actions/checkout@v4
    - uses: github/codeql-action/init@v3
      with:
        languages: python
        queries: security-extended
    - uses: github/codeql-action/analyze@v3
```

#### b. Dependency Scanning (`dependency-scan`)
- **Tools:**
  - `pip-audit` - Scans Python dependencies for known vulnerabilities
  - `safety check` - Checks against safety-db
- **Fail Condition:** Any HIGH or CRITICAL vulnerability

```yaml
dependency-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Run pip-audit
      run: |
        pip install pip-audit
        pip-audit --requirement requirements.txt --format json > audit-results.json
    - name: Run Safety
      run: |
        pip install safety
        safety check --file requirements.txt --output json
```

#### c. Container Scanning (`trivy`)
- **Tool:** Trivy (Aqua Security)
- **Scans:**
  - Dockerfile for misconfigurations
  - Built images for vulnerabilities
- **Severity Threshold:** HIGH, CRITICAL
- **Output:** SARIF format uploaded to GitHub Security

```yaml
trivy:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Build Docker image
      run: docker build -t unifi-mcp:test .
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: unifi-mcp:test
        format: sarif
        severity: HIGH,CRITICAL
        output: trivy-results.sarif
    - name: Upload Trivy results
      uses: github/codeql-action/upload-sarif@v3
      with:
        sarif_file: trivy-results.sarif
```

#### d. Code Security (`bandit`)
- **Tool:** Bandit (PyCQA)
- **Scans:** Python code for common security issues
- **Excludes:** `tests/` directory
- **Severity:** Medium and above

```yaml
bandit:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Run Bandit
      run: |
        pip install bandit
        bandit -r src/ -f json -o bandit-report.json -ll
    - name: Upload Bandit report
      uses: actions/upload-artifact@v4
      with:
        name: bandit-report
        path: bandit-report.json
```

#### e. Secret Scanning (`detect-secrets`)
- **Tool:** detect-secrets (Yelp)
- **Scans:** Codebase for accidentally committed secrets
- **Baseline:** `.secrets.baseline` (audited false positives)
- **Fail Condition:** New secrets detected

```yaml
detect-secrets:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Install detect-secrets
      run: pip install detect-secrets
    - name: Scan for secrets
      run: |
        detect-secrets scan --baseline .secrets.baseline
        detect-secrets audit .secrets.baseline
```

### 3. Docker Build & Push (`.github/workflows/docker.yml`)

**Trigger:** Push to `main`, Tags matching `v*.*.*`

**Multi-Architecture Builds:**
- linux/amd64
- linux/arm64
- linux/arm/v7 (32-bit ARM)
- linux/arm64/v8

**Registries:**
- GitHub Container Registry (ghcr.io)
- Docker Hub (optional, configurable)

**Tags:**
- `latest` (for main branch)
- `v{version}` (for tagged releases)
- `{branch}` (for feature branches)

```yaml
docker:
  runs-on: ubuntu-latest
  permissions:
    contents: read
    packages: write
  steps:
    - uses: actions/checkout@v4
    
    - name: Set up QEMU
      uses: docker/setup-qemu-action@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Login to GitHub Container Registry
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ghcr.io/${{ github.repository }}
        tags: |
          type=ref,event=branch
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          type=raw,value=latest,enable={{is_default_branch}}
    
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        platforms: linux/amd64,linux/arm64,linux/arm/v7,linux/arm64/v8
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

### 4. Release Pipeline (`.github/workflows/release.yml`)

**Trigger:** Tags matching `v*.*.*` (e.g., `v0.2.0`)

**Automated Tasks:**
1. Generate changelog from conventional commits
2. Create GitHub Release with notes
3. Build and publish Docker images
4. Upload release artifacts

```yaml
release:
  runs-on: ubuntu-latest
  permissions:
    contents: write
    packages: write
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0  # Full history for changelog
    
    - name: Generate changelog
      id: changelog
      uses: TriPSs/conventional-changelog-action@v5
      with:
        github-token: ${{ secrets.GITHUB_TOKEN }}
        output-file: CHANGELOG.md
        skip-version-file: true
    
    - name: Create GitHub Release
      uses: ncipollo/release-action@v1
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
        tag: ${{ github.ref_name }}
        name: Release ${{ github.ref_name }}
        body: ${{ steps.changelog.outputs.clean_changelog }}
        draft: false
        prerelease: false
    
    - name: Build release artifacts
      run: |
        pip install build
        python -m build
    
    - name: Upload artifacts to release
      uses: actions/upload-release-asset@v1
      with:
        upload_url: ${{ steps.create_release.outputs.upload_url }}
        asset_path: ./dist/*
        asset_name: unifi-mcp-server-${{ github.ref_name }}.tar.gz
        asset_content_type: application/gzip
```

## Branch Protection Rules

### Main Branch (`main`)
- **Required Status Checks:**
  - `lint` (all Python versions)
  - `test` (all Python versions)
  - `codeql` (CodeQL analysis)
  - `trivy` (Container security)
- **Required Reviews:** 1 approving review
- **Require Signed Commits:** Yes
- **Require Linear History:** Yes
- **Dismiss Stale Reviews:** Yes
- **Restrict Push:** Only maintainers

### Release Branches (`release/*`)
- Same as `main` plus:
  - **Additional Checks:** `integration` tests
  - **Required Reviews:** 2 approving reviews
  - **No Force Push:** Enforced

### Feature Branches
- No protection (encourages experimentation)
- CI must pass before merge to `main`

## Environment Variables & Secrets

### Repository Secrets (Configured in GitHub Settings)

#### Required Secrets
```
UNIFI_API_KEY              # UniFi API key for integration tests
UNIFI_INTEGRATION_SITE_ID  # Test site ID
GITHUB_TOKEN               # Auto-provided by GitHub Actions
```

#### Optional Secrets
```
DOCKERHUB_USERNAME         # Docker Hub credentials (if publishing)
DOCKERHUB_TOKEN
CODECOV_TOKEN              # Codecov integration token
AGNOST_ORG_ID              # agnost.ai organization ID (for analytics)
```

### Environment Variables in Workflows

#### CI Environment
```yaml
env:
  PYTHON_VERSION: "3.11"  # Primary Python version
  UV_CACHE_DIR: ~/.cache/uv
  PYTEST_ADDOPTS: "-v --strict-markers --tb=short"
  REDIS_URL: "redis://localhost:6379/0"
```

#### Docker Environment
```yaml
env:
  DOCKER_BUILDKIT: 1
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
```

## Caching Strategy

### Python Dependencies Cache
```yaml
- name: Cache uv dependencies
  uses: actions/cache@v4
  with:
    path: ~/.cache/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('**/pyproject.toml') }}
    restore-keys: |
      ${{ runner.os }}-uv-
```

### Docker Layer Cache
```yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### Test Result Cache
```yaml
- name: Cache pytest
  uses: actions/cache@v4
  with:
    path: .pytest_cache
    key: ${{ runner.os }}-pytest-${{ hashFiles('tests/**') }}
```

## Performance Optimization

### Parallel Jobs
- Lint, test, and security scans run in parallel
- Matrix builds for multiple Python versions (3.10, 3.11, 3.12)
- Docker multi-arch builds use BuildKit parallel build

### Build Time Optimization
- **uv** instead of pip (10-100x faster dependency resolution)
- Docker layer caching with GitHub Actions cache
- Conditional job execution (integration tests only on `main`)

### Resource Limits
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10  # Prevent hanging jobs
    
  docker:
    runs-on: ubuntu-latest
    timeout-minutes: 30  # Multi-arch builds take longer
```

## Monitoring & Notifications

### Success/Failure Notifications
- **Slack Integration** (optional):
```yaml
- name: Notify Slack on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "CI failed for ${{ github.repository }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "❌ *CI Failed*\n*Repository:* ${{ github.repository }}\n*Branch:* ${{ github.ref }}\n*Run:* ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
            }
          }
        ]
      }
```

### GitHub Status Badges
Add to README.md:
```markdown
![CI Status](https://github.com/enuno/unifi-mcp-server/actions/workflows/ci.yml/badge.svg)
![Security](https://github.com/enuno/unifi-mcp-server/actions/workflows/security.yml/badge.svg)
![Docker](https://github.com/enuno/unifi-mcp-server/actions/workflows/docker.yml/badge.svg)
[![codecov](https://codecov.io/gh/enuno/unifi-mcp-server/branch/main/graph/badge.svg)](https://codecov.io/gh/enuno/unifi-mcp-server)
```

## Deployment

### Production Deployment (Docker)
Triggered automatically on release tags:
```bash
# Create and push release tag
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0

# GitHub Actions will:
# 1. Run full CI pipeline
# 2. Run security scans
# 3. Build multi-arch Docker images
# 4. Push to ghcr.io with tags: v0.2.0, 0.2, latest
# 5. Create GitHub Release with changelog
```

### Manual Deployment (PyPI)
For Python package distribution:
```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Build package
        run: |
          pip install build
          python -m build
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

## Rollback Procedures

### Docker Image Rollback
```bash
# Revert to previous version
docker pull ghcr.io/enuno/unifi-mcp-server:v0.1.0

# Or use specific commit SHA
docker pull ghcr.io/enuno/unifi-mcp-server:sha-abc1234
```

### Git Tag Rollback
```bash
# Delete bad tag locally and remotely
git tag -d v0.2.0
git push origin :refs/tags/v0.2.0

# Delete GitHub Release (via UI or API)
gh release delete v0.2.0
```

## Troubleshooting CI/CD Issues

### Common Failures

#### 1. Test Failures
```bash
# Reproduce locally
pytest tests/unit/ --cov=src --cov-fail-under=80 -v

# Check specific test
pytest tests/unit/test_specific.py::test_name -vv
```

#### 2. Docker Build Failures
```bash
# Test multi-arch build locally
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t test .
```

#### 3. Coverage Below Threshold
```bash
# Generate detailed coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Add tests for uncovered code
pytest --cov=src --cov-report=term-missing
```

#### 4. Security Scan Failures
```bash
# Run Trivy locally
trivy image --severity HIGH,CRITICAL unifi-mcp:latest

# Run Bandit locally
bandit -r src/ -ll

# Check for secrets
detect-secrets scan
```

### Debug GitHub Actions

#### Enable Debug Logging
```yaml
# In workflow file
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
```

#### Or via Repository Settings
Settings → Secrets and variables → Actions → Variables:
- `ACTIONS_STEP_DEBUG` = `true`
- `ACTIONS_RUNNER_DEBUG` = `true`

#### SSH into Runner (for complex debugging)
```yaml
- name: Setup tmate session
  if: failure()
  uses: mxschmitt/action-tmate@v3
  timeout-minutes: 15
```

## Best Practices

### 1. Conventional Commits
Use semantic commit messages for automated changelog:
```
feat: add new WiFi management tools
fix: prevent race condition in cache invalidation
docs: update API documentation
test: add integration tests for DPI tools
chore: update dependencies
```

### 2. Version Bumping
Follow semantic versioning:
- **Major (v1.0.0)**: Breaking API changes
- **Minor (v0.2.0)**: New features, backward compatible
- **Patch (v0.1.1)**: Bug fixes, backward compatible

### 3. Pre-commit Hooks
Install locally to catch issues before CI:
```bash
pre-commit install
pre-commit install --hook-type commit-msg

# Run manually
pre-commit run --all-files
```

### 4. CI Performance
- Keep jobs under 10 minutes when possible
- Use matrix builds for Python versions
- Cache dependencies aggressively
- Skip unnecessary jobs on docs-only changes:

```yaml
on:
  push:
    paths-ignore:
      - '**.md'
      - 'docs/**'
```

## Continuous Improvement

### Metrics to Track
- **Build Times**: Target < 5 minutes for CI
- **Test Coverage**: Maintain > 80%, target 90%
- **Security Issues**: Zero HIGH/CRITICAL vulnerabilities
- **Docker Image Size**: Optimize to < 200MB

### Quarterly Reviews
- Update dependencies monthly
- Review and update security scanning tools
- Analyze CI performance and optimize
- Update documentation based on issues

## Resources

- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Docker Buildx**: https://docs.docker.com/buildx/working-with-buildx/
- **Conventional Commits**: https://www.conventionalcommits.org/
- **CodeQL Queries**: https://github.com/github/codeql
- **Trivy Documentation**: https://aquasecurity.github.io/trivy/

## Support

For CI/CD issues:
1. Check workflow run logs in GitHub Actions tab
2. Review this documentation
3. Search existing GitHub Issues
4. Open new issue with `ci/cd` label

**Remember**: CI/CD is not just automation—it's your safety net. Keep it reliable, keep it fast, keep it secure.