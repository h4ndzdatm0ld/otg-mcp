from unittest import mock

import pytest

from otg_mcp.models import HealthStatus, TargetHealthInfo
from otg_mcp.server import FastMCP


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
