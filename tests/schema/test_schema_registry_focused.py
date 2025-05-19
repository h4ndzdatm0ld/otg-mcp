"""
Tests for schema registry's edge cases.

Using mocks instead of filesystem operations to improve test reliability.
"""

from unittest.mock import MagicMock

import pytest

from otg_mcp.schema_registry import SchemaRegistry


class TestSchemaRegistryFocused:
    """Test cases for schema registry edge cases using mocks."""

    def test_get_schema_components_non_dict_at_path(self):
        """Test get_schema_components with a non-dict at the specified path."""
        registry = SchemaRegistry()
        registry.get_schema = MagicMock(return_value=[1, 2, 3])  # Return a list, not a dict
        
        # This should execute the warning path in get_schema_components
        result = registry.get_schema_components("1_30_0", "some.path")
        
        # Should return an empty list when the component is not a dict
        assert result == []
    
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
    
    def test_independent_registry_instances(self):
        """Test that schema registry instances are independent."""
        # Create two registry instances with different custom directories
        registry1 = SchemaRegistry(custom_schemas_dir="/path/to/custom1")
        registry2 = SchemaRegistry(custom_schemas_dir="/path/to/custom2")
        
        # They should be separate instances with different configurations
        assert registry1 is not registry2
        assert registry1._custom_schemas_dir != registry2._custom_schemas_dir
        
        # Changes to one instance should not affect the other
        registry1._available_schemas = ["test1"]
        registry2._available_schemas = ["test2"]
        assert registry1._available_schemas != registry2._available_schemas


if __name__ == "__main__":
    pytest.main(["-v", __file__])
