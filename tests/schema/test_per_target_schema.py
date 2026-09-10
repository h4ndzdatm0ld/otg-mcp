"""
Tests for per-target schema resolution.

Each target serves the OpenAPI document it actually implements at
/docs/openapi.json. The client fetches that once per target and reuses it for the
life of the process, so two targets on different software versions never share a
schema. A target that serves no document is an error: there are no local schemas.
"""

from unittest.mock import AsyncMock

import pytest

from otg_mcp.client import OtgClient
from otg_mcp.config import Config, TargetConfig

TARGET_A = "gen-a.example.com:8443"
TARGET_B = "gen-b.example.com:8443"


def spec(version, schema_names):
    """Build a minimal OpenAPI document."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Open Traffic Generator API", "version": version},
        "components": {
            "schemas": {
                name: {"description": f"{name} at {version}"} for name in schema_names
            }
        },
    }


@pytest.fixture
def client():
    """A client with two configured targets and no local schemas."""
    config = Config()
    config.targets.targets[TARGET_A] = TargetConfig()
    config.targets.targets[TARGET_B] = TargetConfig()
    return OtgClient(config=config)


class TestPerTargetSchema:
    """Resolution, caching and isolation of per-target schemas."""

    @pytest.mark.asyncio
    async def test_schema_comes_from_the_target(self, client):
        """A served document is used in preference to the bundled schemas."""
        client._fetch_remote_schema = AsyncMock(return_value=spec("1.20.0", ["Flow"]))

        result = await client._get_schema_for_target(TARGET_A)

        assert result["info"]["version"] == "1.20.0"
        assert TARGET_A in client.target_schemas

    @pytest.mark.asyncio
    async def test_unknown_target_rejected_before_remote_fetch(self, client):
        """An unconfigured target is rejected without making a network request."""
        client._fetch_remote_schema = AsyncMock(return_value=spec("1.61.0", ["Flow"]))

        with pytest.raises(
            ValueError, match="Target unconfigured.example.com:8443 not found"
        ):
            await client._get_schema_for_target("unconfigured.example.com:8443")

        client._fetch_remote_schema.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetched_once_then_cached(self, client):
        """Repeated calls reuse the cached document for the life of the process."""
        fetch = AsyncMock(return_value=spec("1.20.0", ["Flow"]))
        client._fetch_remote_schema = fetch

        for _ in range(3):
            await client._get_schema_for_target(TARGET_A)

        fetch.assert_awaited_once_with(TARGET_A)

    @pytest.mark.asyncio
    async def test_targets_are_isolated(self, client):
        """Two targets keep separate schemas, even on different versions."""

        async def per_target(target):
            if target == TARGET_A:
                return spec("1.20.0", ["Flow"])
            return spec("1.61.0", ["Flow", "Device.Macsec"])

        client._fetch_remote_schema = AsyncMock(side_effect=per_target)

        schema_a = await client._get_schema_for_target(TARGET_A)
        schema_b = await client._get_schema_for_target(TARGET_B)

        assert schema_a["info"]["version"] == "1.20.0"
        assert schema_b["info"]["version"] == "1.61.0"
        assert "Device.Macsec" not in schema_a["components"]["schemas"]
        assert "Device.Macsec" in schema_b["components"]["schemas"]

    @pytest.mark.asyncio
    async def test_listing_is_isolated_per_target(self, client):
        """list_schemas_for_target reflects each target's own document."""

        async def per_target(target):
            if target == TARGET_A:
                return spec("1.20.0", ["Flow"])
            return spec("1.61.0", ["Flow", "Device.Macsec"])

        client._fetch_remote_schema = AsyncMock(side_effect=per_target)

        assert await client.list_schemas_for_target(TARGET_A) == ["Flow"]
        assert sorted(await client.list_schemas_for_target(TARGET_B)) == [
            "Device.Macsec",
            "Flow",
        ]

    @pytest.mark.asyncio
    async def test_target_without_a_schema_is_an_error(self, client):
        """A target that serves no document fails loudly instead of guessing.

        There are no bundled schemas to fall back to, so silently substituting
        another version is not an option. Callers get a message naming the
        endpoint that was tried.
        """
        client._fetch_remote_schema = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="did not serve a schema"):
            await client._get_schema_for_target(TARGET_A)

        assert TARGET_A not in client.target_schemas

    @pytest.mark.asyncio
    async def test_failure_is_not_cached(self, client):
        """A target that recovers is picked up on the next call."""
        fetch = AsyncMock(side_effect=[None, spec("1.61.0", ["Flow"])])
        client._fetch_remote_schema = fetch

        with pytest.raises(ValueError):
            await client._get_schema_for_target(TARGET_A)

        schema = await client._get_schema_for_target(TARGET_A)
        assert schema["info"]["version"] == "1.61.0"


class TestRemoteSchemaFetch:
    """Behaviour of the HTTP fetch itself."""

    @pytest.mark.asyncio
    async def test_non_200_returns_none(self, client, monkeypatch):
        """A target without the endpoint yields None rather than raising."""
        monkeypatch.setattr(
            "otg_mcp.client.aiohttp.ClientSession", _session_returning(404, {})
        )

        assert await client._fetch_remote_schema(TARGET_A) is None

    @pytest.mark.asyncio
    async def test_document_without_components_rejected(self, client, monkeypatch):
        """A 200 response that is not an OpenAPI document is rejected."""
        monkeypatch.setattr(
            "otg_mcp.client.aiohttp.ClientSession",
            _session_returning(200, {"not": "a spec"}),
        )

        assert await client._fetch_remote_schema(TARGET_A) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "components",
        [None, [], "invalid", {"schemas": None}, {"schemas": []}],
        ids=[
            "null-components",
            "list-components",
            "string-components",
            "null-schemas",
            "list-schemas",
        ],
    )
    async def test_malformed_components_rejected(self, client, monkeypatch, components):
        """Malformed nested component values yield None for bundled fallback."""
        monkeypatch.setattr(
            "otg_mcp.client.aiohttp.ClientSession",
            _session_returning(200, {"components": components}),
        )

        assert await client._fetch_remote_schema(TARGET_A) is None

    @pytest.mark.asyncio
    async def test_valid_document_returned(self, client, monkeypatch):
        """A well formed document is returned as parsed JSON."""
        served = spec("1.61.0", ["Flow"])
        monkeypatch.setattr(
            "otg_mcp.client.aiohttp.ClientSession", _session_returning(200, served)
        )

        assert await client._fetch_remote_schema(TARGET_A) == served

    @pytest.mark.asyncio
    async def test_transport_error_returns_none(self, client, monkeypatch):
        """A connection failure yields None so the caller can fall back."""

        class Boom:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                raise OSError("connection refused")

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr("otg_mcp.client.aiohttp.ClientSession", Boom)

        assert await client._fetch_remote_schema(TARGET_A) is None


def _session_returning(status, payload):
    """Build a fake aiohttp.ClientSession yielding one response."""

    class FakeResponse:
        def __init__(self):
            self.status = status

        async def json(self, content_type=None):
            return payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeSession:
        def __init__(self, *a, **kw):
            pass

        def get(self, url, ssl=None):
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    return FakeSession
