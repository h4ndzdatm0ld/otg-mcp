"""
Additional tests to achieve 100% coverage of the schema registry.
"""

from unittest.mock import patch

import pytest

from otg_mcp.schema_registry import SchemaRegistry


def test_schema_registry_with_invalid_builtin_dir():
    """Test SchemaRegistry initialization with invalid built-in directory."""
    registry = SchemaRegistry()
    
    # Set the built-in schemas directory to a non-existent path
    registry._builtin_schemas_dir = "/non/existent/builtin/schemas"
    registry._available_schemas = None  # Force refresh
    
    # Mock os.path.exists to simulate non-existent built-in directory
    with patch('os.path.exists', side_effect=lambda path: path != registry._builtin_schemas_dir):
        # Should gracefully handle non-existent built-in directory
        schemas = registry.get_available_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) == 0


def test_get_parsed_versions_with_mixed_formats():
    """Test _get_parsed_versions with a mix of valid and invalid version formats."""
    registry = SchemaRegistry()
    
    # Mix of valid and invalid versions
    versions = ["1_30_0", "invalid", "2_0_0", "not_a_version"]
    
    # Mock _parse_version to return appropriate tuples
    def mock_parse_version(version):
        if version == "1_30_0":
            return (1, 30, 0)
        elif version == "2_0_0":
            return (2, 0, 0)
        else:
            return tuple()
    
    with patch.object(registry, "_parse_version", side_effect=mock_parse_version):
        result = registry._get_parsed_versions(versions)
        
        # Should only include the valid versions
        assert len(result) == 2
        assert ("1_30_0", (1, 30, 0)) in result
        assert ("2_0_0", (2, 0, 0)) in result


def test_get_schema_with_keyerror():
    """Test error handling in get_schema when KeyError occurs."""
    registry = SchemaRegistry()
    
    # Create a mock schema without the necessary structure
    mock_schema = {"components": {}}  # Missing the "schemas" key
    
    # Mock the registry to return our test schema
    with patch.object(registry, "schema_exists", return_value=True):
        with patch.dict(registry.schemas, {"1_30_0": mock_schema}):
            # Should raise ValueError with appropriate message
            with pytest.raises(ValueError, match="Error accessing components.schemas"):
                registry.get_schema("1_30_0", "components.schemas.TestSchema")


def test_find_closest_schema_version_with_unparseable_version():
    """Test find_closest_schema_version with unparseable requested version."""
    registry = SchemaRegistry()
    
    # Mock available_schemas
    available_versions = ["1_30_0", "1_28_0"]
    
    with patch.object(registry, "get_available_schemas", return_value=available_versions):
        # Mock _parse_version to return empty tuple for the requested version
        with patch.object(registry, "_parse_version", return_value=tuple()):
            # Should fall back to latest version
            with patch.object(registry, "get_latest_schema_version", return_value="1_30_0"):
                result = registry.find_closest_schema_version("unparseable")
                assert result == "1_30_0"


def test_find_closest_version_with_short_version_tuple():
    """Test find_closest_schema_version with short version tuple (major only)."""
    registry = SchemaRegistry()
    
    # Available versions
    available_versions = ["1_30_0", "1_28_0", "2_0_0"]
    
    # Mock getting available schemas
    with patch.object(registry, "get_available_schemas", return_value=available_versions):
        # Mock parsing to return short tuples
        def mock_parse(version):
            if version == "1.0":
                return (1,)  # Major only
            elif version == "1_30_0":
                return (1, 30, 0)
            elif version == "1_28_0":
                return (1, 28, 0)
            elif version == "2_0_0":
                return (2, 0, 0)
            return tuple()
        
        with patch.object(registry, "_parse_version", side_effect=mock_parse):
            # Should pad the requested version with zeros
            result = registry.find_closest_schema_version("1.0")
            # Should find 1_30_0 as it's the latest with major version 1
            assert result == "1_30_0"
