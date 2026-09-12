"""
Unit tests for OtgClient plumbing: client caching, version probing, target
enumeration, health, and the config/metrics round trips.

Nothing here talks to hardware. The snappi API object is always a mock or a
purpose-built fake, and the two aiohttp probes are replaced with fake sessions.

Two distinct notions of "version" are exercised and deliberately kept apart:
`_get_api_version` / `_discover_api_schema` inspect the *local* snappi library,
while `get_target_version` asks the *remote* generator over HTTP.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from otg_mcp.client import OtgClient
from otg_mcp.config import Config, PortConfig, TargetConfig
from otg_mcp.models import CapabilitiesVersionResponse

TARGET = "gen-a.example.com:8443"


def make_client(*target_names):
    """Build a client whose config contains the named targets and nothing else.

    Args:
        target_names: Config keys, each of which is also the target's address

    Returns:
        An OtgClient with an empty client and schema cache
    """
    config = Config()
    config.targets.targets.clear()
    for name in target_names:
        config.targets.targets[name] = TargetConfig(
            ports={"p1": PortConfig(location="eth1", name="p1", interface="eth1")}
        )
    return OtgClient(config=config)


def session_returning(status, payload):
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
            FakeSession.requested_url = url
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    return FakeSession


class RecordingMetricsRequest:
    """A metrics request that records which dimensions were populated."""

    def __init__(self):
        self.populated = {}

    def __getattr__(self, name):
        """Create and record a dimension on first access."""
        dimension = SimpleNamespace()
        self.populated[name] = dimension
        return dimension


class BrokenTargets:
    """Stands in for TargetsConfig when reading targets must fail."""

    @property
    def targets(self):
        """Raise instead of returning the target mapping."""
        raise RuntimeError("config exploded")


class TestApiClientCache:
    """One snappi client per target, created lazily and reused."""

    def test_client_is_created_once_and_reused(self):
        """A second call for the same target must not open a new connection.

        Creating a snappi client performs I/O against the generator, so the
        cache is what keeps repeated tool calls cheap.
        """
        client = make_client(TARGET)

        with patch("otg_mcp.client.snappi.api", return_value=MagicMock()) as snappi_api:
            first = client._get_api_client(TARGET)
            second = client._get_api_client(TARGET)

        assert first is second
        assert snappi_api.call_count == 1
        assert client.api_clients[TARGET] is first

    def test_client_is_created_with_tls_verification_disabled(self):
        """Lab gear uses self-signed certs, so verify=False is intentional."""
        client = make_client(TARGET)

        with patch("otg_mcp.client.snappi.api", return_value=MagicMock()) as snappi_api:
            client._get_api_client(TARGET)

        snappi_api.assert_called_once_with(location=f"https://{TARGET}", verify=False)

    def test_separate_targets_get_separate_clients(self):
        """Two configured generators must never share a snappi client."""
        client = make_client(TARGET, "gen-b.example.com:8443")

        with patch("otg_mcp.client.snappi.api", side_effect=[MagicMock(), MagicMock()]):
            a = client._get_api_client(TARGET)
            b = client._get_api_client("gen-b.example.com:8443")

        assert a is not b
        assert len(client.api_clients) == 2

    @pytest.mark.parametrize(
        "target", ["localhost:8443", "gen.example.com", "10.0.0.1:443"]
    )
    def test_location_is_the_target_key_over_https(self, target):
        """The config key *is* the address; it is used verbatim under https.

        A symbolic label would not connect, which is why this is pinned.
        """
        client = make_client(target)

        assert client._get_location_for_target(target) == f"https://{target}"


class TestLocalApiIntrospection:
    """Feature detection against the locally installed snappi library."""

    def test_schema_reports_which_traffic_methods_exist(self):
        """Discovery records exactly the traffic entry points the API exposes.

        The traffic control fallback chains rely on this feature detection, so
        an API exposing only control_state must be reported as such.
        """
        api = MagicMock(spec=["control_state", "set_control_state"])

        schema = OtgClient(config=Config())._discover_api_schema(api)

        assert schema["has_control_state"] is True
        assert schema["has_start_transmit"] is False
        assert schema["has_stop_transmit"] is False
        assert schema["has_set_flow_transmit"] is False
        assert schema["has_transmit_state"] is False
        assert "control_state" in schema["methods"]

    def test_schema_reports_a_fully_featured_api(self):
        """An API with every entry point is reported with all flags set."""
        api = MagicMock(
            spec=[
                "control_state",
                "transmit_state",
                "start_transmit",
                "stop_transmit",
                "set_flow_transmit",
            ]
        )

        schema = OtgClient(config=Config())._discover_api_schema(api)

        flags = {key: value for key, value in schema.items() if key.startswith("has_")}
        assert len(flags) == 5
        assert all(flags.values())

    def test_version_prefers_the_api_object(self):
        """A snappi object that advertises its own version wins."""
        client = OtgClient(config=Config())
        api = SimpleNamespace()
        api.__version__ = "9.9.9"

        assert client._get_api_version(api) == "9.9.9"

    def test_version_falls_back_to_the_snappi_library(self, monkeypatch):
        """Without a version on the object, the installed library is reported."""
        import otg_mcp.client as client_module

        monkeypatch.setattr(client_module.snappi, "__version__", "1.28.2", raising=False)
        client = OtgClient(config=Config())

        assert client._get_api_version(MagicMock(spec=[])) == "1.28.2"

    def test_version_is_unknown_when_nothing_advertises_one(self, monkeypatch):
        """An unknowable version is reported as such rather than guessed."""
        import otg_mcp.client as client_module

        monkeypatch.delattr(client_module.snappi, "__version__", raising=False)
        client = OtgClient(config=Config())

        assert client._get_api_version(MagicMock(spec=[])) == "unknown"


class TestRemoteTargetVersion:
    """The HTTP probe of the generator's own /capabilities/version."""

    @pytest.mark.asyncio
    async def test_version_is_reported_verbatim(self, monkeypatch):
        """Whatever the generator reports is passed through unchanged.

        The served value is not reconciled with any local snappi version.
        """
        payload = {
            "api_spec_version": "1.20.0",
            "sdk_version": "1.28.2",
            "app_version": "1.28.0-33",
        }
        session = session_returning(200, payload)
        monkeypatch.setattr("otg_mcp.client.aiohttp.ClientSession", session)

        result = await make_client(TARGET).get_target_version(TARGET)

        assert isinstance(result, CapabilitiesVersionResponse)
        assert result.app_version == "1.28.0-33"
        assert result.sdk_version == "1.28.2"
        assert session.requested_url == f"https://{TARGET}/capabilities/version"

    @pytest.mark.asyncio
    async def test_non_200_raises_naming_the_target(self, monkeypatch):
        """A generator that refuses the probe produces a ValueError, not None."""
        monkeypatch.setattr(
            "otg_mcp.client.aiohttp.ClientSession", session_returning(503, {})
        )

        with pytest.raises(ValueError, match=f"Failed to get version from {TARGET}"):
            await make_client(TARGET).get_target_version(TARGET)


class TestAvailableTargets:
    """Enumeration of configured targets with liveness and version."""

    @pytest.mark.asyncio
    async def test_reachable_target_reports_ports_and_version(self):
        """A reachable target carries its ports plus the version it reports."""
        client = make_client(TARGET)
        version = CapabilitiesVersionResponse(
            api_spec_version="1.20.0", sdk_version="1.28.2", app_version="1.28.0"
        )

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch.object(client, "get_target_version", return_value=version),
        ):
            result = await client.get_available_targets()

        assert result[TARGET]["available"] is True
        assert result[TARGET]["apiVersion"] == "1.28.2"
        assert result[TARGET]["ports"]["p1"] == {"location": "eth1", "name": "p1"}

    @pytest.mark.asyncio
    async def test_version_failure_does_not_mark_target_unavailable(self):
        """A connectable target with a broken version endpoint stays available.

        The version error is surfaced separately so callers can still use the
        target for traffic operations.
        """
        client = make_client(TARGET)

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch.object(
                client, "get_target_version", side_effect=RuntimeError("no endpoint")
            ),
        ):
            result = await client.get_available_targets()

        assert result[TARGET]["available"] is True
        assert "no endpoint" in result[TARGET]["apiVersionError"]
        assert "apiVersion" not in result[TARGET]

    @pytest.mark.asyncio
    async def test_unreachable_target_is_reported_with_its_error(self):
        """A target that cannot be connected to is flagged, not omitted."""
        client = make_client(TARGET)

        with patch.object(
            client, "_get_api_client", side_effect=ConnectionError("refused")
        ):
            result = await client.get_available_targets()

        assert result[TARGET]["available"] is False
        assert "refused" in result[TARGET]["error"]

    @pytest.mark.asyncio
    async def test_cache_is_cleared_so_liveness_is_measured_fresh(self):
        """Stale cached clients would make a dead target look alive."""
        client = make_client(TARGET)
        client.api_clients["stale-target:8443"] = MagicMock()

        with patch.object(
            client, "_get_api_client", side_effect=ConnectionError("refused")
        ):
            await client.get_available_targets()

        assert "stale-target:8443" not in client.api_clients

    @pytest.mark.asyncio
    async def test_unreadable_config_yields_an_empty_mapping(self):
        """A failure reading config is swallowed into an empty result."""
        client = make_client(TARGET)
        client.config = SimpleNamespace(targets=BrokenTargets())

        assert await client.get_available_targets() == {}


class TestTargetConfigLookup:
    """_get_target_config layers the reported version onto the target entry."""

    @pytest.mark.asyncio
    async def test_known_target_carries_the_reported_version(self):
        """The version the target reports is attached to its config entry."""
        client = make_client(TARGET)
        version = CapabilitiesVersionResponse(
            api_spec_version="1.20.0", sdk_version="1.28.2", app_version="1.28.0"
        )

        with (
            patch.object(
                client, "get_available_targets", return_value={TARGET: {"ports": {}}}
            ),
            patch.object(client, "get_target_version", return_value=version),
        ):
            result = await client._get_target_config(TARGET)

        assert result["apiVersion"] == "1.28.2"

    @pytest.mark.asyncio
    async def test_version_probe_failure_leaves_version_unknown(self):
        """A silent target still yields a config entry, with version unknown."""
        client = make_client(TARGET)

        with (
            patch.object(
                client, "get_available_targets", return_value={TARGET: {"ports": {}}}
            ),
            patch.object(
                client, "get_target_version", side_effect=RuntimeError("timeout")
            ),
        ):
            result = await client._get_target_config(TARGET)

        assert result["apiVersion"] == "unknown"

    @pytest.mark.asyncio
    async def test_unknown_target_is_none(self):
        """Looking up a target that is not configured yields None."""
        client = make_client(TARGET)

        with patch.object(client, "get_available_targets", return_value={}):
            assert await client._get_target_config("nope.example.com:8443") is None

    @pytest.mark.asyncio
    async def test_enumeration_failure_is_none(self):
        """An error while enumerating targets is swallowed into None."""
        client = make_client(TARGET)

        with patch.object(
            client, "get_available_targets", side_effect=RuntimeError("boom")
        ):
            assert await client._get_target_config(TARGET) is None


class TestTrafficGeneratorListing:
    """list_traffic_generators and its legacy alias."""

    @pytest.mark.asyncio
    async def test_generators_and_ports_are_listed(self):
        """Every configured target is listed with its ports resolved."""
        client = make_client(TARGET)

        result = await client.list_traffic_generators()

        assert set(result.generators) == {TARGET}
        generator = result.generators[TARGET]
        assert generator.available is True
        assert generator.ports["p1"].location == "eth1"

    @pytest.mark.asyncio
    async def test_port_without_a_location_is_listed_with_an_empty_one(self):
        """A location-less port must not break listing with a validation error."""
        client = make_client(TARGET)
        client.config.targets.targets[TARGET] = TargetConfig(
            ports={"p1": PortConfig(location=None, name="p1", interface=None)}
        )

        result = await client.list_traffic_generators()

        assert result.generators[TARGET].ports["p1"].location == ""

    @pytest.mark.asyncio
    async def test_unreachable_generator_is_reported_unavailable(self):
        """A generator that cannot be reached is listed with available=False.

        This used to be impossible to observe: the availability check was a bare
        logger call inside a try block that then set available=True
        unconditionally, so every configured target was reported reachable
        whether or not it answered. Building the client is what actually proves
        reachability.
        """
        client = make_client(TARGET)

        with patch.object(
            client, "_get_api_client", side_effect=ConnectionError("refused")
        ):
            result = await client.list_traffic_generators()

        assert result.generators[TARGET].available is False

    @pytest.mark.asyncio
    async def test_reachable_generator_is_reported_available(self):
        """A generator whose client builds successfully is reported available."""
        client = make_client(TARGET)

        with patch.object(client, "_get_api_client", return_value=object()):
            result = await client.list_traffic_generators()

        assert result.generators[TARGET].available is True

    @pytest.mark.asyncio
    async def test_legacy_status_call_delegates_to_listing(self):
        """The legacy name is kept as a pure alias of the current method."""
        client = make_client(TARGET)

        legacy = await client.get_traffic_generators_status()
        current = await client.list_traffic_generators()

        assert legacy.generators.keys() == current.generators.keys()

    @pytest.mark.asyncio
    async def test_unreadable_config_yields_an_empty_status(self):
        """Errors are reported as an empty status rather than raised."""
        client = make_client(TARGET)
        client.config = SimpleNamespace(targets=BrokenTargets())

        result = await client.list_traffic_generators()

        assert result.generators == {}
        assert result.status == "success"


class TestHealth:
    """Health reporting across one or many targets."""

    @pytest.mark.asyncio
    async def test_healthy_target_keeps_its_version_info(self):
        """A healthy target's reported version is retained for the caller."""
        client = make_client(TARGET)
        version = CapabilitiesVersionResponse(
            api_spec_version="1.20.0", sdk_version="1.28.2", app_version="1.28.0"
        )

        with patch.object(client, "get_target_version", return_value=version):
            result = await client.health(TARGET)

        assert result.status == "success"
        assert result.targets[TARGET].healthy is True
        assert result.targets[TARGET].version_info.app_version == "1.28.0"

    @pytest.mark.asyncio
    async def test_unhealthy_target_downgrades_overall_status(self):
        """One bad target makes the whole report an error, with the reason."""
        client = make_client(TARGET, "gen-b.example.com:8443")

        async def probe(target):
            if target == TARGET:
                return CapabilitiesVersionResponse(
                    api_spec_version="1.20.0",
                    sdk_version="1.28.2",
                    app_version="1.28.0",
                )
            raise ConnectionError("unreachable")

        with (
            patch.object(
                client,
                "get_available_targets",
                return_value={TARGET: {}, "gen-b.example.com:8443": {}},
            ),
            patch.object(client, "get_target_version", side_effect=probe),
        ):
            result = await client.health()

        assert result.status == "error"
        assert result.targets[TARGET].healthy is True
        assert result.targets["gen-b.example.com:8443"].healthy is False
        assert "unreachable" in result.targets["gen-b.example.com:8443"].error

    @pytest.mark.asyncio
    async def test_no_configured_targets_is_not_reported_healthy(self):
        """An empty target list must not vacuously report success."""
        client = make_client()

        with patch.object(client, "get_available_targets", return_value={}):
            result = await client.health()

        assert result.status == "error"
        assert result.targets == {}


class TestConfigRoundTrip:
    """set_config / get_config and their error contract."""

    @staticmethod
    def api_with_config(applied):
        """Build a snappi mock whose get_config returns a serializable config.

        Args:
            applied: Dictionary the serialized config should equal

        Returns:
            A MagicMock standing in for the snappi API object
        """
        api = MagicMock()
        api.get_config.return_value.serialize.return_value = applied
        return api

    @pytest.mark.asyncio
    async def test_dict_config_is_deserialized_then_applied(self):
        """A dict config goes through snappi's own deserializer before use."""
        client = make_client(TARGET)
        api = self.api_with_config({"ports": [{"name": "p1"}]})

        with patch.object(client, "_get_api_client", return_value=api):
            result = await client.set_config({"ports": [{"name": "p1"}]}, TARGET)

        api.config.return_value.deserialize.assert_called_once_with(
            {"ports": [{"name": "p1"}]}
        )
        api.set_config.assert_called_once_with(api.config.return_value)
        assert result.status == "success"
        assert result.config == {"ports": [{"name": "p1"}]}

    @pytest.mark.asyncio
    async def test_non_dict_config_is_passed_straight_through(self):
        """An already-built snappi config object is applied as given."""
        client = make_client(TARGET)
        api = self.api_with_config({"ports": []})
        prebuilt = SimpleNamespace(name="already-a-config")

        with patch.object(client, "_get_api_client", return_value=api):
            result = await client.set_config(prebuilt, TARGET)

        api.set_config.assert_called_once_with(prebuilt)
        api.config.assert_not_called()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_set_config_failure_is_returned_not_raised(self):
        """Errors reach the MCP client as an ApiResponse, never an exception."""
        client = make_client(TARGET)
        api = MagicMock()
        api.set_config.side_effect = RuntimeError("port already owned")

        with patch.object(client, "_get_api_client", return_value=api):
            result = await client.set_config({"ports": []}, TARGET)

        assert result.status == "error"
        assert "port already owned" in result.config["error"]

    @pytest.mark.asyncio
    async def test_get_config_returns_the_serialized_document(self):
        """get_config serializes whatever the generator currently holds."""
        client = make_client(TARGET)
        api = self.api_with_config({"flows": [{"name": "f1"}]})

        with patch.object(client, "_get_api_client", return_value=api):
            result = await client.get_config(TARGET)

        assert result.status == "success"
        assert result.config == {"flows": [{"name": "f1"}]}

    @pytest.mark.asyncio
    async def test_get_config_failure_is_returned_not_raised(self):
        """A generator that cannot be read yields an error response."""
        client = make_client(TARGET)
        api = MagicMock()
        api.get_config.side_effect = RuntimeError("connection reset")

        with patch.object(client, "_get_api_client", return_value=api):
            result = await client.get_config(TARGET)

        assert result.status == "error"
        assert "connection reset" in result.config["error"]

    @pytest.mark.asyncio
    async def test_omitted_target_defaults_to_localhost(self):
        """Calling without a target falls back to the localhost generator."""
        client = make_client(TARGET)
        api = self.api_with_config({})

        with patch.object(client, "_get_api_client", return_value=api) as get_client:
            await client.get_config()

        get_client.assert_called_once_with("localhost")


class TestMetrics:
    """get_metrics request shaping and its error contract."""

    @staticmethod
    def metrics_api(serialized):
        """Build a snappi mock returning serializable metrics.

        Args:
            serialized: Dictionary the serialized metrics should equal

        Returns:
            A MagicMock standing in for the snappi API object
        """
        api = MagicMock()
        api.get_metrics.return_value.serialize.return_value = serialized
        return api

    def test_request_carries_the_requested_dimensions(self):
        """Flow and port filters are set independently on the metrics request."""
        client = make_client(TARGET)
        api = MagicMock()
        request = RecordingMetricsRequest()
        api.metrics_request.return_value = request

        client._get_metrics(api, flow_names=["f1"], port_names=["p1"])

        assert request.populated["flow"].flow_names == ["f1"]
        assert request.populated["port"].port_names == ["p1"]
        api.get_metrics.assert_called_once_with(request)

    @pytest.mark.parametrize(
        "kwargs,expected",
        [
            ({}, set()),
            ({"flow_names": ["f1"]}, {"flow"}),
            ({"port_names": ["p1"]}, {"port"}),
            ({"flow_names": [], "port_names": []}, set()),
        ],
        ids=["unfiltered", "flows-only", "ports-only", "empty-filters"],
    )
    def test_only_supplied_dimensions_are_written_to_the_request(
        self, kwargs, expected
    ):
        """An unrequested dimension is left untouched on the request object.

        Writing an empty name filter would ask the generator for nothing rather
        than for everything.
        """
        client = make_client(TARGET)
        api = MagicMock()
        request = RecordingMetricsRequest()
        api.metrics_request.return_value = request

        client._get_metrics(api, **kwargs)

        assert set(request.populated) == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "flow_names,port_names,expected_flows,expected_ports",
        [
            ("f1", None, ["f1"], None),
            (["f1", "f2"], None, ["f1", "f2"], None),
            (None, "p1", None, ["p1"]),
            (None, ["p1", "p2"], None, ["p1", "p2"]),
            ([], [], [], []),
            (["f1"], ["p1"], ["f1"], ["p1"]),
        ],
        ids=[
            "single-flow",
            "many-flows",
            "single-port",
            "many-ports",
            "all-flows-and-ports",
            "both-dimensions",
        ],
    )
    async def test_names_are_normalised_to_lists(
        self, flow_names, port_names, expected_flows, expected_ports
    ):
        """A bare string name is accepted and normalised to a one-item list."""
        client = make_client(TARGET)
        api = self.metrics_api({"flow_metrics": []})

        with (
            patch.object(client, "_get_api_client", return_value=api),
            patch.object(
                client, "_get_metrics", return_value=api.get_metrics.return_value
            ) as get_metrics,
        ):
            result = await client.get_metrics(
                flow_names=flow_names, port_names=port_names, target=TARGET
            )

        assert result.status == "success"
        get_metrics.assert_called_once_with(
            api, flow_names=expected_flows, port_names=expected_ports
        )

    @pytest.mark.asyncio
    async def test_no_filters_asks_for_everything(self):
        """With no filters the unfiltered metrics request is used."""
        client = make_client(TARGET)
        api = self.metrics_api({"port_metrics": []})

        with (
            patch.object(client, "_get_api_client", return_value=api),
            patch.object(
                client, "_get_metrics", return_value=api.get_metrics.return_value
            ) as get_metrics,
        ):
            result = await client.get_metrics(target=TARGET)

        get_metrics.assert_called_once_with(api)
        assert result.metrics == {"port_metrics": []}

    @pytest.mark.asyncio
    async def test_metrics_failure_is_returned_not_raised(self):
        """A metrics failure is reported through the response model."""
        client = make_client(TARGET)
        api = MagicMock()
        api.get_metrics.side_effect = RuntimeError("no such flow")

        with patch.object(client, "_get_api_client", return_value=api):
            result = await client.get_metrics(flow_names="ghost", target=TARGET)

        assert result.status == "error"
        assert "no such flow" in result.metrics["error"]
