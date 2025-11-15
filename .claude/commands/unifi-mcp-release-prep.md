---
description: Prepare a new release with version bump, changelog, and quality checks
allowed-tools:
  - Read
  - Edit
  - Grep
  - Glob
  - Bash(git:*)
  - Bash(pytest:*)
  - Bash(black:*)
  - Bash(ruff:*)
  - Bash(mypy:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/pytest:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/black:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/ruff:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/mypy:*)
author: project
version: 1.0.0
---

Prepare a new release for the UniFi MCP Server with comprehensive quality checks.

This command orchestrates the complete release preparation process including version bumping, changelog generation, testing, and validation.

**Steps to execute:**

1. Ask user for release details:
   - Version number (e.g., "0.2.0") or type (major/minor/patch)
   - Release type: major, minor, patch, or custom
   - Brief release description

2. Verify current state:
   - Check git status (must be clean or on release branch)
   - Verify on main branch or create release branch
   - Check for uncommitted changes
   - Ensure all tests pass

3. Run comprehensive quality checks:
   - Code formatting: `black --check src/ tests/`
   - Import sorting: `isort --check-only src/ tests/`
   - Linting: `ruff check src/ tests/`
   - Type checking: `mypy src/`
   - Security scan: `bandit -r src/ -ll`
   - Dependency check: `safety check`

4. Run full test suite with coverage:
   - Execute: `pytest --cov=src --cov-report=term-missing -v`
   - Verify coverage meets 80% minimum threshold
   - Check that all tests pass
   - If coverage < 80%, warn user and ask to proceed

5. Update version numbers:
   - Update `pyproject.toml` version field
   - Update `src/__init__.py` __version__
   - Update version in README.md badges
   - Update Docker image tags in documentation

6. Generate changelog:
   - Get commits since last tag: `git log $(git describe --tags --abbrev=0)..HEAD --oneline`
   - Categorize commits:
     - Features (feat:)
     - Bug fixes (fix:)
     - Documentation (docs:)
     - Refactoring (refactor:)
     - Tests (test:)
     - Other changes
   - Update CHANGELOG.md with new version section

7. Update documentation:
   - Run /unifi-mcp-update-docs to sync API.md
   - Verify README.md is current
   - Check that examples still work
   - Update compatibility matrix if needed

8. Create release summary:
   - Version number
   - Release date
   - Highlights (top 3-5 features/fixes)
   - Breaking changes (if any)
   - Contributors
   - Full changelog

9. Prepare release artifacts:
   - Tag format: `v{version}` (e.g., v0.2.0)
   - Release branch: `release/v{version}` (if not on main)
   - Draft GitHub release notes

**Report back with:**

- Pre-release checklist status:
  - [ ] All tests passing
  - [ ] Coverage >= 80%
  - [ ] No linting errors
  - [ ] No type errors
  - [ ] No security vulnerabilities
  - [ ] Documentation updated
  - [ ] Changelog generated
  - [ ] Version bumped

- Release summary
- Next steps:
  - Review changes
  - Create release tag
  - Push to GitHub
  - Create GitHub release
  - Publish to PyPI (optional)
  - Build and push Docker images

**Example workflow:**

```bash
User: "Prepare release 0.2.0"

Assistant checks:
✓ Git status clean
✓ On main branch
✓ All tests pass (179/179)
✗ Coverage: 34.10% (below 80% target)
✓ No linting errors
✓ No type errors
✓ No security issues

Release Summary:
Version: 0.2.0
Date: 2025-01-15
Type: Minor release

Highlights:
- Zone-Based Firewall implementation (60% complete)
- Traffic Flows integration (100% complete)
- 22 new tool modules
- Comprehensive CI/CD pipeline

Breaking Changes: None

Warning: Test coverage (34.10%) is below 80% target.
Proceed with release? (y/n)
```

**Safety checks:**

- Never release with failing tests
- Warn if coverage < 80%
- Verify no uncommitted changes
- Check for security vulnerabilities
- Confirm version number doesn't already exist
