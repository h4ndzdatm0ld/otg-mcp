"""
Complete test coverage for schema registry module.

This module provides tests targeting all code paths in the schema_registry.py module,
with special attention to error cases and edge conditions.
"""

import os
import shutil
import tempfile

import pytest
import yaml

from otg_mcp.schema_registry import SchemaRegistry


class TestSchemaRegistryComplete:
    """Test cases for 100% coverage of SchemaRegistry."""

    @pytest.fixture
    def mock_schemas_dir(self):
        """Create a temporary directory with mock schema files."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        # Create schema version directories
        v1_dir = os.path.join(temp_dir, "1_30_0")
        v2_dir = os.path.join(temp_dir, "1_31_0")
        os.makedirs(v1_dir)
        os.makedirs(v2_dir)
        
        # Create an empty directory (should be ignored)
        os.makedirs(os.path.join(temp_dir, "empty_dir"))

        # Create a directory with no openapi.yaml file (should be ignored)
        no_yaml_dir = os.path.join(temp_dir, "no_yaml")
        os.makedirs(no_yaml_dir)
        with open(os.path.join(no_yaml_dir, "some_other_file.txt"), "w") as f:
            f.write("Not a YAML file")

        # Create mock schema files
        v1_schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test Schema 1.30.0", "version": "1.30.0"},
            "components": {
                "schemas": {
                    "Flow": {"type": "object"},
                    "Device": 12345,  # Not a dict to test error handling
                }
            },
        }

        v2_schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test Schema 1.31.0", "version": "1.31.0"},
            "components": {
                # No schemas key to test KeyError handling
            },
        }

        # Write schemas to files
        with open(os.path.join(v1_dir, "openapi.yaml"), "w") as f:
            yaml.dump(v1_schema, f)

        with open(os.path.join(v2_dir, "openapi.yaml"), "w") as f:
            yaml.dump(v2_schema, f)

        yield temp_dir

        # Cleanup the temporary directory
        shutil.rmtree(temp_dir)

    def test_normalize_version(self):
        """Test version string normalization."""
        registry = SchemaRegistry()
        assert registry._normalize_version("1.30.0") == "1_30_0"
        assert registry._normalize_version("1_30_0") == "1_30_0"

    def test_get_available_schemas(self, mock_schemas_dir):
        """Test getting available schemas."""
        registry = SchemaRegistry()
        registry._builtin_schemas_dir = mock_schemas_dir
        
        # Reset cached value to ensure it's computed fresh
        registry._available_schemas = None
        
        schemas = registry.get_available_schemas()
        assert "1_30_0" in schemas
        assert "1_31_0" in schemas
        assert "empty_dir" not in schemas
        assert "no_yaml" not in schemas
        
        # Call again to use cached value
        cached_schemas = registry.get_available_schemas()
        assert cached_schemas == schemas

    def test_non_existent_schemas_dir(self):
        """Test behavior when schemas directory doesn't exist."""
        registry = SchemaRegistry()
        temp_dir = tempfile.mkdtemp()
        try:
            # Point to a non-existent directory
            non_existent_dir = os.path.join(temp_dir, "non_existent")
            registry._builtin_schemas_dir = non_existent_dir
            registry._available_schemas = None
            
            # Should handle non-existent directory gracefully
            schemas = registry.get_available_schemas()
            # We expect empty list from built-in, but might have default schemas still
            assert isinstance(schemas, list)
        finally:
            shutil.rmtree(temp_dir)

    def test_schema_exists(self, mock_schemas_dir):
        """Test checking if schemas exist."""
        registry = SchemaRegistry()
        registry._builtin_schemas_dir = mock_schemas_dir
        registry._available_schemas = None  # Force refresh
        
        assert registry.schema_exists("1.30.0") is True
        assert registry.schema_exists("1_30_0") is True
        assert registry.schema_exists("1.31.0") is True
        assert registry.schema_exists("2.0.0") is False

    def test_list_schemas(self, mock_schemas_dir):
        """Test listing schema keys."""
        registry = SchemaRegistry()
        registry._builtin_schemas_dir = mock_schemas_dir
        registry._available_schemas = None  # Force refresh
        
        keys = registry.list_schemas("1.30.0")
        assert "openapi" in keys
        assert "info" in keys
        assert "components" in keys

    def test_get_schema_components(self, mock_schemas_dir):
        """Test getting schema components."""
        registry = SchemaRegistry()
        registry._builtin_schemas_dir = mock_schemas_dir
        registry._available_schemas = None  # Force refresh
        
        # Test with a valid path that returns a dict
        components = registry.get_schema_components("1.30.0", "components.schemas")
        assert "Flow" in components
        assert "Device" in components
        
        # Test with a path that returns a non-dict
        components = registry.get_schema_components("1.30.0", "components.schemas.Device")
        assert components == []

    def test_get_schema_basic(self, mock_schemas_dir):
        """Test getting a basic schema."""
        registry = SchemaRegistry()
        registry._builtin_schemas_dir = mock_schemas_dir
        registry._available_schemas = None  # Force refresh
        
        # Get full schema
        schema = registry.get_schema("1.30.0")
        assert schema["info"]["title"] == "Test Schema 1.30.0"
        
        # Get component
        flow = registry.get_schema("1.30.0", "components.schemas.Flow")
        assert flow["type"] == "object"

    def test_get_schema_invalid_version(self, mock_schemas_dir):
        """Test getting a schema with an invalid version."""
        registry = SchemaRegistry()
        registry._builtin_schemas_dir = mock_schemas_dir
        registry._available_schemas = None  # Force refresh
        
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("non_existent")
        assert "not found" in str(excinfo.value)

    def test_get_schema_loading_exception(self):
        """Test exception during schema loading."""
        registry = SchemaRegistry()
        
        # Create a temporary directory with an invalid YAML file
        temp_dir = tempfile.mkdtemp()
        try:
            v1_dir = os.path.join(temp_dir, "1_30_0")
            os.makedirs(v1_dir)
            
            with open(os.path.join(v1_dir, "openapi.yaml"), "w") as f:
                f.write("invalid YAML content:\n\tindentation error")
            
            registry._builtin_schemas_dir = temp_dir
            registry._available_schemas = None  # Force refresh
            
            with pytest.raises(ValueError) as excinfo:
                registry.get_schema("1.30.0")
            assert "Error loading schema" in str(excinfo.value)
        finally:
            shutil.rmtree(temp_dir)

    def test_get_schema_component_special_handling(self, mock_schemas_dir):
        """Test special handling for components.schemas.X paths."""
        registry = SchemaRegistry()
        registry._builtin_schemas_dir = mock_schemas_dir
        registry._available_schemas = None  # Force refresh
        
        # Test with a valid schema component
        flow = registry.get_schema("1.30.0", "components.schemas.Flow")
        assert flow["type"] == "object"
        
        # Test with an invalid schema component
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1.30.0", "components.schemas.NonExistent")
        assert "not found in components.schemas" in str(excinfo.value)
        
        # Test with a missing components.schemas section
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1.31.0", "components.schemas.Flow")
        assert "Error accessing components.schemas" in str(excinfo.value)

    def test_get_schema_component_navigation(self, mock_schemas_dir):
        """Test component path navigation."""
        registry = SchemaRegistry()
        registry._builtin_schemas_dir = mock_schemas_dir
        registry._available_schemas = None  # Force refresh
        
        # Test navigation to a component
        component = registry.get_schema("1.30.0", "components")
        assert "schemas" in component
        
        # Test navigation to a non-existent component
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1.30.0", "non_existent")
        assert "not found in path" in str(excinfo.value)
        
        # Test navigation through a non-dict component
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1.30.0", "components.schemas.Device.property")
        # The path is actually failing in the special handling for components.schemas.X
        # rather than in the TypeError handling section
        assert "Schema Device.property not found in components.schemas" in str(excinfo.value)

    def test_multiple_registry_instances(self):
        """Test that multiple registry instances can be created with different configs."""
        registry1 = SchemaRegistry(custom_schemas_dir="/path/to/custom1")
        registry2 = SchemaRegistry(custom_schemas_dir="/path/to/custom2")
        
        # Instances should be different
        assert registry1 is not registry2
        assert registry1._custom_schemas_dir != registry2._custom_schemas_dir


if __name__ == "__main__":
    pytest.main(["-v", __file__])
