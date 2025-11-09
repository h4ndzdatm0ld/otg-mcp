"""
Test for handling configurations without targets defined.
"""

import json
import logging
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from otg_mcp.client import OtgClient
from otg_mcp.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def config_file_with_no_targets():
    """Create a temporary config file with no targets section."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        config_data = {
            "schemas": {
                "schema_path": "/path/to/schemas"
            }
            # Note: No 'targets' section
        }
        json.dump(config_data, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def config_file_with_empty_targets():
    """Create a temporary config file with empty targets section."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        config_data = {
            "targets": {}
        }
        json.dump(config_data, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_config_loads_without_targets_section(config_file_with_no_targets):
    """Test that config can be loaded without a targets section."""
    # This should not raise an error
    config = Config(config_file_with_no_targets)
    
    # Verify that targets is initialized as empty
    assert config.targets.targets == {}
    logger.info("Config successfully loaded without targets section")


def test_config_loads_with_empty_targets(config_file_with_empty_targets):
    """Test that config can be loaded with an empty targets section."""
    config = Config(config_file_with_empty_targets)
    
    # Verify that targets is empty
    assert config.targets.targets == {}
    logger.info("Config successfully loaded with empty targets section")


@pytest.mark.asyncio
async def test_get_available_targets_with_no_targets():
    """Test that get_available_targets returns helpful info when no targets configured."""
    # Create a config with no targets
    mock_config = Config()
    mock_config.targets.targets = {}
    
    client = OtgClient(config=mock_config)
    
    # Call get_available_targets
    result = await client.get_available_targets()
    
    # Verify the response structure
    assert "_info" in result
    assert result["_info"]["status"] == "no_targets_configured"
    assert "message" in result["_info"]
    assert "suggestions" in result["_info"]
    assert "future_enhancements" in result["_info"]
    
    # Verify suggestions mention configuration
    suggestions = result["_info"]["suggestions"]
    assert any("configuration file" in s.lower() for s in suggestions)
    
    # Verify future enhancements mention plugin architecture
    enhancements = result["_info"]["future_enhancements"]
    assert any("plugin" in e.lower() for e in enhancements)
    assert any("netbox" in e.lower() for e in enhancements)
    
    logger.info("get_available_targets correctly returns info when no targets configured")


@pytest.mark.asyncio
async def test_get_available_targets_with_targets_configured():
    """Test that get_available_targets works normally when targets are configured."""
    # Create a config with targets
    mock_config = Config()
    from otg_mcp.config import TargetConfig, PortConfig
    
    mock_config.targets.targets = {
        "test-host:8443": TargetConfig(
            ports={
                "p1": PortConfig(location="localhost:5555", name="p1")
            }
        )
    }
    
    client = OtgClient(config=mock_config)
    
    # Mock the _get_api_client to avoid actual connections
    client._get_api_client = MagicMock()
    client.get_target_version = MagicMock()
    
    # Call get_available_targets
    result = await client.get_available_targets()
    
    # Verify that we don't get the _info key since targets are configured
    assert "_info" not in result
    
    # Verify we get the target in the result
    assert "test-host:8443" in result
    
    logger.info("get_available_targets works normally with configured targets")
