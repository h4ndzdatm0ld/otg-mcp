"""
Tests for schema version matching functionality.

These tests verify that the schema registry can find the closest matching schema
version when an exact match isn't available.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from otg_mcp.schema_registry import SchemaRegistry


def test_schema_exists():
    """Test the schema_exists method."""
    registry = SchemaRegistry()
    assert registry.schema_exists("1_30_0")
    assert registry.schema_exists("1.30.0")
    assert not registry.schema_exists("1_99_0")


def test_normalize_version():
    """Test version normalization."""
    registry = SchemaRegistry()
    assert registry._normalize_version("1.30.0") == "1_30_0"
    assert registry._normalize_version("1_30_0") == "1_30_0"


class TestVersionMatching:
    """Tests for schema version matching functionality."""
    
    def setup_method(self):
        """Set up the test environment with mock schema registry."""
        self.registry = SchemaRegistry()
        # Mock available schemas to simulate different versions
        self.available_schemas = ["1_28_0", "1_29_0", "1_30_0"]
    
    def test_find_closest_exact_match(self):
        """Test finding exact schema version match."""
        with patch.object(self.registry, "get_available_schemas", return_value=self.available_schemas):
            with patch.object(self.registry, "schema_exists", return_value=True):
                result = self.registry.find_closest_schema_version("1_30_0")
                assert result == "1_30_0"
    
    def test_find_closest_same_major_minor_lower_patch(self):
        """Test finding schema with same major.minor and lower patch."""
        with patch.object(self.registry, "get_available_schemas", return_value=self.available_schemas):
            # Test finding 1.28.0 when requesting 1.28.2
            result = self.registry.find_closest_schema_version("1.28.2")
            assert result == "1_28_0"
    
    def test_find_closest_same_major(self):
        """Test finding schema with same major version when no matching minor."""
        with patch.object(self.registry, "get_available_schemas", return_value=self.available_schemas):
            # Test finding 1.30.0 (latest with same major) when requesting 1.31.2
            result = self.registry.find_closest_schema_version("1.31.2")
            assert result == "1_30_0"
    
    def test_fallback_to_latest(self):
        """Test fallback to latest version when no matching major version."""
        with patch.object(self.registry, "get_available_schemas", return_value=self.available_schemas):
            # Test finding 1.30.0 (latest overall) when requesting 2.0.0
            result = self.registry.find_closest_schema_version("2.0.0")
            assert result == "1_30_0"
    
    def test_empty_schema_list(self):
        """Test error when no schemas are available."""
        with patch.object(self.registry, "get_available_schemas", return_value=[]):
            with pytest.raises(ValueError, match="No schema versions available"):
                self.registry.find_closest_schema_version("1.28.0")


class TestCustomSchemaPaths:
    """Tests for custom schema path functionality."""
    
    def setup_method(self):
        """Set up the test environment with temporary directories."""
        # Create temporary directories for custom and built-in schemas
        self.temp_dir = tempfile.mkdtemp()
        self.custom_dir = os.path.join(self.temp_dir, "custom_schemas")
        os.makedirs(self.custom_dir)
        
        # Create schema directories
        self.custom_schema_dir = os.path.join(self.custom_dir, "1_31_0")
        os.makedirs(self.custom_schema_dir)
        
        # Create schema files
        with open(os.path.join(self.custom_schema_dir, "openapi.yaml"), "w") as f:
            f.write("# Custom schema 1.31.0")
    
    def teardown_method(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir)
    
    def test_custom_schemas_directory(self):
        """Test that custom schemas directory is used."""
        registry = SchemaRegistry(self.custom_dir)
        
        # Create a non-existent directory for built-in schemas to ensure we only get custom schemas
        non_existent_dir = os.path.join(self.temp_dir, "non_existent")
        registry._builtin_schemas_dir = non_existent_dir
        registry._available_schemas = None  # Force refresh

        available = registry.get_available_schemas()
        assert "1_31_0" in available
    
    def test_prioritize_custom_schemas(self):
        """Test that custom schemas take priority over built-in schemas."""
        # Create a temporary built-in directory with the same version
        built_in_dir = os.path.join(self.temp_dir, "built_in")
        os.makedirs(built_in_dir)
        common_version = "1_30_0"

        # Create same version in custom dir with valid YAML content
        os.makedirs(os.path.join(self.custom_dir, common_version))
        with open(os.path.join(self.custom_dir, common_version, "openapi.yaml"), "w") as f:
            f.write("""
# Custom schema 1.30.0
components:
  schemas:
    Test:
      type: object
      properties:
        name:
          type: string
""")
        
        # Create same version in built-in dir (with different content)
        built_in_version_dir = os.path.join(built_in_dir, common_version)
        os.makedirs(built_in_version_dir)
        with open(os.path.join(built_in_version_dir, "openapi.yaml"), "w") as f:
            f.write("""
# Built-in schema 1.30.0
components:
  schemas:
    Test:
      type: object
      properties:
        id:
          type: integer
""")

        # Create registry with our test directories
        registry = SchemaRegistry(self.custom_dir)
        registry._builtin_schemas_dir = built_in_dir
        registry._available_schemas = None  # Force refresh
        
        # Get available schemas (should include both custom and built-in)
        available = registry.get_available_schemas()
        assert common_version in available
        
        # Verify the schema exists at the expected path
        schema_path = os.path.join(self.custom_dir, common_version, "openapi.yaml")
        assert os.path.exists(schema_path)
        
        # Check that custom takes priority by looking at the first schema in the list
        # The implementation guarantees custom schemas are added first
        assert available.count(common_version) == 1  # Should only appear once
        
        # Ensure custom schema is loaded
        schema = registry.get_schema(common_version)

        # Now check that the schema was loaded and has the expected content
        assert isinstance(schema, dict)
        assert "components" in schema
        assert "schemas" in schema["components"]
        assert "Test" in schema["components"]["schemas"]

        # The schema from custom dir should have a 'name' property, not 'id'
        # This verifies we loaded from custom dir, not built-in
        assert "name" in schema["components"]["schemas"]["Test"]["properties"]
        assert "id" not in schema["components"]["schemas"]["Test"]["properties"]


def test_get_latest_schema_version():
    """Test getting the latest schema version."""
    registry = SchemaRegistry()
    
    with patch.object(registry, "get_available_schemas", 
                     return_value=["1_20_0", "1_28_0", "1_30_0", "1_5_0"]):
        latest = registry.get_latest_schema_version()
        assert latest == "1_30_0"


def test_get_latest_schema_version_empty():
    """Test error when no schemas are available for latest version."""
    registry = SchemaRegistry()
    
    with patch.object(registry, "get_available_schemas", return_value=[]):
        with pytest.raises(ValueError, match="No schema versions available"):
            registry.get_latest_schema_version()
