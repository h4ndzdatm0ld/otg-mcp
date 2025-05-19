"""
Edge case tests to achieve 100% coverage of the schema registry.
"""

from unittest.mock import patch

import pytest

from otg_mcp.schema_registry import SchemaRegistry


def test_schema_navigation_typeerror():
    """Test error handling in schema navigation when TypeError occurs."""
    registry = SchemaRegistry()
    
    # Create a mock schema with an element that's not a dictionary for navigation
    mock_schema = {
        "components": "not_a_dict"  # This will cause TypeError when trying to access components.schemas
    }
    
    # Mock the registry to return our test schema
    with patch.object(registry, "schema_exists", return_value=True):
        with patch.dict(registry.schemas, {"1_30_0": mock_schema}):
            # The actual implementation raises TypeError directly
            with pytest.raises(TypeError, match="string indices must be integers"):
                registry.get_schema("1_30_0", "components.schemas.TestSchema")


def test_get_schema_with_standard_navigation():
    """Test accessing components without using special component path handling."""
    registry = SchemaRegistry()
    
    # Create a mock schema with nested structure
    mock_schema = {
        "components": {
            "schemas": {
                "Flow": {
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Flow name"
                        }
                    }
                }
            }
        }
    }
    
    # Mock the registry to return our test schema
    with patch.object(registry, "schema_exists", return_value=True):
        with patch.dict(registry.schemas, {"1_30_0": mock_schema}):
            # We need to use standard component path that doesn't trigger special handling
            result = registry.get_schema("1_30_0", "components")
            assert "schemas" in result
            assert "Flow" in result["schemas"]


def test_loading_schema_from_builtin_path_after_custom_fails():
    """Test loading schema from built-in path when custom fails."""
    registry = SchemaRegistry("/custom/path")
    
    # Create a side effect function for _load_schema_from_path
    def load_schema_side_effect(path, version, source_type):
        # Return False for custom path, True for built-in path
        result = source_type == "built-in"
        if result:
            # Need to actually populate the schema when returning True
            registry.schemas[version] = {"test": "schema"}
        return result
    
    # Mock methods
    with patch.object(registry, "schema_exists", return_value=True):
        with patch.object(registry, "_load_schema_from_path", side_effect=load_schema_side_effect):
            # Should load from built-in path after custom path fails
            result = registry.get_schema("1_30_0")
            # Verify we got the schema we set in the mock
            assert result == {"test": "schema"}
