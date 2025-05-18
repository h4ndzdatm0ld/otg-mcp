"""
Tests for schema retrieval functionality.

This module contains tests for the schema retrieval functionality,
specifically focusing on the ability to retrieve schemas with dotted notation.
"""

import logging
from unittest.mock import MagicMock

import pytest

from otg_mcp.schema_registry import SchemaRegistry

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def mock_schema():
    """Create a mock schema for testing."""
    return {
        "components": {
            "schemas": {
                "Flow": {"description": "A flow object"},
                "Flow.Router": {"description": "A flow router object"},
                "Bgp.V4Peer": {"description": "A BGP v4 peer object"},
                "Device.BgpRouter": {"description": "A BGP router device"},
            },
            "responses": {
                "Success": {"description": "Success response"},
                "Failure": {"description": "Failure response"},
            },
        }
    }


class TestSchemaRegistry:
    """Test class for SchemaRegistry."""

    def test_get_schema_with_simple_path(self, mock_schema):
        """Test retrieving a schema with a simple path."""
        # Create schema registry with a mocked schema
        registry = SchemaRegistry()
        registry.schema_exists = MagicMock(return_value=True)
        registry.schemas = {"1_30_0": mock_schema}

        # Test getting a basic component path
        result = registry.get_schema("1.30.0", "components")
        assert result == mock_schema["components"]

        # Test getting a nested component path
        result = registry.get_schema("1.30.0", "components.schemas")
        assert result == mock_schema["components"]["schemas"]

    def test_get_schema_with_dotted_notation(self, mock_schema):
        """Test retrieving a schema with dotted notation in the name."""
        # Create schema registry with a mocked schema
        registry = SchemaRegistry()
        registry.schema_exists = MagicMock(return_value=True)
        registry.schemas = {"1_30_0": mock_schema}

        # Test getting a schema with dots in the name
        result = registry.get_schema("1.30.0", "components.schemas.Flow.Router")
        assert result == mock_schema["components"]["schemas"]["Flow.Router"]

        # Test another schema with dots
        result = registry.get_schema("1.30.0", "components.schemas.Bgp.V4Peer")
        assert result == mock_schema["components"]["schemas"]["Bgp.V4Peer"]

        # And another one
        result = registry.get_schema("1.30.0", "components.schemas.Device.BgpRouter")
        assert result == mock_schema["components"]["schemas"]["Device.BgpRouter"]

    def test_get_schema_component_not_found(self, mock_schema):
        """Test error handling when a schema component is not found."""
        # Create schema registry with a mocked schema
        registry = SchemaRegistry()
        registry.schema_exists = MagicMock(return_value=True)
        registry.schemas = {"1_30_0": mock_schema}

        # Test getting a non-existent schema
        with pytest.raises(ValueError) as excinfo:
            registry.get_schema("1.30.0", "components.schemas.NonExistent")
        assert "not found" in str(excinfo.value)

    def test_get_schema_components(self, mock_schema):
        """Test getting all schema components."""
        # Create schema registry with a mocked schema
        registry = SchemaRegistry()
        registry.schema_exists = MagicMock(return_value=True)
        registry.schemas = {"1_30_0": mock_schema}

        # Test getting all schema components
        result = registry.get_schema_components("1.30.0", "components.schemas")
        expected = ["Flow", "Flow.Router", "Bgp.V4Peer", "Device.BgpRouter"]
        assert sorted(result) == sorted(expected)


if __name__ == "__main__":
    pytest.main(["-v", __file__])
