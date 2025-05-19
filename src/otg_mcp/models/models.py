"""Unified models for OTG MCP."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """Base response model for API responses."""

    status: str = Field(default="success", description="Status of the response")


class ConfigResponse(ApiResponse):
    """Response model for configuration operations."""

    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Configuration data"
    )


class MetricsResponse(ApiResponse):
    """Response model for metrics operations."""

    metrics: Optional[Dict[str, Any]] = Field(default=None, description="Metrics data")


class CaptureResponse(ApiResponse):
    """Response model for capture operations."""

    port: str = Field(..., description="Name of the port used for capture")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Capture data")
    capture_id: Optional[str] = None
    file_path: Optional[str] = Field(
        default=None, description="Path to the saved capture file (.pcap)"
    )


class ControlResponse(ApiResponse):
    """Response model for control responses."""

    action: str = Field(..., description="Action that was performed")
    verified: Optional[bool] = Field(
        default=None, description="Whether the action was verified"
    )
    timestamp: datetime = Field(default_factory=datetime.now)
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Result details of the control operation"
    )


class PortInfo(BaseModel):
    """Information about a port on a traffic generator."""

    name: str = Field(..., description="Name of the port")
    location: str = Field(..., description="Location of the port (hostname:port)")
    interface: Optional[str] = Field(
        None, description="Interface name (backward compatibility)"
    )

    @property
    def interface_name(self) -> str:
        """Get the interface name, falling back to location if not set."""
        return self.interface or self.location


class CapabilitiesVersionResponse(BaseModel):
    """Response from the capabilities/version endpoint."""

    api_spec_version: str
    sdk_version: str
    app_version: str


class TrafficGeneratorInfo(BaseModel):
    """Information about a traffic generator."""

    hostname: str = Field(..., description="Hostname of the traffic generator")
    ports: Dict[str, PortInfo] = Field(
        default_factory=dict, description="Ports available on this generator"
    )
    available: bool = Field(
        default=True, description="Whether the generator is available"
    )


class TrafficGeneratorStatus(ApiResponse):
    """Status of all traffic generators."""

    generators: Dict[str, TrafficGeneratorInfo] = Field(
        default_factory=dict, description="All available traffic generators"
    )


class TargetHealthInfo(BaseModel):
    """Health information for a traffic generator target."""

    name: str = Field(..., description="Name of the target")
    healthy: bool = Field(..., description="Whether the target is healthy")
    version_info: Optional[CapabilitiesVersionResponse] = Field(
        None, description="Version information when available"
    )
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthStatus(BaseModel):
    """Health status collection of all traffic generators."""

    status: str = Field(default="success", description="Status of the response")
    targets: Dict[str, TargetHealthInfo] = Field(
        default_factory=dict, description="Health status of individual targets"
    )


class SnappiError(BaseModel):
    """Error model for snappi errors."""

    error: str
    detail: Optional[str] = None
    code: Optional[int] = None
