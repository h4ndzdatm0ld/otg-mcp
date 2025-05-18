"""
Focused tests for schema registry to achieve 100% coverage.

This module provides tests specifically targeting lines that are still 
showing as uncovered in the schema_registry.py module.
"""

import os
import shutil
import tempfile
from unittest.mock import MagicMock

import pytest

from otg_mcp.schema_registry import SchemaRegistry, get_schema_registry


class TestSchemaRegistryFocused:
    """Test cases specifically targeting uncovered lines in SchemaRegistry."""

    def test_get_schema_components_non_dict_at_path(self):
        """Test get_schema_components with a non-dict at the specified path."""
        registry = SchemaRegistry()
        registry.get_schema = MagicMock(return_value=[1, 2, 3])  # Return a list, not a dict
        
        # This should execute the warning path in get_schema_components
        result = registry.get_schema_components("1_30_0", "some.path")
        
        # Should return an empty list when the component is not a dict
        assert result == []
    
    def test_schema_loading_exception(self):
        """Test exception handling during schema loading."""
        registry = SchemaRegistry()
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        try:
            # Set up the registry to use our temp dir
            v1_dir = os.path.join(temp_dir, "1_30_0")
            os.makedirs(v1_dir)
            registry._schemas_dir = temp_dir
            
            # Create a schema file that will cause a YAML parsing error
            with open(os.path.join(v1_dir, "openapi.yaml"), "w") as f:
                f.write("invalid: yaml: content\n\tindentation: error")
            
            # This should trigger the exception handling code
            with pytest.raises(ValueError) as excinfo:
                registry.get_schema("1_30_0")
            
            assert "Error loading schema" in str(excinfo.value)
        finally:
            # Clean up
            shutil.rmtree(temp_dir)

    def test_schema_components_schemas_keyerror(self):
        """Test KeyError handling when accessing components.schemas."""
        registry = SchemaRegistry()
        
        # Mock the schema to not have 'schemas' under 'components'
        registry.schema_exists = MagicMock(return_value=True)
        registry.schemas = {
            "1_30_0": {
                "components": {
                    # No 'schemas' key here
                }
            }
        }
        
        # This should trigger the KeyError handling for components.schemas
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1_30_0", "components.schemas.Flow")
        
        assert "Error accessing components.schemas" in str(excinfo.value)
    
    def test_component_navigation_typeerror(self):
        """Test TypeError handling during component navigation."""
        registry = SchemaRegistry()
        
        # Mock the schema to have a non-navigable item in the path
        registry.schema_exists = MagicMock(return_value=True)
        registry.schemas = {
            "1_30_0": {
                "components": {
                    "schemas": {
                        "Flow": 123  # Not a dict, so can't navigate further
                    }
                }
            }
        }
        
        # This should trigger the special handling for components.schemas.X
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1_30_0", "components.schemas.Flow.someProperty")
        
        # Due to the special handling for components.schemas.X paths, the error occurs at that level
        # rather than in the TypeError catch block
        assert "Schema Flow.someProperty not found in components.schemas" in str(excinfo.value)
    
    def test_global_registry_init(self):
        """Test global schema registry initialization."""
        # Reset the global registry
        import otg_mcp.schema_registry
        otg_mcp.schema_registry._schema_registry = None
        
        # This should create a new registry
        registry1 = get_schema_registry()
        assert registry1 is not None
        
        # This should return the same instance
        registry2 = get_schema_registry()
        assert registry2 is registry1


if __name__ == "__main__":
    pytest.main(["-v", __file__])
