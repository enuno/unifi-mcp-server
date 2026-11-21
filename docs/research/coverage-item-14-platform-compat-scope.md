# Coverage item 14 — can `platform_compat` extend to cloud or unsynced controllers?

**Status:** gap-with-negative-finding, with the precise limit identified. No
code change is made, because no signal exists to extend it with.

**Question from the brief:** check whether any signal can extend
`platform_compat` to cloud or unsynced controllers; if none exists, document
the limit and stop.

## Summary

**No signal can extend `platform_compat` to a cloud controller, and none is
needed for an unsynced local one.** The limit is not in the analysis but in
the **collection**: the USG signal `platform_compat` is built from is the
synced device inventory, and the worker only collects that for local
controllers.

## The field and its one signal

`fleet_health` reports `platform_compat` on a controller:

```json
{"network_11_capable": false, "reason": "..."}
```

The signal behind it is a **USG gateway anywhere in the controller's synced
device inventory** — USG support ends at Network 10.6, so a site with one has
no Network 11 target at all.

`src/fleet/fleet_tools.py`:

```python
usg_gated = frozenset(
    d.controller for d in await snapshots.fleet_devices(names, model=USG_MODEL_SUBSTRING)
)
entries = [_status_view(s, now, usg_gated) for s in await snapshots.fleet_status(names)]
```

Two properties of this are worth separating, because they are what the
question turns on:

1. **The analysis is controller-agnostic and site-agnostic.** It reads the
   device snapshot and reduces it to a set of controller names. It never
   asks which site a device was in, and never asks what API type the
   controller has. If the snapshot held a cloud controller's devices, this
   code would flag it with no change.
2. **The collection is local-only.** `src/worker/jobs.py`:

   ```python
   inventories: dict[str, list[DeviceRecord]] = {}
   if settings.api_type == APIType.LOCAL:
       for site in sites:
           raw = await _paged(
               client, settings.get_integration_path(f"sites/{site.site_uuid}/devices")
           )
           inventories[site.site_uuid] = [...]
   ```

   A `CLOUD_V1` or `CLOUD_EA` controller gets **sites only**. The module
   docstring gives the reason: *"The cloud APIs list devices per host rather
   than per site, so cloud controllers get sites only."* The device inventory
   snapshot is keyed by site UUID, and the cloud API does not expose devices
   that way.

## Why neither case can be covered by another signal

### Cloud controllers

The only thing `platform_compat` asserts today is `network_11_capable: false`
with a reason. For a cloud controller we can assert neither `false` nor
`true`, because the USG break is precisely the one that cannot be assessed
without the inventory.

- **`false` is not available.** The USG break is the reason the field exists.
  A cloud controller's site *can* contain a USG — the worker simply never
  lists it. Asserting `false` would be asserting the absence of a fact we
  have not looked for.
- **`true` is not available either**, for the same reason: the field is a
  single boolean over two independent breaks (USG removal and the classic
  Network Application Server removal), and one of them is unknown.

There is a second, structural point. The **classic-server** break — a
standalone, self-hosted Network Application Server — *is* structurally
impossible for a `cloud-ea` / `cloud-v1` registry entry: that API type means
the server reaches the console through Ubiquiti's cloud API, and a
standalone Network Application Server is self-hosted software. A
self-hosted server that syncs its site to Site Manager is still a **`local`**
controller in the registry, because that is how the server would be reached.

But the classic-server fact alone does not determine the field, so it cannot
be used to extend it. Both breaks would have to be resolved for a cloud
controller, and only one of them is.

### Unsynced local controllers

This is **not a detection limit**, and it needs no new signal. The worker
syncs each controller periodically; until it has, there is no device
inventory, so no USG signal, so no `platform_compat`. On the next sync the
inventory lands and the flag appears if and only if a USG is present. The
existing code already behaves this way — `_status_view` adds `platform_compat`
only for controllers in `usg_gated`, and `usg_gated` only contains
controllers with inventory.

The one thing that would be needed is a way to say *"not yet known"* rather
than *"no USG-gating signal found"*, because today the two are the same
absence. That is a wording change to the documentation, not a new signal.

## What would actually extend it

**Collection, not analysis.** If the Site Manager API exposed a per-site
device listing, the existing USG check would extend to cloud controllers
unchanged — `fleet_devices` is already controller-scoped over a site-keyed
snapshot, and `usg_gated` already reduces to controller names. A worker
change that populates `inventories` for cloud controllers is the whole of it.

That is a separate piece of work with its own unknowns (whether the cloud
API's per-host device listing can be mapped onto site UUIDs at all), and it
is **not** attempted here.

## What this PR does not claim

- It does not claim a cloud controller is Network 11 capable.
- It does not claim a cloud controller's site is USG-free.
- It does not change `platform_compat`, its reason string, or the
  `fleet_health` contract.
- It does not change the worker.

The `fleet_health` docstring already says the right thing — *"Cloud
controllers are never flagged this way: the worker does not inventory them"*
— and this record explains why that is a collection limit rather than a
statement about the controllers, and what would change it.

## Where the limit is recorded

- `src/fleet/fleet_tools.py` — the `fleet_health` docstring (already
  accurate; cross-referenced here).
- `docs/NETWORK_11_COMPATIBILITY.md` — the compatibility matrix, which
  describes the two breaks and their visibility.
- `skills/unifi-fleet-operations/SKILL.md` — the operator-facing guidance,
  which warns that an absent `platform_compat` means "no USG-gating signal
  found", never an affirmative "compatible".

## Sources

1. `src/worker/jobs.py` — `sync_controller`, the local-only device inventory
   collection, and its module docstring on the cloud per-host listing.
2. `src/fleet/fleet_tools.py` — `fleet_health`, the `usg_gated` computation
   and `_status_view`.
3. `src/fleet/db/snapshots.py` — `fleet_devices`, the site-keyed device
   snapshot.
4. `docs/NETWORK_11_COMPATIBILITY.md` — the two breaks and their visibility.
