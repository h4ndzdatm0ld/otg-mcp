"""
Final tests to achieve 100% coverage of the schema registry.
"""

from unittest.mock import patch

import pytest

from otg_mcp.schema_registry import SchemaRegistry


def test_get_schema_error_loading():
    """Test error handling in get_schema when schema fails to load."""
    registry = SchemaRegistry()
    
    # Mock schema_exists to return True but load_schema to fail
    with patch.object(registry, "schema_exists", return_value=True):
        # Force _load_schema_from_path to always fail for both custom and built-in
        with patch.object(registry, "_load_schema_from_path", return_value=False):
            # Should raise ValueError
            with pytest.raises(ValueError, match="Error loading schema"):
                registry.get_schema("1_30_0")


def test_schema_component_not_found_in_navigation():
    """Test error handling when a component in the navigation path is not found."""
    registry = SchemaRegistry()
    
    # Create a mock schema with nested structure but missing a component
    mock_schema = {
        "components": {
            "schemas": {
                "Flow": {}  # Missing the 'properties' component
            }
        }
    }
    
    # Mock the registry to return our test schema
    with patch.object(registry, "schema_exists", return_value=True):
        with patch.dict(registry.schemas, {"1_30_0": mock_schema}):
            # The actual implementation treats the whole path after components.schemas as the schema name
            with pytest.raises(ValueError, match="Schema Flow.properties.name not found"):
                registry.get_schema("1_30_0", "components.schemas.Flow.properties.name")


def test_parse_version_with_shorter_requested_version():
    """Test find_closest_schema_version with a shorter requested version."""
    registry = SchemaRegistry()
    
    # Available versions
    available_versions = ["1_30_0", "1_28_0", "2_0_0"]
    
    # Mock getting available schemas
    with patch.object(registry, "get_available_schemas", return_value=available_versions):
        # Return valid parsed versions but with different lengths
        def mock_parse_version(version):
            if version == "1.30":
                return (1, 30)  # Missing patch version
            elif version == "1_30_0":
                return (1, 30, 0)
            elif version == "1_28_0":
                return (1, 28, 0)
            return tuple()
            
        # Mock _get_parsed_versions to use our mock_parse_version
        def mock_get_parsed_versions(versions):
            parsed = []
            for v in versions:
                parsed_v = mock_parse_version(v)
                if parsed_v:  # Only include successfully parsed versions
                    parsed.append((v, parsed_v))
            return parsed
            
        with patch.object(registry, "_parse_version", side_effect=mock_parse_version):
            with patch.object(registry, "_get_parsed_versions", side_effect=mock_get_parsed_versions):
                # Should handle different version tuple lengths
                result = registry.find_closest_schema_version("1.30")
                assert result == "1_30_0"
                
                
def test_custom_schema_path_loading_precedence():
    """Test that custom schema paths take precedence over built-in paths."""
    # Create a registry with a custom path
    registry = SchemaRegistry("/custom/path")
    
    # Set up paths for the registry
    
    # Set up the registry with our test paths
    registry._custom_schemas_dir = "/custom/path"
    registry._builtin_schemas_dir = "/builtin/path"
    
    # Mock functions to simulate both paths existing
    with patch('os.path.exists', return_value=True):
        # Mock schema loading to track which path is tried first
        called_paths = []

        def track_schema_loading(path, version, source_type):
            called_paths.append((path, source_type))
            # Always succeed
            registry.schemas[version] = {"test": "schema"}
            return True

        with patch.object(registry, "schema_exists", return_value=True):
            with patch.object(registry, "_load_schema_from_path", side_effect=track_schema_loading):
                # Get the schema - should try custom path first
                registry.get_schema("1_30_0")

                # Verify custom was tried first
                assert len(called_paths) >= 1
                assert called_paths[0][1] == "custom"  # First call should be to custom path


def test_find_schema_with_no_valid_versions():
    """Test find_closest_schema_version when no versions can be parsed."""
    registry = SchemaRegistry()

    # Mock available schemas with invalid versions
    with patch.object(registry, "get_available_schemas", return_value=["invalid", "not_a_version"]):
        # Mock _get_parsed_versions to return empty list (no valid parsed versions)
        with patch.object(registry, "_get_parsed_versions", return_value=[]):
            # Should raise ValueError because no valid versions are available
            with pytest.raises(ValueError, match="No valid schema versions available"):
                registry.find_closest_schema_version("1.0.0")
