"""
Tests for achieving full coverage of the schema registry.
"""

from unittest.mock import patch, mock_open

import pytest
import yaml

from otg_mcp.schema_registry import SchemaRegistry


def test_get_available_schemas_exception_handling():
    """Test exception handling in get_available_schemas for custom directory."""
    custom_dir = "/non/existent/path"
    registry = SchemaRegistry(custom_dir)
    
    # Create a selective mock that only raises an exception for the custom directory
    def selective_listdir(path):
        if path == custom_dir:
            raise PermissionError("Permission denied")
        # Return some schema directories for the built-in path
        return ["1_30_0", "1_28_0"]

    # Mock os.path.exists to return True for all paths
    with patch('os.path.exists', return_value=True):
        # Use the selective mock for listdir
        with patch('os.listdir', side_effect=selective_listdir):
            with patch('os.path.isdir', return_value=True):
                # This should not raise an exception but handle it gracefully
                available_schemas = registry.get_available_schemas()
                assert isinstance(available_schemas, list)
                # Should still have the built-in schemas
                assert "1_30_0" in available_schemas
                assert "1_28_0" in available_schemas


def test_load_schema_from_path_error():
    """Test error handling in _load_schema_from_path."""
    registry = SchemaRegistry()
    
    # Mock open to raise an exception when trying to open the schema file
    mock_file = mock_open()
    mock_file.side_effect = IOError("File not found")
    
    with patch("builtins.open", mock_file):
        # Try to load from a schema path
        result = registry._load_schema_from_path("/fake/path/schema.yaml", "1_30_0", "test")
        # Should return False indicating failure
        assert result is False

def test_load_schema_yaml_error():
    """Test handling of YAML parsing errors."""
    registry = SchemaRegistry()

    # Create a mock that returns invalid YAML content
    mock_file = mock_open(read_data="invalid: yaml: content: - [")

    with patch("builtins.open", mock_file):
        # Mock yaml.safe_load to raise a YAML parsing error
        with patch("yaml.safe_load", side_effect=yaml.YAMLError("YAML parsing error")):
            # Try to load from a schema path with invalid YAML
            result = registry._load_schema_from_path("/fake/path/schema.yaml", "1_30_0", "test")
            # Should return False indicating failure
            assert result is False


def test_parse_version_malformed():
    """Test _parse_version with malformed version strings."""
    registry = SchemaRegistry()

    # Test with completely non-numeric version
    result = registry._parse_version("abc_def_xyz")
    assert result == tuple()

    # Test with partially numeric version
    result = registry._parse_version("1_abc_2")
    assert result == (1, 2)  # Should extract the numeric parts


def test_get_parsed_versions_empty_valid():
    """Test _get_parsed_versions with empty or invalid versions."""
    registry = SchemaRegistry()

    # Test with empty list
    result = registry._get_parsed_versions([])
    assert result == []

    # Test with invalid versions that can't be parsed
    result = registry._get_parsed_versions(["invalid", "not_a_version"])
    assert result == []

def test_get_schema_with_component_not_found():
    """Test error handling when requesting a non-existent component."""
    registry = SchemaRegistry()

    # Create a mock schema with a valid structure but missing the requested component
    mock_schema = {
        "components": {
            "schemas": {
                "ExistingSchema": {"type": "object"}
            }
        }
    }

    # Mock the registry to return our test schema
    with patch.object(registry, "schema_exists", return_value=True):
        with patch.dict(registry.schemas, {"1_30_0": mock_schema}):
            # Try to access a non-existent schema
            with pytest.raises(ValueError, match="Schema NonExistentSchema not found"):
                registry.get_schema("1_30_0", "components.schemas.NonExistentSchema")

def test_get_schema_with_invalid_path():
    """Test error handling when requesting an invalid component path."""
    registry = SchemaRegistry()

    # Create a mock schema
    mock_schema = {"components": {"schemas": {}}}

    # Mock the registry to return our test schema
    with patch.object(registry, "schema_exists", return_value=True):
        with patch.dict(registry.schemas, {"1_30_0": mock_schema}):
            # Try to access an invalid path (components.invalid)
            with pytest.raises(ValueError, match="Component invalid not found"):
                registry.get_schema("1_30_0", "components.invalid")

def test_get_schema_components_non_dict():
    """Test get_schema_components with a component that is not a dictionary."""
    registry = SchemaRegistry()

    # Create a mock schema where a component is not a dictionary
    mock_schema = {"components": {"schemas": "not_a_dict"}}

    # Mock the registry to return our test schema
    with patch.object(registry, "schema_exists", return_value=True):
        with patch.dict(registry.schemas, {"1_30_0": mock_schema}):
            # Should return an empty list for non-dictionary components
            result = registry.get_schema_components("1_30_0")
            assert result == []
