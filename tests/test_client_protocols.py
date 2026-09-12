"""Tests for generic protocol metrics."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import snappi

from otg_mcp.client import OtgClient
from otg_mcp.config import Config, TargetConfig

TARGET = "gen-a.example.com:8443"


def make_client():
    """Build a client with one configured target."""
    config = Config()
    config.targets.targets.clear()
    config.targets.targets[TARGET] = TargetConfig()
    return OtgClient(config=config)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("protocol", "name_field", "metric_choice"),
    [
        ("bgpv4", "peer_names", "bgpv4_metrics"),
        ("bgpv6", "peer_names", "bgpv6_metrics"),
        ("lacp", "lag_member_port_names", "lacp_metrics"),
        ("ospfv2", "router_names", "ospfv2_metrics"),
        ("ospfv3", "router_names", "ospfv3_metrics"),
    ],
)
async def test_protocol_metrics_selects_type_and_names(
    protocol, name_field, metric_choice
):
    """BGP and OSPF requests select their type and protocol-specific filter."""
    client = make_client()
    metrics_filter = SimpleNamespace(**{name_field: None})
    request = SimpleNamespace(choice=None, **{protocol: metrics_filter})
    response = MagicMock()
    response.DICT = "dict"
    response.serialize.return_value = {
        "choice": metric_choice,
        metric_choice: [],
    }
    api = MagicMock()
    api.metrics_request.return_value = request
    api.get_metrics.return_value = response

    with patch.object(client, "_get_api_client", return_value=api):
        result = await client.get_protocol_metrics(
            TARGET, protocol=protocol, names=["protocol-instance"]
        )

    assert result.status == "success"
    assert request.choice == protocol
    assert getattr(metrics_filter, name_field) == ["protocol-instance"]
    assert result.metrics["choice"] == metric_choice


@pytest.mark.asyncio
async def test_unknown_protocol_metrics_returns_error():
    """Unsupported metric types return the MCP error response contract."""
    client = make_client()

    result = await client.get_protocol_metrics(TARGET, protocol="unknown")

    assert result.status == "error"
    assert "Protocol metrics must be one of" in result.metrics["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("protocol", "metric_choice"),
    [
        ("bgpv4", "bgpv4_metrics"),
        ("lacp", "lacp_metrics"),
        ("ospfv2", "ospfv2_metrics"),
        ("ospfv3", "ospfv3_metrics"),
    ],
)
async def test_real_snappi_serializes_protocol_metric_requests(
    protocol, metric_choice
):
    """The installed SDK accepts BGP and OSPF choices with router filters."""
    client = make_client()
    snappi_api = snappi.api(location="https://127.0.0.1:1", verify=False)
    request = snappi_api.metrics_request()
    response = MagicMock()
    response.DICT = "dict"
    response.serialize.return_value = {"choice": metric_choice, metric_choice: []}
    api = MagicMock()
    api.metrics_request.return_value = request
    api.get_metrics.return_value = response

    with patch.object(client, "_get_api_client", return_value=api):
        result = await client.get_protocol_metrics(
            TARGET, protocol=protocol, names=["protocol-instance"]
        )

    serialized = request.serialize(encoding=request.DICT)
    name_fields = {
        "bgpv4": "peer_names",
        "lacp": "lag_member_port_names",
        "ospfv2": "router_names",
        "ospfv3": "router_names",
    }
    assert serialized["choice"] == protocol
    assert serialized[protocol][name_fields[protocol]] == ["protocol-instance"]
    assert result.status == "success"
