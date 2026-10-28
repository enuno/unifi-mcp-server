#!/usr/bin/env bash
# Prints the tag a local-checkout build gets: local-<short-sha>[-dirty].
#
# Shared by scripts/helm_deploy_local.sh and the unifi_mcp Ansible role's
# local-checkout mode (deploy/ansible/inventories/dev-local), so both
# deployment methods agree on one tag format instead of inventing their
# own. "-dirty" is a deliberate, unmissable signal that the running image
# does not correspond to any committed, reviewable state — never silently
# collapse it into the clean-tree tag.
#
# Usage: scripts/resolve_dev_tag.sh [REPO_PATH]
#   REPO_PATH defaults to the directory this script lives in (its repo
#   root), so it can be called from any working directory.
set -euo pipefail

repo="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

sha="$(git -C "$repo" rev-parse --short=12 HEAD)"

if git -C "$repo" diff --quiet -- . && git -C "$repo" diff --cached --quiet -- .; then
  echo "local-${sha}"
else
  echo "local-${sha}-dirty"
fi
