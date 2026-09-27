#!/usr/bin/env bash
# fetch-specs.sh — download canonical UniFi API spec snapshots from developer.ui.com.
#
# Modern replacement for the puppeteer scrapers (scraper/scrape-api-docs.js,
# update-api-docs.js): Ubiquiti now publishes machine-readable artifacts per
# service/version (openapi.json, llms.txt, Postman collections) at
# https://developer.ui.com/{service}/{version}/ — no portal auth, no browser.
#
# Only the CURRENT version of each spec is hosted; older versions 404. Keep the
# downloaded snapshots in git (force-add if .gitignore patterns block them) —
# they are the diff baseline for future audits. Re-audit quarterly per
# DEVELOPMENT_PLAN.md P10.
set -euo pipefail
cd "$(dirname "$0")"

# Pinned spec baseline (last audited 2026-09-26; check https://developer.ui.com/llms.txt for current versions).
SERVICES=(
  "network:10.6.106:scraped-api-spec-v10.6.106.json"
  "protect:7.3.68:protect-api-spec-v7.3.68.json"
  "mobility:1.0.0:mobility-api-spec-v1.0.0.json"
  "innerspace:1.3.23:innerspace-api-spec-v1.3.23.json"
  "carrier-fabric:1.0.0:carrier-fabric-api-spec-v1.0.0.json"
)

fail=0
for entry in "${SERVICES[@]}"; do
  IFS=: read -r svc ver outfile <<<"$entry"
  url="https://developer.ui.com/${svc}/v${ver}/openapi.json"
  if curl -sfL -o "$outfile" "$url"; then
    echo "OK   $svc v$ver -> $outfile ($(stat -c%s "$outfile") bytes)"
  else
    echo "FAIL $svc v$ver ($url) — version unpublished or network error" >&2
    fail=1
  fi
done

# Endpoint index for the Network spec (useful for quick coverage greps).
network_ver=$(IFS=: read -r _ v _ <<<"${SERVICES[0]}"; echo "$v")
curl -sfL -o "network-v${network_ver}-llms.txt" "https://developer.ui.com/network/v${network_ver}/llms.txt" \
  && echo "OK   network llms.txt -> network-v${network_ver}-llms.txt" || echo "WARN network llms.txt fetch failed (non-fatal)"

exit $fail
