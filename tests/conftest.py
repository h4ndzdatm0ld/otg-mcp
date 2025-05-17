"""
Shared fixtures for tests.
"""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml

# Add src to path so tests can import modules properly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from otg_mcp.client import OtgClient
from otg_mcp.config import DirectConnectionInfo, PortConfig, TargetConfig, config


@pytest.fixture
def api_schema():
    """
    Load the test API schema from fixtures directory.

    Returns:
        dict: The parsed OpenAPI schema
    """
    schema_path = os.path.join(os.path.dirname(__file__), "fixtures", "apiSchema.yml")
    with open(schema_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def mock_schema_registry(api_schema, monkeypatch):
    """
    Create a mock schema registry that uses the test apiSchema.yml.

    Args:
        api_schema: The API schema fixture
        monkeypatch: PyTest monkeypatch fixture

    Returns:
        Mock schema registry that returns the test schema
    """
    from otg_mcp.schema_registry import SchemaRegistry

    # Create a class that inherits from the original but overrides key methods
    class TestSchemaRegistry(SchemaRegistry):
        def __init__(self):
            super().__init__()
            self.schemas = {"1_30_0": api_schema}

        def get_available_schemas(self):
            return ["1_30_0"]

        def schema_exists(self, version):
            return self._normalize_version(version) == "1_30_0"

    # Create an instance of our test registry
    test_registry = TestSchemaRegistry()

    # Patch the get_schema_registry function to return our test registry
    from otg_mcp import schema_registry
    monkeypatch.setattr(schema_registry, "get_schema_registry", lambda: test_registry)

    return test_registry


@pytest.fixture
def mock_api_wrapper():
    """Mock OtgApiWrapper for testing."""
    mock_wrapper = mock.MagicMock()
    # Set up necessary mock methods
    mock_config = mock.MagicMock()
    mock_wrapper.get_config.return_value = mock_config
    mock_config.serialize.return_value = {"ports": [], "flows": []}

    # Add metrics_request method
    mock_metrics_request = mock.MagicMock()
    mock_wrapper.metrics_request = mock.MagicMock(return_value=mock_metrics_request)

    mock_metrics = mock.MagicMock()
    mock_metrics.serialize.return_value = {"port_metrics": [], "flow_metrics": []}
    mock_wrapper.get_metrics = mock.MagicMock(return_value=mock_metrics)

    # Set up start_traffic and stop_traffic methods
    mock_wrapper.start_traffic = mock.MagicMock()
    mock_wrapper.stop_traffic = mock.MagicMock(return_value=True)

    # Set up capture methods
    mock_wrapper.start_capture = mock.MagicMock()
    mock_capture_response = mock.MagicMock()
    mock_capture_response.serialize.return_value = {"status": "stopped", "data": {}}
    mock_wrapper.stop_capture = mock.MagicMock(return_value=mock_capture_response)

    return mock_wrapper


@pytest.fixture
def router():
    """Create a test router."""
    return OtgClient(config=config)


@pytest.fixture
def direct_connection():
    """Create a test direct connection."""
    return DirectConnectionInfo(
        hostname="test-host.example.com",
        name="test-host",
        instance_id="test-host.example.com",
    )


@pytest.fixture
def example_target_config():
    """Create example target configuration."""
    # Clear any existing targets
    config.targets.targets = {}

    # Add example target
    config.targets.targets["test-target.example.com:8443"] = TargetConfig(
        ports={
            "p1": PortConfig(interface="enp0s31f6", location="enp0s31f6", name="p1"),
            "p2": PortConfig(
                interface="enp0s31f6.1", location="enp0s31f6.1", name="p2"
            ),
        }
    )

    # Return the config for use in tests
    return config.targets


# Define custom marker for integration tests
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as requiring integration with real traffic generators",
    )


# Skip integration tests unless environment variable is set
def pytest_runtest_setup(item):
    """Skip integration tests unless enabled via environment variable."""
    if "integration" in item.keywords and not os.environ.get("RUN_INTEGRATION_TESTS"):
        pytest.skip("Integration test skipped. Set RUN_INTEGRATION_TESTS=1 to run")
