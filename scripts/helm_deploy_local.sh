#!/usr/bin/env bash
# Build the current working tree into an image, get it into a cluster's
# runtime, and install/upgrade deploy/helm/unifi-mcp against it.
#
# Unlike scripts/helm_smoke_test.sh (CI-only, kind-only, throwaway
# namespace), this is for a real, persistent dev/staging deployment of
# whatever is checked out right now -- including uncommitted changes. It
# never deletes anything on exit.
#
#   scripts/helm_deploy_local.sh --namespace NS --release NAME \
#     [--extras fleet] [--target k3s|kind|push] [--kind-cluster NAME] \
#     [--registry REPO] [--values FILE ...] [-- EXTRA_HELM_ARGS...]
#
# --target k3s   (default) docker build, then `k3s ctr images import`
#                (needs root for the containerd socket -- the script sudos
#                explicitly, it does not silently escalate anything else).
# --target kind  docker build, then `kind load docker-image` (same path
#                scripts/helm_smoke_test.sh uses, for dev against a kind
#                cluster instead of a real k3s host).
# --target push  docker build, then `docker push` to --registry. Refuses
#                to push to ghcr.io/enuno/unifi-mcp-server (the release
#                workflow's own path) unless
#                --i-know-this-overwrites-releases is also given.
#
# --values can repeat; each is passed to `helm upgrade --install -f`,
# layered after deploy/helm/unifi-mcp/ci/local-build-values.yaml so the
# caller's real secrets/config (existingSecret, controller.localHost, ...)
# still apply. The image repository/tag/pullPolicy this script resolves
# always win -- they are set last, after every -f file.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chart="$here/../deploy/helm/unifi-mcp"
local_values="$chart/ci/local-build-values.yaml"

namespace=""
release="unifi-mcp"
extras=""
target="k3s"
kind_cluster="kind"
registry=""
allow_release_overwrite=0
values_files=()
extra_helm_args=()

while [ $# -gt 0 ]; do
  case "$1" in
    --namespace) namespace="$2"; shift 2 ;;
    --release) release="$2"; shift 2 ;;
    --extras) extras="$2"; shift 2 ;;
    --target) target="$2"; shift 2 ;;
    --kind-cluster) kind_cluster="$2"; shift 2 ;;
    --registry) registry="$2"; shift 2 ;;
    --values) values_files+=("$2"); shift 2 ;;
    --i-know-this-overwrites-releases) allow_release_overwrite=1; shift ;;
    --) shift; extra_helm_args+=("$@"); break ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$namespace" ] || { echo "--namespace is required" >&2; exit 2; }

case "$target" in
  k3s|kind|push) ;;
  *) echo "--target must be k3s, kind or push" >&2; exit 2 ;;
esac

if [ "$target" = push ] && [ -z "$registry" ]; then
  echo "--target push needs --registry" >&2
  exit 2
fi
if [ "$target" = push ] && [ "$registry" = "ghcr.io/enuno/unifi-mcp-server" ] \
   && [ "$allow_release_overwrite" -ne 1 ]; then
  echo "refusing: --registry ghcr.io/enuno/unifi-mcp-server is the release workflow's own path." >&2
  echo "pass --i-know-this-overwrites-releases if that is really the intent." >&2
  exit 2
fi

tag="$("$here/resolve_dev_tag.sh" "$here/..")"
case "$target" in
  k3s|kind) repo="unifi-mcp-server" ;;
  push) repo="$registry" ;;
esac
image="${repo}:${tag}"

echo "--- building ${image} (EXTRAS=${extras:-<none>})"
docker build ${extras:+--build-arg "EXTRAS=$extras"} -t "$image" "$here/.."

case "$target" in
  k3s)
    echo "--- importing into k3s's containerd (needs root)"
    docker save "$image" | sudo k3s ctr images import -
    pull_policy=Never
    ;;
  kind)
    echo "--- loading into kind cluster '${kind_cluster}'"
    kind load docker-image "$image" --name "$kind_cluster"
    pull_policy=Never
    ;;
  push)
    echo "--- pushing to ${registry}"
    docker push "$image"
    pull_policy=IfNotPresent
    ;;
esac

helm_values_args=(-f "$local_values")
for f in "${values_files[@]:-}"; do
  [ -z "$f" ] || helm_values_args+=(-f "$f")
done

echo "--- helm upgrade --install ${release} -n ${namespace} (image ${image}, pullPolicy ${pull_policy})"
helm upgrade --install "$release" "$chart" --namespace "$namespace" --create-namespace \
  "${helm_values_args[@]}" \
  --set "image.repository=${repo}" --set "image.tag=${tag}" --set "image.pullPolicy=${pull_policy}" \
  "${extra_helm_args[@]:-}"

kubectl -n "$namespace" rollout status "deployment/${release}-unifi-mcp" --timeout=300s

deployed_image="$(kubectl -n "$namespace" get "deployment/${release}-unifi-mcp" \
  -o jsonpath='{.spec.template.spec.containers[0].image}')"
echo "--- deployed image: ${deployed_image}"
[ "$deployed_image" = "$image" ] || {
  echo "warning: deployed image (${deployed_image}) does not match the built tag (${image})" >&2
  exit 1
}

echo "deployed ${image} as ${release} in namespace ${namespace}."
echo "a later commit needs a re-run: the tag only changes with the tree, Kubernetes will not notice"
echo "an in-place image change under the same tag with pullPolicy ${pull_policy}."
