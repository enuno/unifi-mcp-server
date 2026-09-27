#!/usr/bin/env python3
"""audit-spec-coverage.py — field-level drift audit of Integration API call sites.

Compares every /v1/ path literal and f-string in src/tools/ against the
pinned Network Integration API spec snapshot, then compares request-body
field sets for operations that carry one. Re-run after each spec refresh
(scripts/fetch-specs.sh); see .analysis-reports/api-spec-audit-2026-09-26.md
for the findings this produced originally.

Usage: python3 scripts/audit-spec-coverage.py [--spec scripts/scraped-api-spec-v10.6.106.json]
Exit code 0 always; findings are printed for human triage.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec_path = Path(sys.argv[sys.argv.index("--spec") + 1]) if "--spec" in sys.argv else ROOT / "scripts/scraped-api-spec-v10.6.106.json"
spec = json.load(open(spec_path))
comps = spec.get("components", {}).get("schemas", {})


def resolve(schema, depth=0):
    """Resolve $ref chain; return (properties, required) for object schemas."""
    if depth > 6 or not isinstance(schema, dict):
        return {}, []
    if "$ref" in schema:
        return resolve(comps.get(schema["$ref"].split("/")[-1], {}), depth + 1)
    return schema.get("properties", {}) or {}, schema.get("required", []) or []


def norm(p: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", p)


# 1. Spec operations
ops = []
for path, methods in spec.get("paths", {}).items():
    for m, op in methods.items():
        if m.lower() not in ("get", "post", "put", "patch", "delete"):
            continue
        rb = op.get("requestBody", {}).get("content", {})
        body = next((rb[ct]["schema"] for ct in ("application/json", "application/*+json")
                     if ct in rb and "schema" in rb[ct]), None)
        props, req = resolve(body) if body else ({}, [])
        ops.append({"method": m.upper(), "path": path, "summary": op.get("summary", ""),
                    "tags": op.get("tags", []), "has_body": bool(body),
                    "body_props": sorted(props), "body_req": req})

# 2. Code literals (canonical cloud form carries the /integration prefix;
#    spec paths drop it — normalize both away)
code_paths = defaultdict(list)
pat = re.compile(r'["\'](/[^"\']*(?:integration/v\d+|/v1/)[^"\']*)["\']')
for f in sorted((ROOT / "src/tools").glob("*.py")):
    for i, line in enumerate(open(f), 1):
        for match in pat.finditer(line):
            raw = match.group(1)
            norm_raw = norm(re.sub(r"^/integration/v\d+", "/v1", raw))
            code_paths[norm_raw].append((f.name, i, raw))

# 3. Report
print("=== A. Spec operations vs code matches (NO-CODE-MATCH = not called via Integration API) ===")
for op in ops:
    hits = code_paths.get(norm(op["path"]), [])
    locs = "; ".join(f"{h[0]}:{h[1]}" for h in hits[:3])
    print(f"{op['method']:6s} {op['path']:58s} body={op['has_body']!s:5s} "
          f"{'NO-CODE-MATCH' if not hits else locs}")

print("\n=== B. Code Integration-API literals NOT in spec (path drift suspects) ===")
spec_norms = {norm(o["path"]) for o in ops}
drift = False
for n, hits in sorted(code_paths.items()):
    if n not in spec_norms:
        drift = True
        for h in hits[:2]:
            print(f"  {h[0]}:{h[1]} {h[2]}")
if not drift:
    print("  none")

print("\n=== C. Spec request-body field sets (comparison targets) ===")
for op in ops:
    if op["has_body"]:
        print(f"{op['method']:6s} {op['path']:50s} required={op['body_req']} props={op['body_props']}")
