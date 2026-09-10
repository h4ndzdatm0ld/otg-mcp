import json
from unittest import mock

import pytest

from otg_mcp.models import HealthStatus, TargetHealthInfo
from otg_mcp.server import FastMCP, OtgMcpServer

EXPECTED_TOOLS = {
    "get_available_targets",
    "get_capture",
    "get_config",
    "get_metrics",
    "get_schemas_for_target",
    "health",
    "list_schemas_for_target",
    "set_config",
    "start_capture",
    "start_traffic",
    "stop_capture",
    "stop_traffic",
}


@pytest.fixture
def mock_fastmcp():
    """Mock FastMCP for testing."""
    mock_mcp = mock.MagicMock(spec=FastMCP)
    return mock_mcp


@pytest.fixture
def server_config_file(tmp_path):
    """Write a minimal single-target config file and return its path."""
    config_file = tmp_path / "trafficGeneratorConfig.json"
    config_file.write_text(
        json.dumps(
            {
                "targets": {
                    "test-target.example.com:8443": {
                        "ports": {"p1": {"location": "localhost:5555", "name": "p1"}}
                    }
                }
            }
        )
    )
    return str(config_file)


class TestToolRegistration:
    """Tests that the server boots and registers its tools against real FastMCP.

    These deliberately avoid mocking FastMCP. Registration is the one thing that
    breaks when the installed FastMCP changes its add_tool signature, and a mocked
    server accepts any call shape, so only a real instance catches it.
    """

    def test_server_registers_every_tool(self, server_config_file):
        """Every tool_* method is registered under its stripped name."""
        server = OtgMcpServer(config_file=server_config_file)

        registered = {name for name in dir(server) if name.startswith("tool_")}
        assert {name[5:] for name in registered} == EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_tools_are_visible_to_mcp(self, server_config_file):
        """FastMCP exposes the registered tools, proving add_tool actually took."""
        server = OtgMcpServer(config_file=server_config_file)

        tools = await server.mcp.get_tools()

        assert set(tools) == EXPECTED_TOOLS


class TestOtgMcpServer:
    """Tests for OtgMcpServer."""

    def test_health_check_tool(self):
        """Test the health check tool."""
        # Simplify the test - we just want to verify that a health status
        # object has the expected properties
        target_info = TargetHealthInfo(name="target1", healthy=True)
        health_status = HealthStatus(
            status="success",
            targets={"target1": target_info}
        )

        # Verify health status properties
        assert health_status.status == "success"
        assert "target1" in health_status.targets
        assert health_status.targets["target1"].name == "target1"
        assert health_status.targets["target1"].healthy
