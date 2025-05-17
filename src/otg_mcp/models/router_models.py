"""Models for OTG router and API responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """Generic API response model."""

    status: str = "success"
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ConfigResponse(BaseModel):
    """Response model for configuration operations."""

    status: str = "success"
    config: Dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    """Response model for metrics operations."""

    status: str = "success"
    metrics: Dict[str, Any] = Field(default_factory=dict)


class CaptureResponse(BaseModel):
    """Response model for capture operations."""

    status: str = "success"
    port: Optional[str] = None
    capture_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ControlResponse(BaseModel):
    """Response model for traffic control operations."""

    status: str = "success"
    action: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class TrafficGeneratorStatus(BaseModel):
    """Status information for all traffic generators."""

    traffic_generators: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: float = Field(default_factory=datetime.now().timestamp)

    @classmethod
    def create_error_status(cls, error: str) -> "TrafficGeneratorStatus":
        """Create a status with an error.

        Args:
            error: Error message

        Returns:
            TrafficGeneratorStatus with the error
        """
        return cls(
            traffic_generators=[], error=error, timestamp=datetime.now().timestamp()
        )


class HealthStatus(BaseModel):
    """
    Health status of the target host.

    This model represents the health status of a target host and port,
    indicating whether it's reachable over HTTP/HTTPS.

    Attributes:
        status: Overall health status ("healthy", "degraded", or "unhealthy")
        server_info: Information about the MCP server
        connection_info: List of connection status details for checked hosts
        last_error: Optional error message if any
    """

    status: str  # Status values can be "healthy", "degraded", or "unhealthy"
    server_info: Dict[str, Any] = Field(default_factory=dict)
    connection_info: List[Dict[str, Any]] = Field(default_factory=list)
    last_error: Optional[str] = None

    @classmethod
    def create_unhealthy(cls, error: str) -> "HealthStatus":
        """Create an unhealthy status.

        Args:
            error: The error message

        Returns:
            HealthStatus: An unhealthy status with the error
        """
        return cls(
            status="unhealthy",
            last_error=error,
            server_info={"error_time": datetime.now().timestamp()},
            connection_info=[],
        )


class SnappiError(BaseModel):
    """Error model for snappi errors."""

    error: str
    detail: Optional[str] = None
    code: Optional[int] = None
