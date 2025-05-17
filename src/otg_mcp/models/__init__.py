"""OTG MCP models package."""

from .router_models import (
    ApiResponse,
    CaptureResponse,
    ConfigResponse,
    ControlResponse,
    HealthStatus,
    MetricsResponse,
    SnappiError,
)
from .server_models import (
    PortInfo,
    TrafficGeneratorInfo,
    TrafficGeneratorStatus,
    CapabilitiesVersionResponse,
)

__all__ = [
    "ApiResponse",
    "ConfigResponse",
    "MetricsResponse",
    "CaptureResponse",
    "ControlResponse",
    "TrafficGeneratorStatus",
    "TrafficGeneratorInfo",
    "PortInfo",
    "HealthStatus",
    "SnappiError",
    "CapabilitiesVersionResponse",
]
