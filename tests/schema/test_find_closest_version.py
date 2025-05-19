"""
Tests for the find_closest_schema_version functionality.

This file contains tests specifically for the version matching algorithm
that finds the closest matching schema version when an exact match isn't available.
"""

import pytest
from unittest.mock import patch

from otg_mcp.schema_registry import SchemaRegistry


class TestFindClosestVersion:
    """Tests for the find_closest_schema_version method."""

    def setup_method(self):
        """Set up test environment."""
        self.registry = SchemaRegistry()

    def test_exact_match(self):
        """Test that an exact version match is returned when available."""
        with patch.object(self.registry, "get_available_schemas", 
                         return_value=["1_28_0", "1_30_0"]):
            with patch.object(self.registry, "schema_exists", return_value=True):
                result = self.registry.find_closest_schema_version("1_28_0")
                assert result == "1_28_0"

    def test_same_major_minor_lower_patch(self):
        """Test finding a schema with same major.minor but lower patch version."""
        with patch.object(self.registry, "get_available_schemas", 
                         return_value=["1_28_0", "1_30_0"]):
            with patch.object(self.registry, "schema_exists", return_value=False):
                result = self.registry.find_closest_schema_version("1_28_2")
                assert result == "1_28_0"

    def test_same_major_different_minor(self):
        """Test finding a schema with same major but different minor version."""
        with patch.object(self.registry, "get_available_schemas", 
                         return_value=["1_28_0", "1_30_0"]):
            with patch.object(self.registry, "schema_exists", return_value=False):
                result = self.registry.find_closest_schema_version("1_31_0")
                assert result == "1_30_0"

    def test_different_major_version(self):
        """Test finding a schema when major version doesn't match."""
        with patch.object(self.registry, "get_available_schemas", 
                         return_value=["1_28_0", "1_30_0"]):
            with patch.object(self.registry, "schema_exists", return_value=False):
                result = self.registry.find_closest_schema_version("2_0_0")
                assert result == "1_30_0"  # Should use latest version

    def test_invalid_version_format(self):
        """Test handling of invalid version format."""
        with patch.object(self.registry, "get_available_schemas", 
                         return_value=["1_28_0", "1_30_0"]):
            with patch.object(self.registry, "schema_exists", return_value=False):
                # With invalid format, should fall back to latest version
                result = self.registry.find_closest_schema_version("invalid_version")
                assert result == "1_30_0"

    def test_no_schemas_available(self):
        """Test error when no schemas are available."""
        with patch.object(self.registry, "get_available_schemas", return_value=[]):
            with pytest.raises(ValueError, match="No schema versions available"):
                self.registry.find_closest_schema_version("1_28_0")

    def test_empty_requested_version(self):
        """Test handling of empty requested version."""
        with patch.object(self.registry, "get_available_schemas", 
                         return_value=["1_28_0", "1_30_0"]):
            with patch.object(self.registry, "get_latest_schema_version", 
                            return_value="1_30_0"):
                result = self.registry.find_closest_schema_version("")
                assert result == "1_30_0"  # Should use latest version

    def test_partial_version(self):
        """Test handling of partial version (only major or major.minor)."""
        with patch.object(self.registry, "get_available_schemas", 
                         return_value=["1_28_0", "1_30_0"]):
            # Test with just major version
            result = self.registry.find_closest_schema_version("1")
            assert result == "1_30_0"  # Should use latest matching major

            # Test with major.minor
            result = self.registry.find_closest_schema_version("1.28")
            assert result == "1_28_0"  # Should match major.minor

    def test_multiple_match_options(self):
        """Test with multiple possible matches."""
        with patch.object(self.registry, "get_available_schemas", 
                         return_value=["1_28_0", "1_28_1", "1_30_0"]):
            # Should match 1_28_1 as it's the highest with same major.minor
            result = self.registry.find_closest_schema_version("1_28_2")
            assert result == "1_28_1"

            # Should match 1_28_1 as it's the highest with same major.minor
            result = self.registry.find_closest_schema_version("1.28.5")
            assert result == "1_28_1"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
