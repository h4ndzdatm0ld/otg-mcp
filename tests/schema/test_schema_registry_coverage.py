"""
Tests for schema registry coverage using mocks instead of file system operations.

These tests help achieve high code coverage without relying on filesystem operations.
"""

import os
import pytest
from unittest.mock import patch

from otg_mcp.schema_registry import SchemaRegistry


class TestSchemaRegistryCoverage:
    """Test cases for schema registry coverage using mocks."""

    def test_version_parsing_error(self):
        """Test handling of version parsing errors."""
        registry = SchemaRegistry()

        # Test with invalid version string
        with patch.object(registry, 'get_available_schemas', return_value=['1_30_0']):
            with patch.object(registry, 'get_latest_schema_version', return_value='1_30_0'):
                # Should fall back to latest version
                result = registry.find_closest_schema_version('invalid.version')
                assert result == '1_30_0'

    def test_empty_parsed_versions(self):
        """Test handling empty parsed versions list."""
        registry = SchemaRegistry()

        # Available versions list has items but none can be parsed
        with patch.object(registry, 'get_available_schemas', return_value=['invalid_1', 'invalid_2']):
            with patch.object(registry, '_parse_version', return_value=tuple()):
                with pytest.raises(ValueError, match="No valid schema versions available"):
                    registry.get_latest_schema_version()

    def test_partial_version(self):
        """Test handling partial version strings."""
        registry = SchemaRegistry()

        with patch.object(registry, 'get_available_schemas', return_value=['1_30_0']):
            # Test with only major version
            with patch.object(registry, '_parse_version', side_effect=lambda v: (1,) if v == '1' else (1, 30, 0)):
                result = registry.find_closest_schema_version('1')
                assert result == '1_30_0'

    def test_scan_custom_dir_error(self):
        """Test error handling when scanning custom schemas directory."""
        registry = SchemaRegistry('/nonexistent/path')

        # We need to be more specific with our patching to avoid the error
        # Only patch the call to os.listdir with the custom dir, not all calls
        original_listdir = os.listdir

        def mock_listdir(path):
            if path == '/nonexistent/path':
                raise PermissionError("Permission denied")
            return original_listdir(path)

        with patch('os.listdir', mock_listdir):
            # Should not raise exception but log a warning
            schemas = registry.get_available_schemas()
            assert isinstance(schemas, list)

    def test_different_custom_schemas_dir_instances(self):
        """Test that different custom_schemas_dir creates different instances."""
        # Create two separate instances with different custom schema directories
        registry1 = SchemaRegistry("/path/one")
        registry2 = SchemaRegistry("/path/two")

        # Verify they are different instances with different configurations
        assert registry1 is not registry2
        assert registry1._custom_schemas_dir != registry2._custom_schemas_dir


if __name__ == "__main__":
    pytest.main(["-v", __file__])
