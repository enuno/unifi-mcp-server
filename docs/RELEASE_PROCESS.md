# Release Process

This document describes the release process for the UniFi MCP Server.

## Overview

Releases are published through GitHub Actions with optional manual steps for package registries. The process is intentionally lightweight so it can support frequent patch releases and larger roadmap milestones.

## Release workflow

### 1. Tag the release

Create and push a semantic version tag for the version you are shipping:

```bash
git tag -a v0.2.5 -m "Release v0.2.5"
git push origin v0.2.5
```

Tagging rules:
- Use semantic versioning: `vMAJOR.MINOR.PATCH`
- Prefix every tag with `v`
- Match the tag to the version recorded in `pyproject.toml` and the release notes

### 2. GitHub Actions validation

After the tag is pushed, the release workflow should:

1. Run the full test suite
2. Run the security scans
3. Build multi-arch Docker images
4. Publish container images to GitHub Container Registry
5. Create the GitHub release entry
6. Publish the wheel and sdist to PyPI using the repository's trusted publisher
7. Generate or attach release notes

### 3. Manual publishing steps

The release workflow publishes the Python package and container images after
the blocking test and security gates pass. Do not upload a second copy from a
workstation.

#### PyPI

PyPI publication is performed by `pypa/gh-action-pypi-publish` with the
repository Actions secret `PYPI_RELEASE_KEY`, whose value is maintained in the
Bitwarden secrets project. The workflow uses the PyPI token as `__token__` and
publishes only after the build-and-test job succeeds. If PyPI trusted
publishing is configured later, replace the token inputs with OIDC and remove
the secret after verifying the new publisher claims.

#### Docker images

```bash
docker pull ghcr.io/enuno/unifi-mcp-server:latest
docker pull ghcr.io/enuno/unifi-mcp-server:0.7.0        # semver tags have no leading v
docker pull ghcr.io/enuno/unifi-mcp-server:0.7.0-fleet  # with the fleet extras (amd64, arm64)
```

#### npm (metadata wrapper)

```bash
# Ensure package.json is up to date
cat package.json

# Login to npm (if not already)
npm login

# Publish package
npm publish --access public

# Verify publication
npm view unifi-mcp-server
```

#### MCP Registry

```bash
# Install mcp-publisher
brew install mcp-publisher
# Or: curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/

# Authenticate with GitHub (for io.github.enuno namespace)
mcp-publisher login github

# Publish to registry (requires npm package published first)
mcp-publisher publish

# Verify
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.enuno/unifi-mcp-server"
```

---

## Pre-release checklist

### Code quality
- [ ] All tests pass locally
- [ ] Coverage meets target (≥80%)
- [ ] Linting passes (`ruff`)
- [ ] Type checking passes (`mypy`)
- [ ] Formatting is clean

### Security
- [ ] `bandit` passes
- [ ] Dependency scan is clean
- [ ] Secret scanning is clean
- [ ] Docker image scan is clean

### Documentation
- [ ] `README.md` matches the current release posture
- [ ] `ROADMAP.md` and `TODO.md` match `DEVELOPMENT_PLAN.md`
- [ ] `API.md` and `UNIFI_API.md` match the implemented surface
- [ ] Release notes are written and linked

### Verification
- [ ] Docker image starts successfully
- [ ] MCP inspector or equivalent smoke test passes
- [ ] Real hardware verification is complete when the change affects live device behavior

---

## Post-release verification

After publishing, verify the release artifacts:

- Pull the tagged Docker image and confirm the server starts
- Install the published Python package and confirm the reported version
- Confirm the GitHub release points at the expected commit/tag
- Confirm the release notes describe the shipped changes accurately

---

## Rollback procedures

If a bad release is published:

1. Delete or retag only if the release has not been broadly consumed
2. Yank the PyPI package if necessary
3. Deprecate or retract the Docker tag if the registry workflow allows it
4. Publish a patch release with the fix and clear notes

---

## Notes

- Keep release steps simple and repeatable.
- Do not hardcode old version numbers into new releases.
- Treat documentation sync as part of release readiness, not an afterthought.
