"""Test the health function to ensure proper status reporting."""

import pytest
from unittest import mock

from otg_mcp.client import OtgClient
from otg_mcp.models import CapabilitiesVersionResponse, HealthStatus


@pytest.fixture
def mock_otg_client():
    """Create a mock OtgClient for testing."""
    mock_config = mock.MagicMock()
    mock_config.schemas.schema_path = None
    mock_config.targets.targets = {
        "healthy-target": {},
        "unhealthy-target": {}
    }
    
    # Create a partial mock of OtgClient
    client = OtgClient(config=mock_config)
    client.get_available_targets = mock.AsyncMock(return_value={
        "healthy-target": {},
        "unhealthy-target": {}
    })
    
    return client


@pytest.mark.asyncio
async def test_health_all_healthy(mock_otg_client):
    """Test that status remains 'success' when all targets are healthy."""
    # Mock the get_target_version to always succeed
    mock_otg_client.get_target_version = mock.AsyncMock(return_value=CapabilitiesVersionResponse(
        api_spec_version="1.0",
        sdk_version="1.0",
        app_version="1.0"
    ))
    
    # Call the health function
    result = await mock_otg_client.health()
    
    # Verify that overall status is success
    assert result.status == "success"
    assert "healthy-target" in result.targets
    assert "unhealthy-target" in result.targets
    assert result.targets["healthy-target"].healthy is True
    assert result.targets["unhealthy-target"].healthy is True


@pytest.mark.asyncio
async def test_health_with_unhealthy_target(mock_otg_client):
    """Test that status changes to 'error' when any target is unhealthy."""
    # Mock the get_target_version to succeed for one target and fail for another
    async def mock_get_target_version(target):
        if target == "healthy-target":
            return CapabilitiesVersionResponse(
                api_spec_version="1.0",
                sdk_version="1.0",
                app_version="1.0"
            )
        else:
            raise ValueError("Connection timeout to host")
    
    mock_otg_client.get_target_version = mock_get_target_version
    
    # Call the health function
    result = await mock_otg_client.health()
    
    # Verify that overall status is error
    assert result.status == "error"
    assert "healthy-target" in result.targets
    assert "unhealthy-target" in result.targets
    assert result.targets["healthy-target"].healthy is True
    assert result.targets["unhealthy-target"].healthy is False
    assert "Connection timeout" in result.targets["unhealthy-target"].error


@pytest.mark.asyncio
async def test_health_with_exception(mock_otg_client):
    """Test that status is set to 'error' when the health check itself fails."""
    # Mock get_available_targets to raise an exception
    mock_otg_client.get_available_targets = mock.AsyncMock(side_effect=Exception("Failed to get targets"))
    
    # Call the health function
    result = await mock_otg_client.health()
    
    # Verify that overall status is error
    assert result.status == "error"
    assert result.targets == {}


@pytest.mark.asyncio
async def test_health_specific_target_healthy(mock_otg_client):
    """Test health check for a specific target that is healthy."""
    # Mock the get_target_version to succeed
    mock_otg_client.get_target_version = mock.AsyncMock(return_value=CapabilitiesVersionResponse(
        api_spec_version="1.0",
        sdk_version="1.0",
        app_version="1.0"
    ))
    
    # Call the health function with a specific target
    result = await mock_otg_client.health("healthy-target")
    
    # Verify that overall status is success
    assert result.status == "success"
    assert len(result.targets) == 1
    assert "healthy-target" in result.targets
    assert result.targets["healthy-target"].healthy is True


@pytest.mark.asyncio
async def test_health_specific_target_unhealthy(mock_otg_client):
    """Test health check for a specific target that is unhealthy."""
    # Mock the get_target_version to fail
    mock_otg_client.get_target_version = mock.AsyncMock(
        side_effect=ValueError("Connection timeout to host")
    )
    
    # Call the health function with a specific target
    result = await mock_otg_client.health("unhealthy-target")
    
    # Verify that overall status is error
    assert result.status == "error"
    assert len(result.targets) == 1
    assert "unhealthy-target" in result.targets
    assert result.targets["unhealthy-target"].healthy is False
    assert "Connection timeout" in result.targets["unhealthy-target"].error
