"""
Shared fixtures for tests.
"""

import os
import sys
from pathlib import Path

import pytest
import yaml

# Add src to path so tests can import modules properly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from otg_mcp.client import OtgClient
from otg_mcp.config import Config, PortConfig, TargetConfig


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
def test_config():
    """Create a test configuration instance."""
    return Config()


@pytest.fixture
def router(test_config):
    """Create a test router."""
    return OtgClient(config=test_config)


@pytest.fixture
def example_target_config(test_config):
    """Create example target configuration."""
    # Add example target
    test_config.targets.targets["test-target.example.com:8443"] = TargetConfig(
        ports={
            "p1": PortConfig(interface="enp0s31f6", location="enp0s31f6", name="p1"),
            "p2": PortConfig(
                interface="enp0s31f6.1", location="enp0s31f6.1", name="p2"
            ),
        }
    )

    # Return the config for use in tests
    return test_config.targets


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
