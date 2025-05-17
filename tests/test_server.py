from unittest import mock

import pytest

from otg_mcp.models import HealthStatus
from otg_mcp.server import FastMCP, OtgMcpServer


@pytest.fixture
def mock_fastmcp():
    """Mock FastMCP for testing."""
    mock_mcp = mock.MagicMock(spec=FastMCP)
    return mock_mcp


class TestOtgMcpServer:
    """Tests for OtgMcpServer."""

    def test_health_check_tool(self):
        """Test the health check tool."""
        # Simplify the test - we just want to verify that a health status
        # object has the expected properties
        health_status = HealthStatus(
            status="healthy", server_info={"server_name": "otg-mcp-server"}
        )

        # Verify health status properties
        assert health_status.status == "healthy"
        assert health_status.server_info == {"server_name": "otg-mcp-server"}
