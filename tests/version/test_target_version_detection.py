"""
Tests for reporting a target's API version.

The version is whatever the target reports at /capabilities/version. Nothing is
matched against local schema files any more, so the reported value is passed
through untouched and failures surface as "unknown" rather than being replaced
with the version of some bundled schema.
"""

from unittest.mock import AsyncMock

import pytest

from otg_mcp.client import OtgClient
from otg_mcp.config import Config
from otg_mcp.models import CapabilitiesVersionResponse


@pytest.fixture
def client():
    """Create a client with no local schemas."""
    return OtgClient(config=Config())


def _available_target():
    """A minimal get_available_targets payload for one target."""
    return {
        "test-target": {
            "ports": {"p1": {"location": "localhost:5555", "name": "p1"}},
            "available": True,
        }
    }


@pytest.mark.asyncio
async def test_reports_the_version_the_target_reports(client):
    """The target's own version is passed through verbatim."""
    client.get_available_targets = AsyncMock(return_value=_available_target())
    client.get_target_version = AsyncMock(
        return_value=CapabilitiesVersionResponse(
            api_spec_version="1.*", sdk_version="1.61.1", app_version="1.61.0-9"
        )
    )

    config = await client._get_target_config("test-target")

    assert config is not None
    assert config["apiVersion"] == "1.61.1"


@pytest.mark.asyncio
async def test_unusual_version_is_not_rewritten(client):
    """A version with no matching local schema is still reported as-is.

    Previously this was silently replaced with the closest bundled schema
    version, which misreported what the target was actually running.
    """
    client.get_available_targets = AsyncMock(return_value=_available_target())
    client.get_target_version = AsyncMock(
        return_value=CapabilitiesVersionResponse(
            api_spec_version="1.*", sdk_version="1.28.2", app_version="1.28.0-33"
        )
    )

    config = await client._get_target_config("test-target")

    assert config is not None
    assert config["apiVersion"] == "1.28.2"


@pytest.mark.asyncio
async def test_version_failure_reports_unknown(client):
    """A failed version probe reports "unknown" instead of inventing a version."""
    client.get_available_targets = AsyncMock(return_value=_available_target())
    client.get_target_version = AsyncMock(side_effect=Exception("Connection failed"))

    config = await client._get_target_config("test-target")

    assert config is not None
    assert config["apiVersion"] == "unknown"


@pytest.mark.asyncio
async def test_missing_target_returns_none(client):
    """An unknown target resolves to None."""
    client.get_available_targets = AsyncMock(return_value={})

    assert await client._get_target_config("nope") is None


def test_client_has_no_schema_registry(client):
    """The client no longer carries a local schema registry."""
    assert not hasattr(client, "schema_registry")
    assert isinstance(client.target_schemas, dict)
