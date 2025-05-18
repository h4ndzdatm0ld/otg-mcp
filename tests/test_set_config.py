"""
Test for set_config functionality that returns applied configuration.
"""

import logging
from unittest.mock import MagicMock

import pytest

from otg_mcp.client import OtgClient
from otg_mcp.models import ConfigResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def mock_api():
    """Create a mock API client for testing."""
    mock_api = MagicMock()

    # Mock config object with serialize method
    mock_config = MagicMock()
    mock_config.serialize.return_value = {
        "ports": [{"name": "port1", "location": "localhost:5555"}],
        "flows": [{"name": "flow1", "tx_rx": {"port": ["port1", "port1"]}}],
    }
    mock_config.DICT = "dict"

    # Configure get_config to return our mock config
    mock_api.get_config.return_value = mock_config

    return mock_api


@pytest.fixture
def client():
    """Create a client instance for testing."""
    from otg_mcp.config import Config
    mock_config = Config()
    return OtgClient(config=mock_config)


@pytest.mark.asyncio
async def test_set_config_returns_applied_config(client, mock_api):
    """Test that set_config returns the applied configuration."""
    # Mock the _get_api_client method to return our mock API
    client._get_api_client = MagicMock(return_value=mock_api)

    # Call set_config
    test_config = {
        "ports": [{"name": "port1", "location": "localhost:5555"}],
        "flows": [{"name": "flow1", "tx_rx": {"port": ["port1", "port1"]}}],
    }
    response = await client.set_config(config=test_config, target="localhost")

    # Verify the API interactions
    mock_api.set_config.assert_called_once()  # Was set_config called?
    mock_api.get_config.assert_called_once()  # Was get_config called after set_config?

    # Verify the response structure
    assert isinstance(response, ConfigResponse)
    assert response.status == "success"
    assert response.config is not None

    # Verify the returned config matches what was serialized
    expected_config = {
        "ports": [{"name": "port1", "location": "localhost:5555"}],
        "flows": [{"name": "flow1", "tx_rx": {"port": ["port1", "port1"]}}],
    }
    assert response.config == expected_config


@pytest.mark.asyncio
async def test_set_config_error_handling(client, mock_api):
    """Test that set_config properly handles errors."""
    # Mock the _get_api_client method to return our mock API
    client._get_api_client = MagicMock(return_value=mock_api)

    # Configure mock to raise an exception on set_config
    mock_api.set_config.side_effect = Exception("Test error")

    # Call set_config
    test_config = {"ports": [{"name": "port1", "location": "localhost:5555"}]}
    response = await client.set_config(config=test_config, target="localhost")

    # Verify the response includes the error
    assert response.status == "error"
    assert "error" in response.config
    assert "Test error" in response.config["error"]

    # Verify that get_config was not called after the error
    mock_api.get_config.assert_not_called()


@pytest.mark.asyncio
async def test_set_config_serialization_error(client, mock_api):
    """Test that set_config handles serialization errors."""
    # Mock the _get_api_client method to return our mock API
    client._get_api_client = MagicMock(return_value=mock_api)

    # Configure mock config to raise an exception on serialize
    mock_config = MagicMock()
    mock_config.serialize.side_effect = Exception("Serialization error")
    mock_config.DICT = "dict"
    mock_api.get_config.return_value = mock_config

    # Call set_config
    test_config = {"ports": [{"name": "port1", "location": "localhost:5555"}]}
    response = await client.set_config(config=test_config, target="localhost")

    # Verify the API interactions
    mock_api.set_config.assert_called_once()  # Was set_config called?
    mock_api.get_config.assert_called_once()  # Was get_config called after set_config?

    # Verify the response status and error message
    assert response.status == "error"
    assert "error" in response.config
    assert "Serialization error" in response.config["error"]
