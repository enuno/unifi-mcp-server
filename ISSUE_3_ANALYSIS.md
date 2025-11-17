# GitHub Issue #3 Analysis: Cloud API Site Schema Mismatch

## Issue Summary

When calling `list_all_sites` with Cloud API credentials, the MCP server returns a Pydantic validation error because the `Site` model expects fields (`_id`, `name`) that don't match the Cloud API response schema.

## Root Cause

The codebase has a **schema mismatch** between Local Controller API and Cloud API responses:

### Local Controller API Response
```json
{
  "data": [
    {
      "_id": "default",
      "name": "Default Site",
      "desc": "Default site description",
      "role": "admin"
    }
  ]
}
```

### Cloud API Response (Actual)
```json
{
  "data": [
    {
      "siteId": "63b384c52165f...",
      "isOwner": true,
      // name field may be missing or named differently
    }
  ]
}
```

## Technical Analysis

### Affected Code Locations

1. **src/models/site.py** (lines 20-22)
   ```python
   id: str = Field(..., description="Site ID", alias="_id")  # REQUIRED
   name: str = Field(..., description="Site name")            # REQUIRED
   desc: str | None = Field(None, description="Site description")
   ```
   - Model expects `_id` (required)
   - Model expects `name` (required)
   - Cloud API returns `siteId` instead

2. **src/tools/sites.py** (line 68)
   ```python
   sites = [Site(**s).model_dump() for s in paginated]
   ```
   - Direct parsing without schema transformation
   - Assumes Local Controller API schema
   - Fails with Cloud API responses

3. **src/main.py** (line 237)
   ```python
   @mcp.tool()
   async def list_all_sites() -> list[dict]:
       """List all accessible sites."""
       return await sites_tools.list_sites(settings)
   ```
   - MCP tool that triggers the error
   - Uses same code path for both API types

### API Type Detection

The codebase supports both API types via `src/config/config.py`:
```python
api_type: APIType = Field(
    default=APIType.CLOUD,
    description="API connection type: 'cloud' or 'local'",
)
```

**However**, there's **NO conditional logic** to handle different schemas based on `api_type`.

## Solution Options

### Option 1: Flexible Site Model (Recommended)

Make the `Site` model handle both schemas using Pydantic v2 features:

```python
# src/models/site.py
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Site(BaseModel):
    """UniFi site information (supports both Cloud and Local API)."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",  # Allow extra fields from Cloud API
    )

    # Support both _id (Local) and siteId (Cloud)
    id: str = Field(
        ...,
        description="Site ID",
        alias="_id",
        validation_alias=["_id", "siteId"]  # Accept either field name
    )

    # Make name optional since Cloud API may not return it
    name: str | None = Field(
        None,
        description="Site name",
        validation_alias=["name", "siteName"]  # Try multiple field names
    )

    desc: str | None = Field(None, description="Site description")

    # Cloud API specific fields
    is_owner: bool | None = Field(None, alias="isOwner", description="Whether user owns the site")

    @field_validator('name', mode='before')
    @classmethod
    def ensure_name(cls, v: str | None, info) -> str:
        """Ensure name is populated from id if not provided."""
        if v is None:
            # Use siteId or _id as fallback name for Cloud API
            return info.data.get('id') or info.data.get('siteId') or info.data.get('_id') or 'Unknown Site'
        return v
```

**Pros:**
- ✅ Single model for both API types
- ✅ Backward compatible with existing Local API code
- ✅ Uses Pydantic v2 `validation_alias` feature
- ✅ Minimal code changes

**Cons:**
- ⚠️ Name field defaults to ID if not provided

### Option 2: Separate CloudSite Model

Create distinct models for each API type:

```python
# src/models/site.py
class Site(BaseModel):
    """UniFi site (Local Controller API)."""
    id: str = Field(..., alias="_id")
    name: str
    desc: str | None = None

class CloudSite(BaseModel):
    """UniFi site (Cloud API)."""
    site_id: str = Field(..., alias="siteId")
    is_owner: bool | None = Field(None, alias="isOwner")
    name: str | None = None  # May not be provided

    def to_site(self) -> Site:
        """Convert to standard Site model."""
        return Site(
            id=self.site_id,
            name=self.name or self.site_id,
            desc=None
        )
```

**Pros:**
- ✅ Explicit schema separation
- ✅ Type safety for each API
- ✅ Clear API differences

**Cons:**
- ❌ Requires changes throughout codebase
- ❌ Conditional logic based on `api_type` everywhere
- ❌ More maintenance burden

### Option 3: Response Transformation Layer

Add transformation in `list_sites`:

```python
# src/tools/sites.py
async def list_sites(settings: Settings, ...) -> list[dict[str, Any]]:
    """List all accessible sites."""
    ...
    response = await client.get("/ea/sites")
    sites_data = response.get("data", [])

    # Transform Cloud API schema to Local API schema
    if settings.api_type == APIType.CLOUD:
        sites_data = [
            {
                "_id": s.get("siteId", s.get("_id")),
                "name": s.get("name", s.get("siteName", s.get("siteId"))),
                "desc": s.get("desc", s.get("description")),
                "is_owner": s.get("isOwner"),
                **s  # Keep all other fields
            }
            for s in sites_data
        ]

    # Apply pagination
    paginated = sites_data[offset : offset + limit]
    sites = [Site(**s).model_dump() for s in paginated]
    ...
```

**Pros:**
- ✅ Centralized transformation logic
- ✅ Existing Site model unchanged
- ✅ Easy to debug/test

**Cons:**
- ❌ Must update every function that fetches sites
- ❌ Duplication of transformation logic

## Recommended Solution

**Use Option 1: Flexible Site Model** because:

1. ✅ **Minimal code changes** - Update only `src/models/site.py`
2. ✅ **Pydantic v2 native** - Uses modern `validation_alias` feature
3. ✅ **Future-proof** - Handles API schema evolution
4. ✅ **Backward compatible** - Works with existing Local API code
5. ✅ **Single source of truth** - One model, not duplicated logic

## Implementation Plan

### Step 1: Update Site Model
File: `src/models/site.py`

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Site(BaseModel):
    """UniFi site information (Cloud and Local API compatible)."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "example": {
                "_id": "default",
                "name": "Default Site",
                "desc": "Default site description",
            }
        },
    )

    id: str = Field(
        ...,
        description="Site ID",
        alias="_id",
        validation_alias=AliasChoices("_id", "siteId", "id")
    )

    name: str = Field(
        ...,
        description="Site name",
        validation_alias=AliasChoices("name", "siteName")
    )

    desc: str | None = Field(
        None,
        description="Site description",
        validation_alias=AliasChoices("desc", "description")
    )

    # Cloud API fields
    is_owner: bool | None = Field(None, alias="isOwner")

    # Existing optional fields
    attr_hidden_id: str | None = Field(None, description="Hidden ID attribute")
    attr_no_delete: bool | None = Field(None, description="Whether site can be deleted")
    role: str | None = Field(None, description="Site role")

    @field_validator('name', mode='before')
    @classmethod
    def fallback_name_from_id(cls, v: str | None, info) -> str:
        """Use ID as name if name is not provided (Cloud API)."""
        if v is None or v == '':
            # Get ID from any available field
            site_id = info.data.get('siteId') or info.data.get('_id') or info.data.get('id')
            if site_id:
                return f"Site {site_id}"
            return "Unknown Site"
        return v
```

### Step 2: Add Unit Tests
File: `tests/unit/test_models_site.py` (new file)

```python
"""Tests for Site model with Cloud and Local API compatibility."""
import pytest
from src.models.site import Site

def test_site_local_api_schema():
    """Test Site model with Local API response."""
    data = {
        "_id": "default",
        "name": "Default Site",
        "desc": "Main site"
    }
    site = Site(**data)
    assert site.id == "default"
    assert site.name == "Default Site"
    assert site.desc == "Main site"

def test_site_cloud_api_schema():
    """Test Site model with Cloud API response."""
    data = {
        "siteId": "63b384c52165f",
        "isOwner": True
    }
    site = Site(**data)
    assert site.id == "63b384c52165f"
    assert site.name.startswith("Site")  # Fallback name
    assert site.is_owner is True

def test_site_cloud_api_with_name():
    """Test Cloud API with optional name field."""
    data = {
        "siteId": "63b384c52165f",
        "siteName": "My Cloud Site",
        "isOwner": True
    }
    site = Site(**data)
    assert site.id == "63b384c52165f"
    assert site.name == "My Cloud Site"
```

### Step 3: Update Documentation
File: `docs/UNIFI_API.md`

Add section documenting Cloud API schema differences:

```markdown
## Cloud API vs Local API Schema Differences

### Sites Endpoint

#### Local Controller API
- Endpoint: `GET /ea/sites`
- Returns: `_id`, `name`, `desc`

#### Cloud API
- Endpoint: `GET /ea/sites` or `/v1/sites`
- Returns: `siteId`, `isOwner`, optional `name`/`siteName`

The `Site` model automatically handles both schemas using field aliases.
```

### Step 4: Verify with Integration Test

Add test case with actual Cloud API credentials to verify the fix.

## Testing Strategy

1. **Unit tests** - Test both schemas with mocked data
2. **Integration tests** - Test with real Cloud API
3. **Regression tests** - Ensure Local API still works

## Migration Path

1. Update `Site` model (no breaking changes)
2. Run existing tests to verify Local API compatibility
3. Add Cloud API tests
4. Deploy and verify with Cloud API user

## Additional Considerations

### Other Models to Review

Check if these models have similar issues:
- `Device` - May have schema differences
- `Client` - May have schema differences
- `Network` - May have schema differences

### API Endpoint Differences

Document which endpoints differ between Cloud and Local:
- `/ea/sites` - Schema differences identified
- `/ea/sites/{siteId}/devices` - May need review
- Other endpoints - Audit needed

## References

- Pydantic v2 Alias Documentation: https://docs.pydantic.dev/latest/concepts/fields/#field-aliases
- GitHub Issue #3: [Link when available]
- UniFi Cloud API: https://developer.ui.com/

## Conclusion

This issue is a **schema compatibility problem** between Cloud and Local APIs. The recommended solution uses Pydantic v2's `validation_alias` feature to accept both field names, making the Site model compatible with both API types without code duplication.

**Estimated effort**: 2-3 hours
- 30 min: Update Site model
- 1 hour: Write comprehensive tests
- 30 min: Integration testing with Cloud API
- 30 min: Documentation

**Risk**: Low - Backward compatible change with extensive testing
