---
name: release-planner
description: Use this skill to plan and coordinate version releases. Creates release checklists, validates pre-release requirements, generates changelogs, and orchestrates the release process. Essential for v0.2.0, v0.3.0, and v1.0.0 milestone releases.
---

# Release Planner Skill

## Purpose
Guide the complete release process for UniFi MCP Server version releases, ensuring all requirements are met, documentation is updated, tests pass, and releases are properly tagged and published. Coordinates the multi-step release workflow from planning to deployment.

## When to Use This Skill
- Planning a new version release (v0.2.0, v0.3.0, v1.0.0)
- Before running `/unifi-mcp-release-prep` slash command
- Quarterly release planning
- Patch release preparation
- Hotfix release coordination
- Post-release verification

## Phase 1: Release Planning

### Step 1: Determine Release Type

Ask the user about the release:

**Release Types:**
1. **Major Release (X.0.0)**
   - Breaking changes
   - Major new features
   - Architecture changes
   - Example: v1.0.0 (Multi-Application Platform)

2. **Minor Release (0.X.0)**
   - New features
   - No breaking changes
   - New tools added
   - Example: v0.2.0 (ZBF + Traffic Flows)

3. **Patch Release (0.0.X)**
   - Bug fixes only
   - No new features
   - Security patches
   - Example: v0.1.5 (Bug fixes)

4. **Hotfix Release**
   - Critical bug fix
   - Urgent security fix
   - Immediate deployment

**Questions to Ask:**
- What type of release is this?
- What features/fixes are included?
- Are there any breaking changes?
- What's the target release date?
- Is this a planned or emergency release?

### Step 2: Review Development Plan Progress

Load and analyze DEVELOPMENT_PLAN.md and TODO.md:

```python
# Check current progress
Current Version: v0.1.4
Next Planned: v0.2.0

v0.2.0 Status (from TODO.md):
- Phase 1 (ZBF): ~60% complete
- Phase 2 (Traffic Flows): 100% complete ✅
- Phase 3 (QoS): 0% complete
- Phase 4 (Backup): 0% complete
- Phase 5 (Site Manager): ~30% complete
- Phase 6 (RADIUS): 10% complete
- Phase 7 (Topology): 0% complete

Overall: ~35% complete
```

**Release Decision:**
- **If <80% complete**: Consider splitting release into smaller increments
- **If ≥80% complete**: Proceed with full release
- **If critical features incomplete**: Delay release or remove from scope

### Step 3: Define Release Scope

Based on completion status, define what's included:

**Example v0.2.0 Scope:**
```markdown
## v0.2.0 Release Scope

### Included Features (Complete)
- ✅ Traffic Flow Monitoring (15 tools) - 100% complete
- ✅ Zone-Based Firewall Zones (7 tools) - Working features only

### Partially Included (Documented as Experimental)
- ⚠️  ZBF Policy Matrix (8 tools) - Marked as deprecated (endpoints don't exist)

### Deferred to v0.2.1
- ⏸ Advanced QoS (Phase 3) - Defer to v0.2.1
- ⏸ Backup & Restore (Phase 4) - Defer to v0.2.1
- ⏸ Site Manager API (Phase 5) - Defer to v0.2.1

### Not Included
- ❌ Enhanced RADIUS (Phase 6)
- ❌ Network Topology (Phase 7)

### Breaking Changes
- None

### Deprecated Tools
- 8 ZBF matrix tools (endpoints don't exist in UniFi Network v10.0.156)
```

## Phase 2: Pre-Release Validation

### Validation Checklist

**Code Quality** (Must Pass):
- [ ] All tests passing: `pytest tests/unit/ -v`
- [ ] Test coverage ≥60%: `pytest --cov=src --cov-report=term`
- [ ] No linting errors: `ruff check src/ tests/`
- [ ] Code formatted: `black src/ tests/ --check`
- [ ] Imports sorted: `isort src/ tests/ --check`
- [ ] Type checking passed: `mypy src/`
- [ ] No security issues: `bandit -r src/`

**Documentation** (Must Be Updated):
- [ ] README.md updated with new features
- [ ] API.md updated with new tools
- [ ] CHANGELOG.md has release notes
- [ ] Version numbers updated in:
  - [ ] `pyproject.toml`
  - [ ] `src/__init__.py`
  - [ ] `README.md`
  - [ ] `DEVELOPMENT_PLAN.md`
- [ ] Migration guides written (if breaking changes)

**CI/CD** (Must Pass):
- [ ] GitHub Actions CI workflow passing
- [ ] Security scan workflow passing
- [ ] Docker build succeeds
- [ ] All required checks green

**Testing** (Recommended):
- [ ] Integration tests run on real controller
- [ ] Manual testing of new features completed
- [ ] Performance benchmarks acceptable
- [ ] No regressions in existing features

### Automated Validation

Run comprehensive checks:

```bash
#!/bin/bash
# scripts/pre-release-validation.sh

set -e

echo "🔍 Running pre-release validation..."

# 1. Code quality
echo "→ Running tests..."
pytest tests/unit/ -v --cov=src --cov-report=term --cov-report=html

echo "→ Running linters..."
ruff check src/ tests/
black src/ tests/ --check
isort src/ tests/ --check
mypy src/

echo "→ Running security scan..."
bandit -r src/ -ll

# 2. Documentation
echo "→ Checking documentation..."
# Verify README mentions new version
grep -q "v0.2.0" README.md || echo "⚠️  README not updated"

# Verify CHANGELOG exists for version
grep -q "## \[0.2.0\]" CHANGELOG.md || echo "⚠️  CHANGELOG not updated"

# 3. Version consistency
echo "→ Checking version consistency..."
# Extract version from pyproject.toml
VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
echo "Version: $VERSION"

# Verify version in README
grep -q "v$VERSION" README.md || echo "⚠️  README version mismatch"

# 4. CI/CD status
echo "→ Checking CI/CD status..."
gh run list --limit 1 --json conclusion --jq '.[0].conclusion' | grep -q "success" || echo "⚠️  Latest CI run failed"

echo "✅ Pre-release validation complete!"
```

## Phase 3: Changelog Generation

### Changelog Structure

Follow [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-03-15

### Added
- **Traffic Flow Monitoring** - 15 new tools for real-time traffic analysis
  - Real-time flow monitoring with packet counts and connection details
  - Flow filtering by IP, protocol, application, time range
  - Connection state tracking (active, closed, timed-out)
  - Client traffic aggregation with top applications/destinations
  - Bandwidth rate calculations for streaming flows
  - Security quick-response capabilities (block suspicious IPs)
- **Zone-Based Firewall** - 7 new tools for zone management
  - Zone creation and management (Internal, External, Gateway, VPN zones)
  - Zone-to-zone traffic policies via zone matrix operations
  - Zone membership assignment for devices and networks
- **Type-safe Pydantic Models** - New data models for v0.2.0 features
  - TrafficFlow model with comprehensive fields
  - FirewallZone model for ZBF zones
  - Enhanced validation and type safety

### Changed
- Updated README.md with v0.2.0 features
- Improved test coverage from 37% to 60%
- Enhanced error handling in API client

### Deprecated
- 8 ZBF matrix tools - Zone policy matrix and application blocking endpoints do not exist in UniFi API v10.0.156
  - `get_zbf_matrix` - Use UniFi Console UI for zone policies
  - `update_zbf_policy` - Not available via API
  - `delete_zbf_policy` - Not available via API
  - `get_zone_policies` - Not available via API
  - `block_application_by_zone` - Not available via API
  - `unblock_application_by_zone` - Not available via API
  - `list_blocked_applications` - Not available via API
  - `get_zone_statistics` - Not available via API

### Fixed
- Fixed 3 failing config tests caused by .env file loading
- Resolved async/await issues in traffic flow tools
- Fixed cache invalidation for ZBF zone updates

### Security
- Updated dependencies to address security vulnerabilities
- Enhanced input validation for all new tools
- Added rate limiting for API requests

## [0.1.4] - 2025-01-17

### Fixed
- Version number correction (v0.2.0 was published prematurely)
- Documentation updates

[... Previous versions ...]
```

### Automated Changelog Generation

Generate changelog from git commits:

```python
# scripts/generate_changelog.py

import subprocess
from datetime import date

def get_commits_since_tag(tag):
    """Get commits since last tag."""
    cmd = f"git log {tag}..HEAD --oneline"
    result = subprocess.run(cmd.split(), capture_output=True, text=True)
    return result.stdout.strip().split('\n')

def categorize_commit(commit_message):
    """Categorize commit by conventional commit type."""
    if commit_message.startswith('feat:'):
        return 'Added'
    elif commit_message.startswith('fix:'):
        return 'Fixed'
    elif commit_message.startswith('docs:'):
        return 'Changed'
    elif commit_message.startswith('chore:'):
        return 'Changed'
    elif commit_message.startswith('test:'):
        return 'Changed'
    elif commit_message.startswith('refactor:'):
        return 'Changed'
    else:
        return 'Changed'

def generate_changelog_entry(version, commits):
    """Generate changelog entry for version."""
    today = date.today().strftime('%Y-%m-%d')

    entry = f"## [{version}] - {today}\n\n"

    # Group by category
    categories = {
        'Added': [],
        'Changed': [],
        'Deprecated': [],
        'Removed': [],
        'Fixed': [],
        'Security': []
    }

    for commit in commits:
        if not commit:
            continue
        category = categorize_commit(commit)
        # Remove commit hash and type prefix
        message = commit.split(' ', 1)[1]
        message = message.split(':', 1)[1].strip() if ':' in message else message
        categories[category].append(message)

    # Write non-empty categories
    for category, messages in categories.items():
        if messages:
            entry += f"### {category}\n"
            for msg in messages:
                entry += f"- {msg}\n"
            entry += "\n"

    return entry
```

## Phase 4: Release Execution

### Release Workflow

**Step 1: Create Release Branch**

```bash
# Create release branch
git checkout -b release/v0.2.0

# Update version in pyproject.toml
# Update version in src/__init__.py
# Update README.md with version
# Update DEVELOPMENT_PLAN.md progress

git add .
git commit -m "chore: prepare v0.2.0 release"
```

**Step 2: Update Documentation**

```bash
# Generate/update API.md
# (Use api-doc-generator skill)

# Update CHANGELOG.md with release notes
# (Use changelog generation)

# Update README.md features list

git add API.md CHANGELOG.md README.md
git commit -m "docs: update documentation for v0.2.0 release"
```

**Step 3: Run Final Validation**

```bash
# Run pre-release validation script
./scripts/pre-release-validation.sh

# Manual testing checklist
# - Test new ZBF tools
# - Test traffic flow monitoring
# - Verify deprecated tools marked correctly
# - Check Docker build
# - Verify examples in README work
```

**Step 4: Create Release PR**

```bash
# Push release branch
git push origin release/v0.2.0

# Create PR
gh pr create \
  --title "Release v0.2.0" \
  --body "$(cat <<'EOF'
## v0.2.0 Release

### Summary
This release adds Traffic Flow Monitoring and Zone-Based Firewall support.

### Changes
- 22 new tools (15 traffic flow, 7 ZBF zones)
- 8 deprecated tools (ZBF matrix endpoints don't exist in API)
- Type-safe Pydantic models for new features
- Test coverage improved from 37% to 60%

### Testing
- [x] All tests passing (219 tests)
- [x] Integration tests completed
- [x] Manual testing on UniFi Network v10.0.156
- [x] Documentation updated
- [x] Docker build succeeds

### Checklist
- [x] Version bumped in pyproject.toml
- [x] CHANGELOG.md updated
- [x] README.md updated
- [x] API.md updated
- [x] All CI checks passing
- [x] Pre-release validation passed

EOF
)" \
  --base main \
  --head release/v0.2.0
```

**Step 5: Merge and Tag**

```bash
# After PR approval, merge to main
gh pr merge release/v0.2.0 --squash

# Switch to main and pull
git checkout main
git pull

# Create and push tag
git tag -a v0.2.0 -m "Release v0.2.0: Traffic Flows + ZBF"
git push origin v0.2.0

# GitHub Actions will automatically:
# - Build Docker images
# - Push to GitHub Container Registry
# - Create GitHub Release
# - (Optional) Publish to PyPI
```

**Step 6: Create GitHub Release**

```bash
# Create GitHub release with changelog
gh release create v0.2.0 \
  --title "v0.2.0 - Traffic Flow Monitoring & Zone-Based Firewall" \
  --notes "$(cat <<'EOF'
# UniFi MCP Server v0.2.0

## 🎉 What's New

### Traffic Flow Monitoring (15 new tools)
Real-time traffic flow analysis and monitoring:
- Flow monitoring with packet counts and connection details
- Advanced filtering (IP, protocol, application, time range)
- Connection state tracking
- Client traffic aggregation
- Security quick-response (block suspicious IPs)

### Zone-Based Firewall (7 new tools)
Modern zone-based firewall management:
- Zone creation (Internal, External, Gateway, VPN)
- Network/device assignment to zones
- Zone management (create, read, update, delete)

## ⚠️  Important Notes

### Deprecated Tools
8 ZBF matrix tools are deprecated as the UniFi API endpoints do not exist in v10.0.156:
- Zone policy matrix operations
- Application blocking per zone
- Zone statistics

Please use UniFi Console UI for zone-to-zone policies until API support is available.

## 📊 Stats

- **Total Tools**: 77 (69 functional, 8 deprecated)
- **New Tools**: 22
- **Test Coverage**: 60% (up from 37%)
- **Tests**: 219 passing

## 🐳 Docker

```bash
docker pull ghcr.io/enuno/unifi-mcp-server:v0.2.0
docker pull ghcr.io/enuno/unifi-mcp-server:latest
```

## 📚 Documentation

- [README.md](README.md) - Getting started
- [API.md](API.md) - Complete API reference
- [CHANGELOG.md](CHANGELOG.md) - Full changelog

## 🙏 Contributors

Thanks to everyone who contributed to this release!

EOF
)"
```

## Phase 5: Post-Release

### Post-Release Checklist

**Verification:**
- [ ] GitHub release created successfully
- [ ] Docker images built and pushed
- [ ] PyPI package published (if applicable)
- [ ] Documentation deployed
- [ ] Release announcement drafted

**Communication:**
- [ ] Update project README with latest version
- [ ] Post release announcement (GitHub Discussions)
- [ ] Update UniFi MCP Server website (if exists)
- [ ] Notify users of breaking changes (if any)

**Cleanup:**
- [ ] Delete release branch
- [ ] Close completed issues/PRs
- [ ] Update project board
- [ ] Archive release notes

**Next Steps:**
- [ ] Create v0.2.1 milestone for pending features
- [ ] Update DEVELOPMENT_PLAN.md with v0.3.0 timeline
- [ ] Begin Sprint 1 of next version

### Version Bump for Development

```bash
# Bump to next development version
# Update pyproject.toml: version = "0.3.0-dev"

git add pyproject.toml
git commit -m "chore: bump version to v0.3.0-dev"
git push
```

## Integration with Other Skills

- **Before release**: Use `test-strategy` to ensure coverage targets met
- **During release**: Use `api-doc-generator` to update documentation
- **After release**: Plan next version with DEVELOPMENT_PLAN.md

## Reference Files

Load for context:
- `DEVELOPMENT_PLAN.md` - Release milestones and progress
- `TODO.md` - Feature completion status
- `CHANGELOG.md` - Release history
- `pyproject.toml` - Version configuration
- `.github/workflows/release.yml` - Release automation

## Success Metrics

Release successful when:
- [ ] All pre-release validation passed
- [ ] Documentation complete and accurate
- [ ] GitHub release created
- [ ] Docker images available
- [ ] No critical bugs in first 48 hours
- [ ] Users can upgrade smoothly
- [ ] Announcement published
