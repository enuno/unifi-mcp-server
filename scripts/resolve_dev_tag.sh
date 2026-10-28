#!/usr/bin/env bash
# Prints the tag a local-checkout build gets: local-<short-sha>[-dirty-<diffhash>].
#
# Shared by scripts/helm_deploy_local.sh and the unifi_mcp Ansible role's
# local-checkout mode (deploy/ansible/inventories/dev-local), so both
# deployment methods agree on one tag format instead of inventing their
# own. "-dirty-<diffhash>" is a deliberate, unmissable signal that the
# running image does not correspond to any committed, reviewable state --
# never silently collapse it into the clean-tree tag. The diff hash (not
# just "-dirty") is what gives two successive edits to an already-dirty
# checkout two different tags, so a later edit is never mistaken for an
# already-deployed one under a reused tag.
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
  diffhash="$( { git -C "$repo" diff -- .; git -C "$repo" diff --cached -- .; } \
    | git hash-object --stdin | cut -c1-8)"
  echo "local-${sha}-dirty-${diffhash}"
fi
