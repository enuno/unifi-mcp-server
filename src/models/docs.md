# Noridoc: models

Path: @/src/models

## Overview

- Contains all Pydantic data models used throughout the UniFi MCP Server, covering UniFi API resources like firewall policies, traffic flows, RADIUS profiles, network topology, and more.
- Each module defines both **response models** (deserialize API responses) and **request models** (serialize parameters for API calls), with Pydantic's `extra="allow"` to handle undocumented API fields.
- Models are the contract between the API client (`@/src/api/client.py`) and the tool layer (`@/src/tools/`), ensuring type safety and enabling schema validation.

## How it fits into the larger codebase

- All tools in `@/src/tools/` import and instantiate these models to validate and serialize API responses and request payloads before returning results or sending requests.
- Models inherit from Pydantic's `BaseModel` and use `ConfigDict(populate_by_name=True, extra="allow")` to accept both snake_case and camelCase field names from the UniFi API, which often returns mixed conventions.
- Enum classes (e.g., `MatchingTarget`, `PolicyAction`, `ConnectionStateType`) define valid string literals for categorical fields, and the tool layer validates user inputs against these enums to fail fast before making API calls.
- Models are intentionally **not** used in `@/src/api/client.py`; the client layer works with raw dicts to preserve unknown fields and avoid deserialization overhead. Models only enter at the tool layer.

## Core Implementation

- **Response models** deserialize API response dicts with Pydantic's `model_validate()` or direct instantiation (e.g., `FirewallPolicy(**api_response)`). Validation errors raise `pydantic.ValidationError`, which tools catch and convert to user-friendly exceptions.
- **Request models** like `FirewallPolicyCreate` and `FirewallPolicyUpdate` enforce which fields are required vs optional. Update models make all fields optional, enabling sparse payloads that only send changed fields to the API.
- **Enum fields** drive the matching-target and policy-action discriminators in firewall models. The `MatchingTarget` enum includes `ANY`, `IP`, `NETWORK`, `REGION`, `CLIENT`, and `APP` (added in Bug #72), and is used in both source and destination zone matching rules.
- **Nested models** like `MatchTarget` and `Schedule` are reused across multiple parent models (e.g., `MatchTarget` appears in both `FirewallPolicy.source` and `FirewallPolicy.destination`), reducing duplication.
- **Alias mapping** via `Field(..., alias="_id")` allows models to accept the API's `_id` field and expose it as the more Pythonic `id` field in model instances.

## Things to Know

- The `MatchingTarget` enum now includes the `APP` value (Bug #72 fix), which enables firewall policies to filter traffic by application type. This allows rules like "block streaming applications" that previously failed validation because the enum didn't list `APP`.
- The `MatchTarget` model accepts `matching_target` as an enum, but the firewall tools' `_build_match_target()` helper also accepts it as a string and auto-detects the matching mode from which optional fields (ips, network_ids, client_macs) are provided. This dual support (enum validation + string flexibility) exists to bridge the strict model layer with the flexible tool layer.
- Models use `extra="allow"` to silently accept undocumented API fields without raising validation errors. This prevents hard breaks when the UniFi API adds new response fields or when different firmware versions return extra data.
- `FirewallZoneV2Mapping` exposes three zone identifiers—internal MongoDB ObjectId, external UUID, and zone name—because the v2 firewall-policies endpoint uses ObjectIds internally while the integration API and most other tools expect UUIDs. Tools use `_resolve_zone_id()` to map user input (which can be any of the three) to the internal id required by the API.

Created and maintained by Nori.
