"""
Tests for schema retrieval with different input formats.

This module contains tests that verify the schema retrieval logic can handle
various formats of schema names (simple vs fully qualified paths).
"""

import pytest
from unittest.mock import AsyncMock

from otg_mcp.client import OtgClient
from otg_mcp.config import Config, TargetConfig




@pytest.fixture
def remote_spec():
    """An OpenAPI document of the shape a target serves at /docs/openapi.json."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Open Traffic Generator API", "version": "1.30.0"},
        "components": {
            "schemas": {
                "Flow": {"description": "Mock schema for Flow"},
                "Port": {"description": "Mock schema for Port"},
                "Config": {"description": "Mock schema for Config"},
            }
        },
    }


@pytest.fixture
def client(remote_spec):
    """Create a client whose target serves its own schema."""
    mock_config = Config()
    mock_config.targets.targets["test-target"] = TargetConfig()
    client = OtgClient(config=mock_config)
    # The client now prefers the schema the target serves, so stub that fetch
    # rather than the bundled registry. No network access in unit tests.
    client._fetch_remote_schema = AsyncMock(return_value=remote_spec)
    return client


@pytest.mark.asyncio
async def test_get_schemas_simple_names(client):
    """Test retrieving schemas using simple names like 'Flow', 'Port'."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    # Call the method with simple names
    result = await client.get_schemas_for_target(
        "test-target", ["Flow", "Port", "Config"]
    )

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
async def test_get_schemas_qualified_names(client):
    """Test retrieving schemas using fully qualified paths."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    # Call the method with qualified names
    result = await client.get_schemas_for_target(
        "test-target",
        [
            "components.schemas.Flow",
            "components.schemas.Port",
            "components.schemas.Config",
        ],
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
async def test_get_schemas_mixed_format(client):
    """Test retrieving schemas using both simple and fully qualified names."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    # Call the method with mixed format names
    result = await client.get_schemas_for_target(
        "test-target", ["Flow", "components.schemas.Port", "Config"]
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
async def test_schema_not_found_handling(client):
    """Test handling of non-existent schemas."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})


    # Call the method with a non-existent schema
    result = await client.get_schemas_for_target("test-target", ["NonExistentSchema"])

    # Verify the result contains an error for the non-existent schema
    assert "NonExistentSchema" in result
    assert "error" in result["NonExistentSchema"]
    assert "not found" in result["NonExistentSchema"]["error"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
