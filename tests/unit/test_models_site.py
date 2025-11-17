"""Unit tests for Site model with Cloud and Local API compatibility."""

import pytest
from pydantic import ValidationError

from src.models.site import Site


class TestSiteLocalAPI:
    """Tests for Site model with Local Controller API schema."""

    def test_local_api_minimal_schema(self):
        """Test Site model with minimal Local API response."""
        data = {"_id": "default", "name": "Default Site"}
        site = Site(**data)

        assert site.id == "default"
        assert site.name == "Default Site"
        assert site.desc is None
        assert site.is_owner is None

    def test_local_api_full_schema(self):
        """Test Site model with full Local API response."""
        data = {
            "_id": "default",
            "name": "Default Site",
            "desc": "Main site description",
            "role": "admin",
            "attr_hidden_id": "hidden123",
            "attr_no_delete": True,
        }
        site = Site(**data)

        assert site.id == "default"
        assert site.name == "Default Site"
        assert site.desc == "Main site description"
        assert site.role == "admin"
        assert site.attr_hidden_id == "hidden123"
        assert site.attr_no_delete is True

    def test_local_api_serialization(self):
        """Test Site model serialization with Local API schema."""
        data = {"_id": "test-site", "name": "Test Site", "desc": "Test description"}
        site = Site(**data)
        dumped = site.model_dump()

        assert dumped["id"] == "test-site"
        assert dumped["name"] == "Test Site"
        assert dumped["desc"] == "Test description"

    def test_local_api_by_alias(self):
        """Test serialization using field aliases."""
        data = {"_id": "test-site", "name": "Test Site"}
        site = Site(**data)
        dumped = site.model_dump(by_alias=True)

        # When by_alias=True, id should be serialized as _id
        assert dumped["_id"] == "test-site"
        assert dumped["name"] == "Test Site"


class TestSiteCloudAPI:
    """Tests for Site model with Cloud API schema."""

    def test_cloud_api_minimal_schema(self):
        """Test Site model with minimal Cloud API response (no name)."""
        data = {"siteId": "63b384c52165f", "isOwner": True}
        site = Site(**data)

        assert site.id == "63b384c52165f"
        assert site.name == "Site 63b384c52165f"  # Fallback name
        assert site.is_owner is True
        assert site.desc is None

    def test_cloud_api_with_site_name(self):
        """Test Cloud API with siteName field."""
        data = {"siteId": "63b384c52165f", "siteName": "My Cloud Site", "isOwner": True}
        site = Site(**data)

        assert site.id == "63b384c52165f"
        assert site.name == "My Cloud Site"
        assert site.is_owner is True

    def test_cloud_api_with_name(self):
        """Test Cloud API with standard name field."""
        data = {"siteId": "63b384c52165f", "name": "Production Site", "isOwner": False}
        site = Site(**data)

        assert site.id == "63b384c52165f"
        assert site.name == "Production Site"
        assert site.is_owner is False

    def test_cloud_api_with_description(self):
        """Test Cloud API with description field."""
        data = {
            "siteId": "63b384c52165f",
            "name": "Cloud Site",
            "description": "Site description",
            "isOwner": True,
        }
        site = Site(**data)

        assert site.id == "63b384c52165f"
        assert site.name == "Cloud Site"
        assert site.desc == "Site description"

    def test_cloud_api_extra_fields(self):
        """Test that Cloud API extra fields are allowed."""
        data = {
            "siteId": "63b384c52165f",
            "name": "Site Name",
            "isOwner": True,
            "extraField1": "value1",
            "extraField2": 123,
            "extraField3": {"nested": "data"},
        }
        # Should not raise validation error even with extra fields
        site = Site(**data)

        assert site.id == "63b384c52165f"
        assert site.name == "Site Name"
        assert site.is_owner is True


class TestSiteMixedAPI:
    """Tests for Site model with mixed/edge cases."""

    def test_id_field_accepts_id_directly(self):
        """Test that id field also works without alias."""
        data = {"id": "direct-id", "name": "Direct ID Site"}
        site = Site(**data)

        assert site.id == "direct-id"
        assert site.name == "Direct ID Site"

    def test_empty_name_uses_fallback(self):
        """Test that empty name string triggers fallback."""
        data = {"_id": "site123", "name": ""}
        site = Site(**data)

        assert site.id == "site123"
        assert site.name == "Site site123"

    def test_priority_of_id_aliases(self):
        """Test validation_alias priority when multiple ID fields present."""
        # _id should take precedence
        data = {"_id": "local-id", "siteId": "cloud-id", "name": "Test"}
        site = Site(**data)

        assert site.id == "local-id"

    def test_priority_of_name_aliases(self):
        """Test validation_alias priority when multiple name fields present."""
        # name should take precedence over siteName
        data = {"_id": "test", "name": "Primary Name", "siteName": "Secondary Name"}
        site = Site(**data)

        assert site.name == "Primary Name"

    def test_unknown_site_fallback(self):
        """Test fallback when no ID fields are present."""
        # This should still raise validation error because id is required
        with pytest.raises(ValidationError, match="Field required"):
            Site(name="Just a name")


class TestSiteBackwardCompatibility:
    """Tests to ensure backward compatibility with existing code."""

    def test_existing_code_pattern(self):
        """Test that existing code patterns still work."""
        # Pattern used in src/tools/sites.py line 68
        site_data = {"_id": "default", "name": "Default", "desc": "Description"}
        site = Site(**site_data)
        result = site.model_dump()

        assert result["id"] == "default"
        assert result["name"] == "Default"
        assert result["desc"] == "Description"

    def test_conftest_fixture_pattern(self):
        """Test that conftest.py sample_site_data pattern works."""
        sample_site = {
            "_id": "default",
            "name": "Default Site",
            "desc": "Default site description",
        }
        site = Site(**sample_site)

        assert site.id == "default"
        assert site.name == "Default Site"
        assert site.desc == "Default site description"

    def test_get_site_details_pattern(self):
        """Test pattern from src/tools/sites.py get_site_details."""
        api_response = {"_id": "site123", "name": "My Site", "desc": "Description", "role": "admin"}
        site = Site(**api_response)
        result = site.model_dump()

        assert result["id"] == "site123"
        assert "name" in result
        assert "desc" in result
