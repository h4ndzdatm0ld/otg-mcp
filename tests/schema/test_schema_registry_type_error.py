"""
Test for TypeError/KeyError handling in schema_registry.py component path navigation.

This module provides a test to cover the exception handling code in lines 228-230 of schema_registry.py,
which was not covered by the existing tests.
"""

from unittest.mock import MagicMock

import pytest

from otg_mcp.schema_registry import SchemaRegistry


def test_component_path_navigation_type_error():
    """Test handling of TypeError when navigating through non-dict component."""
    # Create a SchemaRegistry instance
    registry = SchemaRegistry()
    
    # Set up a mock schema with a non-dict value in the path
    registry.schema_exists = MagicMock(return_value=True)
    registry.schemas = {
        "1_30_0": {
            "info": {
                "title": "Test API",
                "version": "1.30.0"
            },
            "paths": 12345  # This is not a dict, so trying to navigate through it will cause TypeError
        }
    }
    
    # Try to navigate through the non-dict value in the standard navigation path
    # This should trigger the TypeError exception handling code
    with pytest.raises(ValueError) as excinfo:
        registry.get_schema("1_30_0", "paths.something")
    
    # Verify the error message contains the expected information
    assert "Invalid component path paths.something:" in str(excinfo.value)
    # Check for the actual error message which indicates a type error with the integer
    assert any(phrase in str(excinfo.value) for phrase in [
        "TypeError",
        "not subscriptable",
        "argument of type 'int' is not iterable"
    ])


if __name__ == "__main__":
    pytest.main(["-v", __file__])
