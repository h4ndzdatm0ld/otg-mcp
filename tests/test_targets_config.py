"""
Unit tests for the target configuration functionality.
"""

from unittest import mock

import pytest

from otg_mcp.config import PortConfig, TargetConfig, config


class TestTargetConfig:
    """Tests for target configuration models."""

    def test_port_config_model(self):
        """Test PortConfig Pydantic model."""
        # Create a port config
        port = PortConfig(interface="eth0", location="eth0", name="eth0")

        # Test properties
        assert port.interface == "eth0"
        assert port.location == "eth0"
        assert port.name == "eth0"

        # Test serialization
        data = port.model_dump()
        assert data["interface"] == "eth0"
        assert data["location"] == "eth0"
        assert data["name"] == "eth0"

        # Test deserialization
        port2 = PortConfig.model_validate(
            {"interface": "eth1", "location": "eth1", "name": "eth1"}
        )
        assert port2.interface == "eth1"
        assert port2.location == "eth1"
        assert port2.name == "eth1"

    def test_target_config_model(self):
        """Test TargetConfig Pydantic model."""
        # Create a target config with ports
        target = TargetConfig(
            ports={
                "p1": PortConfig(interface="eth0", location="eth0", name="p1"),
                "p2": PortConfig(interface="eth1", location="eth1", name="p2"),
            }
        )

        # Test properties
        assert len(target.ports) == 2
        assert target.ports["p1"].interface == "eth0"
        assert target.ports["p1"].location == "eth0"
        assert target.ports["p1"].name == "p1"
        assert target.ports["p2"].interface == "eth1"
        assert target.ports["p2"].location == "eth1"
        assert target.ports["p2"].name == "p2"

        # Test serialization
        data = target.model_dump()
        assert data["ports"]["p1"]["interface"] == "eth0"
        assert data["ports"]["p1"]["location"] == "eth0"
        assert data["ports"]["p1"]["name"] == "p1"
        assert data["ports"]["p2"]["interface"] == "eth1"
        assert data["ports"]["p2"]["location"] == "eth1"
        assert data["ports"]["p2"]["name"] == "p2"

        # Test deserialization from dict
        target_dict = {
            "ports": {
                "p1": {"interface": "enp0s31f6", "location": "enp0s31f6", "name": "p1"},
                "p2": {
                    "interface": "enp0s31f6.1",
                    "location": "enp0s31f6.1",
                    "name": "p2",
                },
            }
        }
        target2 = TargetConfig.model_validate(target_dict)
        assert target2.ports["p1"].interface == "enp0s31f6"
        assert target2.ports["p1"].location == "enp0s31f6"
        assert target2.ports["p1"].name == "p1"
        assert target2.ports["p2"].interface == "enp0s31f6.1"
        assert target2.ports["p2"].location == "enp0s31f6.1"
        assert target2.ports["p2"].name == "p2"

    def test_example_target_config(self, example_target_config):
        """Test that example_target_config fixture works correctly."""
        # Verify the fixture created a valid target
        assert "test-target.example.com:8443" in example_target_config.targets
        target = example_target_config.targets["test-target.example.com:8443"]

        # Verify the target has the expected ports
        assert "p1" in target.ports
        assert "p2" in target.ports
        assert target.ports["p1"].interface == "enp0s31f6"
        assert target.ports["p2"].interface == "enp0s31f6.1"


@pytest.mark.asyncio
class TestAvailableTargets:
    """Tests for get_available_targets functionality."""

    async def test_get_available_targets_empty(self, router):
        """Test getting available targets with empty config."""
        # Clear any existing targets
        config.targets.targets = {}

        # Mock the _get_api_client method to avoid actual network calls
        router._get_api_client = mock.MagicMock()

        # Call the method
        result = await router.get_available_targets()

        # Verify the result
        assert result is not None
        assert len(result) == 0

    async def test_get_available_targets_with_targets(
        self, router, example_target_config
    ):
        """Test getting available targets with configured targets."""
        # Mock the _get_api_client method to avoid actual network calls
        router._get_api_client = mock.MagicMock()

        # Call the method
        result = await router.get_available_targets()

        # Verify the result
        assert result is not None
        assert len(result) == 1
        assert "test-target.example.com:8443" in result

        target = result["test-target.example.com:8443"]
        assert "apiVersion" in target
        assert "ports" in target
        assert (
            target["available"] is True
        )  # Because we mocked _get_api_client to succeed
        assert len(target["ports"]) == 2

        # Verify ports
        assert "p1" in target["ports"]
        assert "p2" in target["ports"]
        assert target["ports"]["p1"]["name"] == "p1"
        assert target["ports"]["p1"]["location"] == "enp0s31f6"
        assert target["ports"]["p2"]["name"] == "p2"
        assert target["ports"]["p2"]["location"] == "enp0s31f6.1"

    async def test_get_available_targets_connection_failure(
        self, router, example_target_config
    ):
        """Test getting available targets when connection fails."""
        # Mock the _get_api_client method to simulate connection failure
        router._get_api_client = mock.MagicMock(
            side_effect=Exception("Connection failed")
        )

        # Call the method
        result = await router.get_available_targets()

        # Verify the result - we should still get a target but with available=False
        assert result is not None
        assert len(result) == 1
        assert "test-target.example.com:8443" in result

        target = result["test-target.example.com:8443"]
        assert target["available"] is False
        assert "error" in target

    # Removed test_refresh_targets as the refresh parameter has been removed from get_available_targets
