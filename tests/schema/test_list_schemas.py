"""
Test for list_schemas_for_target functionality.

This file contains tests for the updated list_schemas_for_target functionality
that focuses solely on returning components.schemas entries.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from otg_mcp.client import OtgClient


@pytest.fixture
def mock_schema():
    """Create a mock schema for testing."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Open Traffic Generator API"},
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
        },
        "paths": {"/config": {"get": {}, "post": {}}},
    }


@pytest.fixture
def client():
    """Create a client instance for testing."""
    from otg_mcp.config import Config
    mock_config = Config()
    return OtgClient(config=mock_config)


@pytest.mark.asyncio
async def test_list_schemas_for_target_returns_only_schemas(client, mock_schema):
    """Test that list_schemas_for_target returns only the schemas from components.schemas."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    # Mock the schema registry
    with patch("otg_mcp.client.get_schema_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get_schema.return_value = mock_schema
        mock_get_registry.return_value = mock_registry

        # Call the method
        result = await client.list_schemas_for_target("test-target")

        # Verify the result is a list containing only the schemas
        assert isinstance(result, list)
        assert sorted(result) == sorted(
            ["Flow", "Flow.Router", "Bgp.V4Peer", "Device.BgpRouter"]
        )

        # Verify that we're not returning any other information
        assert not any(key in result for key in ["openapi", "info", "paths"])
        assert not any(key in result for key in ["top_level", "components", "servers"])

        # Make sure the schema registry was called with the correct version
        mock_registry.get_schema.assert_called_once_with("1.30.0")


@pytest.mark.asyncio
async def test_list_schemas_for_target_empty_components(client):
    """Test handling when the schema has no components section."""
    # Setup mocks with AsyncMock
    client._get_target_config = AsyncMock(return_value={"apiVersion": "1.30.0"})

    schema_without_components = {
        "openapi": "3.0.3",
        "info": {"title": "Minimal API"},
        "paths": {},
    }

    # Mock the schema registry
    with patch("otg_mcp.client.get_schema_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get_schema.return_value = schema_without_components
        mock_get_registry.return_value = mock_registry

        # Call the method
        result = await client.list_schemas_for_target("test-target")

        # Verify the result is an empty list
        assert isinstance(result, list)
        assert len(result) == 0


@pytest.mark.asyncio
async def test_list_schemas_for_target_target_not_found(client):
    """Test error handling when target is not found."""
    # Setup AsyncMock to return None for target config
    client._get_target_config = AsyncMock(return_value=None)

    # Call the method and verify it raises ValueError
    with pytest.raises(ValueError) as excinfo:
        await client.list_schemas_for_target("non-existent-target")

    assert "not found" in str(excinfo.value)
