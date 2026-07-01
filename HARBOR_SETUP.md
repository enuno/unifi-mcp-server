# HARBOR_SETUP

Operator runbook for private registry workflows used to build, promote, and distribute UniFi MCP Server images.

## Purpose

Support air-gapped, edge, and controlled-release deployments that require immutable image tags, promotion gates, and reliable offline distribution.

## When to use this runbook

- You need to publish a release image to a private registry.
- You need to mirror a release into an isolated environment.
- You need to promote a tested build from staging to production.
- You need to validate TLS trust and credential handling before rollout.

## Required inputs

- Registry hostname and namespace
- Image name and version tag
- Push credentials with the minimum required scope
- Trust-store approach for any internal CA
- Release promotion target and approval state

## Operating model

Use Harbor or an equivalent OCI registry with the following properties:

- immutable release tags
- retention policy for old artifacts
- role-based access to push and pull
- TLS enabled on every registry endpoint
- separate namespaces for build, staging, and production artifacts

## Baseline workflow

1. Build the image from the approved source revision.
2. Tag the image with an immutable release tag and a short-lived staging tag if needed.
3. Push to the private registry.
4. Verify the digest after push.
5. Promote the image only after verification passes.
6. Pull the image from the target environment before any runtime rollout.

## Registry prerequisites

Before the first release:

- Confirm DNS resolution for the registry hostname.
- Confirm TLS certificates chain to a trusted CA.
- Confirm the service account can push to the target namespace.
- Confirm developers and CI systems cannot overwrite immutable release tags.

## Image naming and tagging conventions

Recommended convention:

- `unifi-mcp-server:<semver>` for release tags
- `unifi-mcp-server:<semver>-rc.<n>` for release candidates
- `unifi-mcp-server:sha-<shortsha>` for build provenance
- `unifi-mcp-server:latest` only if your release process explicitly allows it

Rules:

- prefer immutable tags for production promotion
- always record the digest alongside the tag
- do not treat `latest` as a deployment target of record

## Push and pull procedure

1. Authenticate to the registry with a scoped credential.
2. Push the tagged image.
3. Verify the registry reports the expected digest.
4. Pull the image into a clean runtime environment.
5. Start the container and confirm the expected entrypoint and health behavior.

## Credential handling

- Store registry credentials in the secret manager used by your deployment system.
- Do not commit credentials into `.env` or compose files.
- Prefer short-lived tokens or robot accounts with namespace-limited access.
- Rotate credentials on a fixed cadence and on personnel changes.

## TLS and trust-store setup

If the registry uses an internal CA:

- install the CA into the host trust store or container trust store
- verify `docker login` and `docker pull` do not prompt for certificate overrides
- reject any deployment path that requires disabling certificate validation

## Promotion flow

A safe promotion process should look like this:

1. Build once.
2. Scan once.
3. Test once.
4. Promote by digest, not by rebuilding.
5. Deploy the same digest through staging and production.

This avoids registry drift and prevents “same tag, different artifact” failures.

## Retention policy guidance

- keep production releases long enough for rollback windows
- keep build cache tags for a limited time only
- prune temporary candidate tags after the release is finalized
- retain the digest history for audit and rollback reference

## Verification checklist

- Registry login succeeds without certificate warnings.
- Image push completes and returns the expected digest.
- Pull by digest works from the target environment.
- The container starts with the expected runtime configuration.
- The health check reaches green before promotion.

## Rollback

If promotion fails:

- redeploy the last known-good digest
- do not retag a broken build as a release artifact
- preserve the failed artifact for triage until the root cause is identified

## Common failure modes

- registry TLS trust mismatch
- expired or over-scoped credentials
- accidental overwrite of a mutable tag
- image digest mismatch between build and deployment environments
- promotion performed by tag instead of digest

## Related tooling

- `Makefile` targets for build, test, push, and release
- `docker-compose.yml` for local service orchestration
- registry-specific deployment manifests or CI jobs

## Status

Phase-4 documentation.