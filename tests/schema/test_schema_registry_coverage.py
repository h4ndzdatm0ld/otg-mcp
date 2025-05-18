"""
Additional test coverage for schema registry to achieve 100% coverage.

This module provides tests specifically targeting uncovered code paths
in the schema_registry.py module.
"""

import os
import shutil
import tempfile

import pytest
import yaml

from otg_mcp.schema_registry import SchemaRegistry, get_schema_registry


class TestSchemaRegistryCoverage:
    """Test cases specifically targeting uncovered lines in SchemaRegistry."""

    @pytest.fixture
    def empty_schemas_dir(self):
        """Create an empty temporary directory for schemas testing."""
        # Create a temporary directory that will be empty
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup the temporary directory
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def invalid_schema_dir(self):
        """Create a temporary directory with invalid schema file."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        # Create schema version directory
        v1_dir = os.path.join(temp_dir, "1_30_0")
        os.makedirs(v1_dir)

        # Create invalid schema file that will cause an exception when loaded
        with open(os.path.join(v1_dir, "openapi.yaml"), "w") as f:
            f.write("invalid: yaml: content\n\tindentation: error")

        yield temp_dir

        # Cleanup the temporary directory
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def invalid_component_dir(self):
        """Create a temporary directory with schema having non-dict component."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        # Create schema version directory
        v1_dir = os.path.join(temp_dir, "1_30_0")
        os.makedirs(v1_dir)

        # Create schema with non-dict component
        schema = {
            "components": {
                "schemas": {
                    "ValidDict": {"type": "object"},
                    "InvalidComponent": ["this", "is", "a", "list", "not", "a", "dict"],
                }
            }
        }

        # Write schema to file
        with open(os.path.join(v1_dir, "openapi.yaml"), "w") as f:
            yaml.dump(schema, f)

        yield temp_dir

        # Cleanup the temporary directory
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def missing_component_dir(self):
        """Create a temporary directory with schema missing components.schemas."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        # Create schema version directory
        v1_dir = os.path.join(temp_dir, "1_30_0")
        os.makedirs(v1_dir)

        # Create schema without components.schemas
        schema = {
            "components": {
                # No schemas key here
                "other": {"something": {"type": "object"}}
            }
        }

        # Write schema to file
        with open(os.path.join(v1_dir, "openapi.yaml"), "w") as f:
            yaml.dump(schema, f)

        yield temp_dir

        # Cleanup the temporary directory
        shutil.rmtree(temp_dir)

    def test_non_existent_schemas_dir(self, empty_schemas_dir):
        """Test behavior when schemas directory doesn't exist."""
        # Create registry with a non-existent schemas directory
        registry = SchemaRegistry()
        non_existent_dir = os.path.join(empty_schemas_dir, "non_existent")
        registry._schemas_dir = non_existent_dir

        # Test that get_available_schemas returns empty list
        available_schemas = registry.get_available_schemas()
        assert available_schemas == []

    def test_schema_loading_exception(self, invalid_schema_dir):
        """Test error handling when schema loading fails."""
        registry = SchemaRegistry()
        registry._schemas_dir = invalid_schema_dir

        # Test that an exception is raised when trying to load an invalid schema
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1_30_0")
        
        assert "Error loading schema" in str(excinfo.value)

    def test_non_dict_component(self, invalid_component_dir):
        """Test handling non-dictionary components in get_schema_components."""
        registry = SchemaRegistry()
        registry._schemas_dir = invalid_component_dir

        # Load the schema first
        schema = registry.get_schema("1_30_0")

        # Verify our test schema has the expected structure
        assert "components" in schema
        assert "schemas" in schema["components"]
        assert "InvalidComponent" in schema["components"]["schemas"]
        assert isinstance(schema["components"]["schemas"]["InvalidComponent"], list)

        # Test getting components from a non-dictionary component
        components = registry.get_schema_components("1_30_0", "components.schemas.InvalidComponent")
        
        # Should return empty list for non-dict component
        assert components == []

    def test_missing_components_schemas(self, missing_component_dir):
        """Test error handling when components.schemas is missing."""
        registry = SchemaRegistry()
        registry._schemas_dir = missing_component_dir

        # Test accessing a schema in components.schemas when it doesn't exist
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1_30_0", "components.schemas.Flow")
        
        assert "Error accessing components.schemas" in str(excinfo.value)

    def test_invalid_component_navigation(self, invalid_component_dir):
        """Test error handling with invalid component navigation."""
        registry = SchemaRegistry()
        registry._schemas_dir = invalid_component_dir
        
        # Try to navigate through a non-navigable component
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1_30_0", "components.schemas.ValidDict.some.nested.path")
        
        # The special handling for components.schemas.X paths is what's actually being tested
        assert "Schema ValidDict.some.nested.path not found in components.schemas" in str(excinfo.value)

    def test_global_schema_registry_initialization(self):
        """Test global schema registry initialization."""
        # Reset the global registry to ensure test isolation
        import otg_mcp.schema_registry
        otg_mcp.schema_registry._schema_registry = None
        
        # First call should create a new instance
        registry1 = get_schema_registry()
        assert registry1 is not None
        
        # Second call should return the same instance
        registry2 = get_schema_registry()
        assert registry2 is registry1


if __name__ == "__main__":
    pytest.main(["-v", __file__])
