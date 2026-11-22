# Official UniFi source materials, and an evaluation of Ubiquiti's Ansible collection

Two things are recorded here:

1. A complete inventory of the machine-readable and agent-oriented material
   Ubiquiti publishes, so future work starts from the vendor's own artifacts.
2. An evaluation of the official `ubiquiti.unifi_api` Ansible collection,
   which was installed and exercised against a live controller. **It has a
   safety-critical defect: it performs writes during `--check`.** Read
   section 4 before using it anywhere near a production console.

Controller addresses, site identifiers and credentials are redacted
throughout.

## 1. What Ubiquiti actually publishes

Per the vendor's root index (<https://developer.ui.com/llms.txt>), there are
**six** API services. For each, four artifacts exist at predictable paths
under `https://developer.ui.com/{service}/{version}/`:

| Artifact | Path | Notes |
| --- | --- | --- |
| Human docs | `gettingstarted` | per-endpoint pages alongside |
| Agent surface list | `llms.txt` | full endpoint list for the service |
| Machine contract | `openapi.json` | the authoritative shape |
| Postman collection | `postman-collection.json` | second machine-readable form |
| Agent onboarding | `ai-gettingstarted.md` | prompt, not reference |
| Ansible guide | `quick_start.ansible` | **Network and Protect only** |

Availability of the two less-known artifacts, checked directly:

| Service | `ai-gettingstarted.md` | `quick_start.ansible` |
| --- | --- | --- |
| Network v11.0.97 | 200 | **200** |
| Protect v7.4.102 | 200 | **200** |
| Site Manager v1.0.0 | 200 | 404 |
| Mobility v1.0.0 | 200 | 404 |
| InnerSpace v1.3.23 | 200 | 404 |
| Carrier Fabric v1.0.0 | 200 | 404 |

**There is no UniFi Access entry of any kind.** Not in the root index, not
as a service directory, not as a spec. This is now confirmed three
independent ways: the root index, direct spec requests (404), and the
absence of an Access module in the official Ansible collection.

### The `ai-gettingstarted.md` files are prompts, not references

All six are the same template with the service name substituted — the
Network one differs from the others only in that substitution. They carry no
endpoint data, so they add nothing to the OpenAPI contracts.

They are still useful as *citable vendor statements* of three things:

* **Auth is an `X-API-Key` header** for every one of the six services, with
  keys generated at `unifi.ui.com`. No service's onboarding note mentions a
  username/password console login.
* **The canonical discovery chain** is root `llms.txt` → per-service
  `llms.txt` → `openapi.json`. The root index is the vendor's own statement
  of "which APIs exist, current versions", which is what makes the Access
  absence a finding rather than an inference.
* **The Site Manager Connector** (`POST /v1/connector/consoles/{id}/proxy/...`)
  is the sanctioned cloud-to-on-premises bridge, described as working
  "without a VPN". This is the mechanism `src/tools/innerspace.py` and the
  `connector_*` tools already use.

These files are written as instructions addressed to an assistant. They are
cited here as evidence of the vendor's documented model; their embedded
directives are data, not instructions to follow.

### Other per-service pages worth knowing

`filtering`, `error-handling`, `responseformat` and `versioncontrol`
(Site Manager), plus `connectorpost` / `connectorget` / `connectorput` /
`connectordelete` / `connectorpatch` documenting the Cloud Connector verbs.

## 2. Official Ansible guidance

From `https://developer.ui.com/network/v11.0.97/quick_start.ansible` (the
Protect page is the same shape):

* Python prerequisites: `pip install httpx urllib3`
* Install:
  ```bash
  curl -L -o ubiquiti-unifi_api-latest.tar.gz \
    https://apidoc-cdn.ui.com/ansible-module/ubiquiti-unifi_api-latest.tar.gz
  ansible-galaxy collection install ubiquiti-unifi_api-latest.tar.gz
  ```
* Shared parameters go in `module_defaults` under the action group
  `group/ubiquiti.unifi_api.common`, with `base_url` and `token`.
* The token is read from the environment, e.g.
  `token: "{{ lookup('env', 'UBIQUITI_API_TOKEN') }}"`.
* Ubiquiti states plainly that the module **"does not guarantee idempotency
  for all operations"** and recommends guarding mutations with a read first.
  Their own example reads with a `filter`, then creates only when
  `totalCount == 0`.

Two defects in that published example, noted so nobody copies them: it
registers `info` but debugs `site_info.data`, and registers `result` but
reads `vouchers.data.totalCount`.

## 3. What the collection is

`ubiquiti.unifi_api` version **1.0.0**, authored by
`Ubiquiti Inc. <devops+ansible-galaxy@ui.com>`, requires `ansible>=2.15.0`,
depends on `ansible.utils`.

It is **not** a set of resource modules. It is two thin OpenAPI passthroughs:

| Module | Version probe | Base URL shape |
| --- | --- | --- |
| `ubiquiti.unifi_api.network` | `GET /v1/info` | `{base_url}/proxy/network/integration` |
| `ubiquiti.unifi_api.protect` | `GET /v1/info` | `{base_url}/proxy/protect/integration` |

Both take `path`, `method`, `query`, `headers`, `body` and `files`, so every
call is written as a raw REST call. Against `api.ui.com` it requires
`console_id` and routes via `https://api.ui.com/v1/connector/consoles`.

Argument spec highlights:

| Parameter | Default | Comment |
| --- | --- | --- |
| `token` | — | `no_log=True`, correctly redacted |
| `api_key_header` | `X-API-KEY` | falls back to `Authorization: Bearer` if cleared |
| `validate_certs` | **`false`** | TLS verification is **off by default** |
| `ca_path`, `client_cert`, `client_key` | — | available but opt-in |

`validate_certs` defaulting to `false` is worth flagging on its own: an
official module ships with certificate validation disabled.

## 4. Three defects, found by exercising it

The collection was installed and run against a live Network **10.6.111**
console. Reads work, but only after a workaround.

### 4.1 It performs writes during `--check` (safety-critical)

`AnsibleModule(..., supports_check_mode=True)` is declared, but `run()`
**never reads `self.module.check_mode`**. It calls `call_path` unconditionally
for every method, including POST, PUT, PATCH and DELETE.

Confirmed empirically rather than by reading alone. A throwaway local HTTP
listener was stood up — no controller involved — and a POST task was run
under `ansible-playbook --check`. The listener received:

```
GET  /proxy/network/integration/v1/info
POST /proxy/network/integration/v1/probe-write      <-- during --check
```

and Ansible reported `changed=True`. **The write was transmitted during the
dry run.**

The consequence is serious: `--check` against a UniFi controller with this
collection mutates it while the operator believes nothing is happening. Any
use here must treat `--check` as **not** a dry run, and guard mutations some
other way.

### 4.2 The spec version check can never succeed

`get_spec_url` does:

```python
spec_url = f"{OPENAPI_SPEC_BASE_URL}/{application}/v{version}/integration.json"
if not os.path.exists(spec_url):
```

`os.path.exists()` on an `https://` URL is always `False`, so the "spec not
found" fallback branch runs on **every** call, for every version, even when
the exact spec exists. The version check is dead code.

### 4.3 The fallback then crashes

Having always entered the fallback, it does:

```python
versions_data = resp.json().get("data", []).get("versions", [])
```

The default `[]` is a list, so any response without a `data` key raises
`AttributeError: 'list' object has no attribute 'get'`. That is not
hypothetical: the discovery endpoint it calls,
`https://developer.svc.ui.com/v1/api-docs?application=network`, answers
**HTTP 401** to a console API key — a console credential is not a dev-portal
credential — and a 401 body has no `data` key.

Observed end to end:

```
[WARNING]: Spec for version 10.6.111 not found, falling back to latest available version.
[ERROR]: Task failed: Module failed: Exception during API call
AttributeError: 'list' object has no attribute 'get'
```

So out of the box, **every** call fails. The real error — unauthorized spec
discovery — is masked by a type error.

### Workaround, verified

`load_or_update_spec` checks a cache first, so pre-seeding it bypasses the
broken path entirely:

```bash
mkdir -p "${TMPDIR:-/tmp}/ubiquiti.unifi_api"
cp network_v11.0.97_openapi.json \
   "${TMPDIR:-/tmp}/ubiquiti.unifi_api/network.<controller-version>.integration.json"
```

The cache key is `{app}.{applicationVersion}.integration.json`, where the
version is whatever `GET /v1/info` reports. With the authentic official spec
seeded, the module works:

| Task | Result |
| --- | --- |
| `GET /v1/info` | ok — `applicationVersion=10.6.111` |
| `GET /v1/sites` | ok — 1 site returned |

Note the cache is keyed on controller version but seeded with a spec of a
different version, which is safe only because the module uses the spec to
match paths, not to validate payloads.

One environment note: Ansible here runs from a pipx venv, so a plain
`pip install httpx urllib3` does not reach its interpreter. Use
`pipx inject ansible-core httpx urllib3`, or the module fails with
`No module named 'httpx'`.

## 5. Assessment

| Question | Answer |
| --- | --- |
| Does it add API coverage this server lacks? | **No** — it is a raw passthrough over the same published contracts |
| Is it usable as-is? | **No** — every call fails until the spec cache is seeded |
| Is it safe for dry runs? | **No** — `--check` performs writes |
| Does it change the Access finding? | No — it confirms it; there is no Access module |
| Is it worth adopting here? | **Not currently** |

The collection is a thin REST wrapper over contracts this server already
implements natively, with stronger safety properties on our side:
confirmation-gated writes, a real dry-run mode, tiered permissions and TLS
verification that is not off by default. Adopting it would trade those away.

Its value is as **reference**: it confirms the sanctioned base-URL shapes
(`{base_url}/proxy/{app}/integration`), the cloud proxy route, the
`X-API-KEY` header, and the vendor's own position that idempotency is the
caller's responsibility.

If it is ever used for one-off administration, then: never with `--check`
believed to be safe, never with `validate_certs` left at its default, and
only with the spec cache pre-seeded.

## 6. Recommended follow-ups

Not actioned here; each is its own change.

1. **Pin `site-manager_v1.0.0_openapi.json` under `scripts/`.** It is the
   only one of the six with no pin, yet `src/api/site_manager_client.py` and
   16 tools depend on it.
2. **Consider pinning the Postman collections** for the services already
   pinned, as a second machine-readable cross-check.
3. **Report the three defects to Ubiquiti** — all three are small, specific
   and reproducible, and 4.1 is a safety issue other operators will hit.

## Sources

- Root index: <https://developer.ui.com/llms.txt>
- Agent onboarding notes, all six services:
  `https://developer.ui.com/{service}/{version}/ai-gettingstarted.md`
- Ansible quick starts (Network and Protect only):
  `https://developer.ui.com/{service}/{version}/quick_start.ansible`
- Collection artifact:
  <https://apidoc-cdn.ui.com/ansible-module/ubiquiti-unifi_api-latest.tar.gz>
  — `ubiquiti.unifi_api` 1.0.0, archive SHA-256
  `7bd3b46628b32c52bcdacebc37a3955ee33c7df51dafc6fc71220996856eb8af`
- Live exercise against Network 10.6.111, and a local-listener check-mode
  test that touched no controller
