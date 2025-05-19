"""Tests for the health check functionality in the OTG client."""

import logging
import pytest
from unittest.mock import MagicMock, patch

from otg_mcp.client import OtgClient
from otg_mcp.models import CapabilitiesVersionResponse

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_config():
    """Create a mocked config."""
    # Create a mock TargetsConfig to hold the targets dict
    targets_config = MagicMock()
    targets_config.targets = {
        "target1": MagicMock(),
        "target2": MagicMock(),
    }

    # Create the main Config mock with the targets attribute
    config = MagicMock()
    config.targets = targets_config

    return config


@pytest.fixture
def client(mock_config):
    """Create client with mocked config."""
    return OtgClient(mock_config)


@pytest.mark.asyncio
async def test_health_all_healthy(client):
    """Test health check when all targets are healthy."""
    # Arrange
    mock_version_info = CapabilitiesVersionResponse(
        api_spec_version="1.*", sdk_version="1.28.2", app_version="1.28.0"
    )

    # Mock the get_available_targets method to avoid it making internal get_target_version calls
    mock_targets = {"target1": {}, "target2": {}}

    with patch.object(
        client, "get_available_targets", return_value=mock_targets
    ), patch.object(
        client, "get_target_version", return_value=mock_version_info
    ) as mock_get_version:
        # Act
        result = await client.health()

        # Assert
        assert result.status == "success"
        assert len(result.targets) == 2
        assert all(target_info.healthy for target_info in result.targets.values())
        assert mock_get_version.call_count == 2


@pytest.mark.asyncio
async def test_health_one_unhealthy(client):
    """Test health check when one target is unhealthy."""
    # Arrange
    mock_version_info = CapabilitiesVersionResponse(
        api_spec_version="1.*", sdk_version="1.28.2", app_version="1.28.0"
    )

    async def mock_get_target_version(target):
        if target == "target1":
            return mock_version_info
        else:
            raise Exception("Connection timeout")

    with patch.object(
        client, "get_target_version", side_effect=mock_get_target_version
    ):
        # Act
        result = await client.health()

        # Assert
        assert result.status == "error"
        assert len(result.targets) == 2
        assert result.targets["target1"].healthy is True
        assert result.targets["target2"].healthy is False
        assert "Connection timeout" in result.targets["target2"].error


@pytest.mark.asyncio
async def test_health_all_unhealthy(client):
    """Test health check when all targets are unhealthy."""
    # Arrange
    with patch.object(
        client, "get_target_version", side_effect=Exception("Connection timeout")
    ):
        # Act
        result = await client.health()

        # Assert
        assert result.status == "error"
        assert len(result.targets) == 2
        assert all(not target_info.healthy for target_info in result.targets.values())


@pytest.mark.asyncio
async def test_health_single_target_healthy(client):
    """Test health check for a single target that is healthy."""
    # Arrange
    mock_version_info = CapabilitiesVersionResponse(
        api_spec_version="1.*", sdk_version="1.28.2", app_version="1.28.0"
    )

    with patch.object(
        client, "get_target_version", return_value=mock_version_info
    ):
        # Act
        result = await client.health("target1")

        # Assert
        assert result.status == "success"
        assert len(result.targets) == 1
        assert "target1" in result.targets
        assert result.targets["target1"].healthy is True


@pytest.mark.asyncio
async def test_health_single_target_unhealthy(client):
    """Test health check for a single target that is unhealthy."""
    # Arrange
    with patch.object(
        client, "get_target_version", side_effect=Exception("Connection timeout")
    ):
        # Act
        result = await client.health("target1")

        # Assert
        assert result.status == "error"
        assert len(result.targets) == 1
        assert "target1" in result.targets
        assert result.targets["target1"].healthy is False


@pytest.mark.asyncio
async def test_health_exception(client):
    """Test health check when an unexpected exception occurs."""
    # Arrange
    with patch.object(
        client, "get_available_targets", side_effect=Exception("Unexpected error")
    ):
        # Act
        result = await client.health()

        # Assert
        assert result.status == "error"
        assert len(result.targets) == 0
