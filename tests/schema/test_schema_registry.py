"""
Unit tests for the schema registry functionality.
"""

import os
import shutil
import tempfile

import pytest
import yaml

from otg_mcp.schema_registry import SchemaRegistry, get_schema_registry


class TestSchemaRegistry:
    """Test case for the SchemaRegistry class."""

    @pytest.fixture
    def mock_schemas_dir(self):
        """Create a temporary directory with mock schema files."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        # Create schema version directories
        v1_dir = os.path.join(temp_dir, "1_30_0")
        v2_dir = os.path.join(temp_dir, "1_31_0")
        os.makedirs(v1_dir)
        os.makedirs(v2_dir)

        # Create mock schema files
        v1_schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test Schema 1.30.0", "version": "1.30.0"},
            "components": {
                "schemas": {
                    "Flow": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "tx_rx": {"type": "object"},
                        },
                    }
                }
            },
        }

        v2_schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test Schema 1.31.0", "version": "1.31.0"},
            "components": {
                "schemas": {
                    "Flow": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "tx_rx": {"type": "object"},
                            "new_property": {"type": "string"},
                        },
                    }
                }
            },
        }

        # Write schemas to files
        with open(os.path.join(v1_dir, "openapi.yaml"), "w") as f:
            yaml.dump(v1_schema, f)

        with open(os.path.join(v2_dir, "openapi.yaml"), "w") as f:
            yaml.dump(v2_schema, f)

        yield temp_dir

        # Cleanup the temporary directory
        shutil.rmtree(temp_dir)

    def test_available_schemas(self, mock_schemas_dir):
        """Test getting available schemas."""
        # Create registry with mocked schemas directory
        registry = SchemaRegistry()
        registry._schemas_dir = mock_schemas_dir

        # Test available schemas
        available_schemas = registry.get_available_schemas()
        assert len(available_schemas) == 2
        assert "1_30_0" in available_schemas
        assert "1_31_0" in available_schemas

    def test_schema_exists(self, mock_schemas_dir):
        """Test checking if a schema exists."""
        registry = SchemaRegistry()
        registry._schemas_dir = mock_schemas_dir

        assert registry.schema_exists("1_30_0") is True
        assert registry.schema_exists("1_31_0") is True
        assert registry.schema_exists("2_0_0") is False

    def test_get_schema(self, mock_schemas_dir):
        """Test getting a schema."""
        registry = SchemaRegistry()
        registry._schemas_dir = mock_schemas_dir

        # Get complete schema
        schema = registry.get_schema("1_30_0")
        assert schema["info"]["title"] == "Test Schema 1.30.0"

        # Get component
        flow_schema = registry.get_schema("1_31_0", "components.schemas.Flow")
        assert flow_schema["type"] == "object"
        assert "new_property" in flow_schema["properties"]

    def test_get_invalid_schema(self, mock_schemas_dir):
        """Test getting an invalid schema."""
        registry = SchemaRegistry()
        registry._schemas_dir = mock_schemas_dir

        with pytest.raises(ValueError):
            registry.get_schema("non_existent")

    def test_get_invalid_component(self, mock_schemas_dir):
        """Test getting an invalid component."""
        registry = SchemaRegistry()
        registry._schemas_dir = mock_schemas_dir

        with pytest.raises(ValueError):
            registry.get_schema("1_30_0", "components.schemas.NonExistentComponent")

    def test_global_registry_instance(self):
        """Test the global registry instance."""
        registry1 = get_schema_registry()
        registry2 = get_schema_registry()

        # Should be the same instance
        assert registry1 is registry2


# TestTargetConfigApiVersion class has been removed since apiVersion is no longer a field
# in the TargetConfig model. The version is now determined dynamically based on the target's
# actual version or the latest available schema version.


# Test class for schema tools integration with server removed
# as the get_schema and get_available_schemas tools have been eliminated


if __name__ == "__main__":
    pytest.main(["-v", __file__])
