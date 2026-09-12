"""
Tests for the schema tools OtgClient exposes on top of a target's own OpenAPI
document.

There are no bundled schema files: every document comes from the target that
serves it, is cached per target, and a target that serves nothing usable is an
error naming the endpoint that was tried. All fetches here are stubbed, so no
test performs a network request.
"""

from unittest.mock import AsyncMock

import pytest

from otg_mcp.client import REMOTE_SCHEMA_PATH, OtgClient
from otg_mcp.config import Config, TargetConfig

TARGET_A = "gen-a.example.com:8443"
TARGET_B = "gen-b.example.com:8443"


def document(version, schema_names):
    """Build a minimal OpenAPI document.

    Args:
        version: Value for info.version
        schema_names: Component schema names the document declares

    Returns:
        A parsed-document-shaped dictionary
    """
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
    """Build a client with two configured targets and an empty schema cache.

    Returns:
        An OtgClient whose targets are TARGET_A and TARGET_B
    """
    config = Config()
    config.targets.targets.clear()
    config.targets.targets[TARGET_A] = TargetConfig()
    config.targets.targets[TARGET_B] = TargetConfig()
    return OtgClient(config=config)


class TestGetSchemasForTarget:
    """Component lookup against the document a target served."""

    @pytest.mark.asyncio
    async def test_bare_names_are_qualified(self, client):
        """A bare component name is resolved under components.schemas.

        Callers should not have to know the dotted prefix to ask for "Flow".
        """
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow", "Port"])
        )

        result = await client.get_schemas_for_target(TARGET_A, ["Flow", "Port"])

        assert result["Flow"] == {"description": "Flow at 1.20.0"}
        assert result["Port"] == {"description": "Port at 1.20.0"}

    @pytest.mark.asyncio
    async def test_fully_qualified_names_are_used_as_given(self, client):
        """A dotted path is navigated verbatim and keyed by the path."""
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow"])
        )

        result = await client.get_schemas_for_target(
            TARGET_A, ["components.schemas.Flow"]
        )

        assert result["components.schemas.Flow"] == {"description": "Flow at 1.20.0"}

    @pytest.mark.asyncio
    async def test_a_missing_component_is_reported_per_schema(self, client):
        """One unknown name must not discard the components that did resolve."""
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow"])
        )

        result = await client.get_schemas_for_target(TARGET_A, ["Flow", "Nonexistent"])

        assert result["Flow"] == {"description": "Flow at 1.20.0"}
        assert "Nonexistent" in result["Nonexistent"]["error"]

    @pytest.mark.asyncio
    async def test_an_unconfigured_target_is_rejected(self, client):
        """A target that is not configured is refused before any fetch."""
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow"])
        )

        with pytest.raises(ValueError, match="not found"):
            await client.get_schemas_for_target("unknown.example.com:8443", ["Flow"])

        client._fetch_remote_schema.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_target_serving_nothing_names_the_endpoint(self, client):
        """The error tells the operator exactly which endpoint was tried.

        There is nothing local to substitute, so the message has to be
        actionable.
        """
        client._fetch_remote_schema = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match=REMOTE_SCHEMA_PATH):
            await client.get_schemas_for_target(TARGET_A, ["Flow"])

    @pytest.mark.asyncio
    async def test_the_document_is_fetched_once_across_calls(self, client):
        """Repeated schema tool calls reuse the cached document.

        Refetching would make every schema lookup an HTTP round trip against
        lab gear that may be busy running traffic.
        """
        fetch = AsyncMock(return_value=document("1.20.0", ["Flow", "Port"]))
        client._fetch_remote_schema = fetch

        await client.get_schemas_for_target(TARGET_A, ["Flow"])
        await client.get_schemas_for_target(TARGET_A, ["Port"])
        await client.list_schemas_for_target(TARGET_A)
        await client.get_schema_components_for_target(TARGET_A)

        fetch.assert_awaited_once_with(TARGET_A)

    @pytest.mark.asyncio
    async def test_targets_on_different_versions_stay_independent(self, client):
        """Each target's own document answers that target's lookups.

        Two generators on different software must never see each other's
        components.
        """

        async def per_target(target):
            if target == TARGET_A:
                return document("1.20.0", ["Flow"])
            return document("1.61.0", ["Flow", "Device.Macsec"])

        client._fetch_remote_schema = AsyncMock(side_effect=per_target)

        older = await client.get_schemas_for_target(TARGET_A, ["Device.Macsec"])
        newer = await client.get_schemas_for_target(TARGET_B, ["Device.Macsec"])

        assert "error" in older["Device.Macsec"]
        assert newer["Device.Macsec"] == {"description": "Device.Macsec at 1.61.0"}

    @pytest.mark.asyncio
    async def test_an_unusable_schema_name_collection_is_a_value_error(self, client):
        """A non-iterable schema_names surfaces as ValueError, not TypeError.

        Callers of the schema tools only have to handle ValueError.
        """
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow"])
        )

        with pytest.raises(ValueError, match=f"Error getting schemas for target {TARGET_A}"):
            await client.get_schemas_for_target(TARGET_A, 42)


class TestListSchemasForTarget:
    """Enumeration of the component schema names a target declares."""

    @pytest.mark.asyncio
    async def test_names_come_from_the_served_document(self, client):
        """Listing reflects exactly what the target published."""
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow", "Port", "Capture"])
        )

        assert sorted(await client.list_schemas_for_target(TARGET_A)) == [
            "Capture",
            "Flow",
            "Port",
        ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "served",
        [{"openapi": "3.0.3"}, {"components": {}}, {"components": {"schemas": []}}],
        ids=["no-components", "no-schemas-key", "schemas-not-a-mapping"],
    )
    async def test_a_document_without_component_schemas_lists_nothing(
        self, client, served
    ):
        """A document with no usable components yields an empty list, not a raise."""
        client._fetch_remote_schema = AsyncMock(return_value=served)

        assert await client.list_schemas_for_target(TARGET_A) == []

    @pytest.mark.asyncio
    async def test_a_target_serving_nothing_is_an_error(self, client):
        """A silent target produces a ValueError that names the target."""
        client._fetch_remote_schema = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match=TARGET_A):
            await client.list_schemas_for_target(TARGET_A)


class TestSchemaComponentsForTarget:
    """Component enumeration under an arbitrary dotted prefix."""

    @pytest.mark.asyncio
    async def test_default_prefix_lists_component_schemas(self, client):
        """With no prefix the component schema names are returned."""
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow", "Port"])
        )

        assert sorted(await client.get_schema_components_for_target(TARGET_A)) == [
            "Flow",
            "Port",
        ]

    @pytest.mark.asyncio
    async def test_a_custom_prefix_is_navigated(self, client):
        """Any dotted path resolving to a mapping can be enumerated."""
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow"])
        )

        assert await client.get_schema_components_for_target(
            TARGET_A, "components"
        ) == ["schemas"]

    @pytest.mark.asyncio
    async def test_a_prefix_resolving_to_a_scalar_lists_nothing(self, client):
        """A path that is not a mapping yields an empty list, not a raise."""
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow"])
        )

        assert await client.get_schema_components_for_target(TARGET_A, "info.version") == []

    @pytest.mark.asyncio
    async def test_an_unresolvable_prefix_is_an_error(self, client):
        """A path that does not exist in the document is reported as an error."""
        client._fetch_remote_schema = AsyncMock(
            return_value=document("1.20.0", ["Flow"])
        )

        with pytest.raises(ValueError, match="Error getting schema components"):
            await client.get_schema_components_for_target(TARGET_A, "nope.nowhere")


class TestServedDocumentAcceptance:
    """What counts as a usable document when it comes off the wire."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "info",
        [None, "1.20.0", {"title": "no version here"}],
        ids=["absent-info", "info-not-a-mapping", "info-without-version"],
    )
    async def test_a_document_with_odd_info_is_still_accepted(
        self, client, monkeypatch, info
    ):
        """Component lookups do not depend on info.version being well formed.

        The served spec version is only ever logged; it is not the same thing as
        the app version the target reports from /capabilities/version, and it is
        never matched against anything.
        """
        served = {"components": {"schemas": {"Flow": {"description": "Flow"}}}}
        if info is not None:
            served["info"] = info

        monkeypatch.setattr(
            "otg_mcp.client.aiohttp.ClientSession", _session_returning(200, served)
        )

        assert await client._fetch_remote_schema(TARGET_A) == served


def _session_returning(status, payload):
    """Build a fake aiohttp.ClientSession class yielding one canned response.

    Args:
        status: HTTP status code the fake response reports
        payload: Object returned by ``response.json()``

    Returns:
        A class that can stand in for ``aiohttp.ClientSession``
    """

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
