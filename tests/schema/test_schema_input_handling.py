"""
Tests for schema retrieval with different input formats.

This module contains tests that verify the schema retrieval logic can handle
various formats of schema names (simple vs fully qualified paths).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from otg_mcp.client import OtgClient


@pytest.fixture
def mock_schema_registry():
    """Create a mock schema registry for testing."""
    mock_registry = MagicMock()
    # Setup schema content for different schema names
    mock_registry.get_schema.side_effect = lambda version, component=None: {
        "description": f"Mock schema for {component or 'all'}"
    }
    return mock_registry


@pytest.fixture
def client(mock_schema_registry):
    """Create a client instance for testing with a mock schema registry."""
    from otg_mcp.config import Config
    mock_config = Config()
    return OtgClient(config=mock_config, schema_registry=mock_schema_registry)


@pytest.mark.asyncio
async def test_get_schemas_simple_names(client, mock_schema_registry):
    """Test retrieving schemas using simple names like 'Flow', 'Port'."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    # Call the method with simple names
    result = await client.get_schemas_for_target("test-target", ["Flow", "Port", "Config"])

    # Verify the result contains the requested schemas
    assert "Flow" in result
    assert "Port" in result
    assert "Config" in result
    
    # Verify the schemas are valid objects
    assert isinstance(result["Flow"], dict)
    assert isinstance(result["Port"], dict)
    assert isinstance(result["Config"], dict)
    
    # Verify description exists in schemas
    assert "description" in result["Flow"]
    assert "description" in result["Port"]
    assert "description" in result["Config"]


@pytest.mark.asyncio
async def test_get_schemas_qualified_names(client, mock_schema_registry):
    """Test retrieving schemas using fully qualified paths."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    # Call the method with qualified names
    result = await client.get_schemas_for_target(
        "test-target", 
        ["components.schemas.Flow", "components.schemas.Port", "components.schemas.Config"]
    )

    # Verify the result contains the requested schemas
    assert "components.schemas.Flow" in result
    assert "components.schemas.Port" in result
    assert "components.schemas.Config" in result
    
    # Verify the schemas are valid objects
    assert isinstance(result["components.schemas.Flow"], dict)
    assert isinstance(result["components.schemas.Port"], dict)
    assert isinstance(result["components.schemas.Config"], dict)


@pytest.mark.asyncio
async def test_get_schemas_mixed_format(client, mock_schema_registry):
    """Test retrieving schemas using both simple and fully qualified names."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    # Call the method with mixed format names
    result = await client.get_schemas_for_target(
        "test-target", 
        ["Flow", "components.schemas.Port", "Config"]
    )

    # Verify the result contains all requested schemas
    assert "Flow" in result
    assert "components.schemas.Port" in result
    assert "Config" in result
    
    # Verify the schemas are valid objects
    assert isinstance(result["Flow"], dict)
    assert isinstance(result["components.schemas.Port"], dict)
    assert isinstance(result["Config"], dict)


@pytest.mark.asyncio
async def test_schema_not_found_handling(client, mock_schema_registry):
    """Test handling of non-existent schemas."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    # Configure mock to raise an exception for a non-existent schema
    def mock_get_schema(version, component=None):
        if component == "components.schemas.NonExistentSchema" or component == "NonExistentSchema":
            raise ValueError("Schema not found")
        return {"description": f"Mock schema for {component or 'all'}"}

    mock_schema_registry.get_schema.side_effect = mock_get_schema

    # Call the method with a non-existent schema
    result = await client.get_schemas_for_target("test-target", ["NonExistentSchema"])

    # Verify the result contains an error for the non-existent schema
    assert "NonExistentSchema" in result
    assert "error" in result["NonExistentSchema"]
    assert "not found" in result["NonExistentSchema"]["error"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
