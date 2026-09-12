"""
Tests for traffic control and packet capture in OtgClient.

snappi renamed the traffic control APIs across releases, so the client probes for
whichever entry point a generator actually implements instead of checking
versions. Each test below hands the client an API object exposing exactly ONE
branch of those chains, which is the only way to prove every branch still works
and that the ordering between them is preserved.

Every API object here is a fake or a mock; no test opens a socket or a real
capture.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from otg_mcp.client import OtgClient
from otg_mcp.config import Config, TargetConfig

TARGET = "gen-a.example.com:8443"


def make_client():
    """Build a client with a single configured target.

    Returns:
        An OtgClient whose only target is TARGET
    """
    config = Config()
    config.targets.targets.clear()
    config.targets.targets[TARGET] = TargetConfig()
    return OtgClient(config=config)


@pytest.fixture
def fake_clock(monkeypatch):
    """Replace the client's view of time with a clock only sleep() advances.

    _verify_traffic_stopped polls with sleeps until a timeout, so a virtual
    clock keeps those tests deterministic and instant.

    Returns:
        The mutable clock state, with the current value under "now"
    """
    import otg_mcp.client as client_module

    state = {"now": 1_000.0, "sleeps": []}

    def sleep(seconds):
        state["sleeps"].append(seconds)
        state["now"] += seconds

    monkeypatch.setattr(
        client_module, "time", SimpleNamespace(time=lambda: state["now"], sleep=sleep)
    )
    return state


class FlowTransmit:
    """A flow_transmit object exposing the START/STOP enum constants."""

    START = "FT_START"
    STOP = "FT_STOP"

    def __init__(self):
        self.state = None


class LegacyFlowTransmit:
    """A flow_transmit object from a build without the enum constants."""

    def __init__(self):
        self.state = None


class Traffic:
    """The traffic branch of a control_state object."""

    FLOW_TRANSMIT = "traffic.flow_transmit"

    def __init__(self, flow_transmit):
        self.choice = None
        if flow_transmit is not None:
            self.flow_transmit = flow_transmit


class ControlState:
    """A control_state object with a configurable traffic branch."""

    TRAFFIC = "cs.traffic"

    def __init__(self, traffic):
        self.choice = None
        if traffic is not None:
            self.traffic = traffic


class ControlStateApi:
    """An API whose only traffic entry point is control_state."""

    def __init__(self, control_state):
        self._control_state = control_state
        self.applied = []

    def control_state(self):
        """Return the control_state object under test."""
        return self._control_state

    def set_control_state(self, control_state):
        """Record the applied control state."""
        self.applied.append(control_state)
        return SimpleNamespace(warnings=[])


class StartTransmitApi:
    """An API exposing only the oldest start entry point."""

    def __init__(self):
        self.calls = []

    def start_transmit(self):
        """Record that the direct start method was used."""
        self.calls.append("start_transmit")


class FlowTransmitApi:
    """An API exposing only set_flow_transmit."""

    def __init__(self):
        self.calls = []

    def set_flow_transmit(self, state):
        """Record the requested transmit state."""
        self.calls.append(state)


class StopTransmitApi:
    """An API exposing only the direct stop entry point."""

    def __init__(self):
        self.calls = []

    def stop_transmit(self):
        """Record that the direct stop method was used."""
        self.calls.append("stop_transmit")


class TransmitStateApi:
    """An API exposing only the transmit_state pair."""

    def __init__(self):
        self.applied = []

    def transmit_state(self):
        """Return a transmit state object carrying a STOP constant."""
        return SimpleNamespace(STOP="TS_STOP", state=None)

    def set_transmit_state(self, transmit_state):
        """Record the applied transmit state."""
        self.applied.append(transmit_state)


class TestStartTrafficChain:
    """start_transmit -> set_flow_transmit -> control_state, in that order."""

    def test_direct_start_is_preferred(self):
        """When start_transmit exists it is used without further probing."""
        client = make_client()
        api = StartTransmitApi()

        client._start_traffic(api)

        assert api.calls == ["start_transmit"]

    def test_flow_transmit_is_the_second_choice(self):
        """A generator with only set_flow_transmit is started with state=start."""
        client = make_client()
        api = FlowTransmitApi()

        client._start_traffic(api)

        assert api.calls == ["start"]

    def test_control_state_is_the_last_resort(self):
        """The newest API is driven through the traffic/flow_transmit choices."""
        client = make_client()
        flow_transmit = FlowTransmit()
        control_state = ControlState(Traffic(flow_transmit))
        api = ControlStateApi(control_state)

        client._start_traffic(api)

        assert control_state.choice == ControlState.TRAFFIC
        assert control_state.traffic.choice == Traffic.FLOW_TRANSMIT
        assert flow_transmit.state == FlowTransmit.START
        assert api.applied == [control_state]

    def test_control_state_without_enum_constants_uses_a_plain_string(self):
        """Builds that predate the enum constants accept the literal "start"."""
        client = make_client()
        flow_transmit = LegacyFlowTransmit()
        api = ControlStateApi(ControlState(Traffic(flow_transmit)))

        client._start_traffic(api)

        assert flow_transmit.state == "start"

    def test_control_state_without_a_traffic_branch_is_rejected(self):
        """An unusable control_state fails loudly rather than silently."""
        client = make_client()
        api = ControlStateApi(ControlState(traffic=None))

        with pytest.raises(AttributeError, match="traffic attribute"):
            client._start_traffic(api)

        assert api.applied == []

    def test_control_state_without_flow_transmit_is_rejected(self):
        """A traffic branch missing flow_transmit is also rejected."""
        client = make_client()
        api = ControlStateApi(ControlState(Traffic(flow_transmit=None)))

        with pytest.raises(AttributeError, match="flow_transmit attribute"):
            client._start_traffic(api)

    def test_an_api_with_no_start_method_is_unsupported(self):
        """A generator implementing none of the branches is an explicit error."""
        client = make_client()

        with pytest.raises(NotImplementedError, match="start traffic"):
            client._start_traffic(SimpleNamespace())


class TestStartTrafficTool:
    """The async wrapper never raises at the MCP boundary."""

    @pytest.mark.asyncio
    async def test_success_reports_the_action(self):
        """A successful start is reported as a success ControlResponse."""
        client = make_client()

        with patch.object(client, "_get_api_client", return_value=StartTransmitApi()):
            result = await client.start_traffic(TARGET)

        assert result.status == "success"
        assert result.action == "traffic_generation"

    @pytest.mark.asyncio
    async def test_unsupported_api_becomes_an_error_response(self):
        """An unsupported generator yields an error response, not a raise."""
        client = make_client()

        with patch.object(
            client, "_get_api_client", return_value=SimpleNamespace()
        ):
            result = await client.start_traffic(TARGET)

        assert result.status == "error"
        assert result.action == "traffic_generation"
        assert "start traffic" in result.result["error"]

    @pytest.mark.asyncio
    async def test_connection_failure_becomes_an_error_response(self):
        """A generator that cannot be reached is reported, not raised."""
        client = make_client()

        with patch.object(
            client, "_get_api_client", side_effect=ConnectionError("refused")
        ):
            result = await client.start_traffic(TARGET)

        assert result.status == "error"
        assert "refused" in result.result["error"]


class TestStopTrafficChain:
    """stop_transmit -> transmit_state -> control_state -> set_flow_transmit."""

    def test_direct_stop_is_preferred(self):
        """stop_transmit wins when present, and verification then runs."""
        client = make_client()
        api = StopTransmitApi()

        with patch.object(
            client, "_verify_traffic_stopped", return_value=True
        ) as verify:
            assert client._stop_traffic(api) is True

        assert api.calls == ["stop_transmit"]
        verify.assert_called_once_with(api)

    def test_transmit_state_is_the_second_choice(self):
        """The transmit_state pair is used when the direct method is absent."""
        client = make_client()
        api = TransmitStateApi()

        with patch.object(client, "_verify_traffic_stopped", return_value=True):
            assert client._stop_traffic(api) is True

        assert api.applied[0].state == "TS_STOP"

    def test_control_state_is_the_third_choice(self):
        """control_state is driven with the STOP constant when available."""
        client = make_client()
        flow_transmit = FlowTransmit()
        api = ControlStateApi(ControlState(Traffic(flow_transmit)))

        with patch.object(client, "_verify_traffic_stopped", return_value=True):
            assert client._stop_traffic(api) is True

        assert flow_transmit.state == FlowTransmit.STOP
        assert len(api.applied) == 1

    def test_control_state_without_enum_constants_uses_a_plain_string(self):
        """Older control_state builds accept the literal "stop"."""
        client = make_client()
        flow_transmit = LegacyFlowTransmit()
        api = ControlStateApi(ControlState(Traffic(flow_transmit)))

        with patch.object(client, "_verify_traffic_stopped", return_value=True):
            client._stop_traffic(api)

        assert flow_transmit.state == "stop"

    def test_flow_transmit_is_the_final_fallback(self):
        """A generator with only set_flow_transmit is stopped through it."""
        client = make_client()
        api = FlowTransmitApi()

        with patch.object(client, "_verify_traffic_stopped", return_value=True):
            assert client._stop_traffic(api) is True

        assert api.calls == ["stop"]

    def test_a_broken_control_state_falls_through_to_the_next_method(self):
        """A branch that raises is skipped so a later branch can still work.

        This is what keeps a generator with a half-implemented control_state
        working: the chain continues rather than aborting.
        """
        client = make_client()

        class BrokenControlStateThenFlowTransmit(ControlStateApi):
            def __init__(self):
                super().__init__(ControlState(traffic=None))
                self.flow_calls = []

            def set_flow_transmit(self, state):
                self.flow_calls.append(state)

        api = BrokenControlStateThenFlowTransmit()

        with patch.object(client, "_verify_traffic_stopped", return_value=True):
            assert client._stop_traffic(api) is True

        assert api.flow_calls == ["stop"]

    def test_no_available_method_reports_failure(self):
        """When every branch is missing the client reports failure, not a raise."""
        client = make_client()

        with patch.object(client, "_verify_traffic_stopped") as verify:
            assert client._stop_traffic(SimpleNamespace()) is False

        verify.assert_not_called()

    @pytest.mark.parametrize(
        "control_state,expected",
        [
            (ControlState(traffic=None), "traffic attribute"),
            (ControlState(Traffic(flow_transmit=None)), "flow_transmit attribute"),
        ],
        ids=["no-traffic-branch", "no-flow-transmit-branch"],
    )
    def test_an_incomplete_control_state_is_rejected(self, control_state, expected):
        """A control_state the client cannot drive raises instead of no-oping.

        The stop chain relies on this raise to move on to the next branch.
        """
        client = make_client()
        api = ControlStateApi(control_state)

        with pytest.raises(AttributeError, match=expected):
            client._stop_traffic_control_state(api)

        assert api.applied == []

    def test_unverified_stop_is_reported_as_unverified(self):
        """A stop the metrics never confirm is reported as False, not True."""
        client = make_client()

        with patch.object(client, "_verify_traffic_stopped", return_value=False):
            assert client._stop_traffic(StopTransmitApi()) is False


class TestStopTrafficTool:
    """The async wrapper surfaces verification without raising."""

    @pytest.mark.asyncio
    async def test_verified_stop_is_reported(self):
        """A verified stop reports verified=True in the response payload."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=StopTransmitApi()),
            patch.object(client, "_verify_traffic_stopped", return_value=True),
        ):
            result = await client.stop_traffic(TARGET)

        assert result.status == "success"
        assert result.result == {"verified": True}

    @pytest.mark.asyncio
    async def test_unverified_stop_is_reported_as_an_error(self):
        """A stop that could not be carried out reports status="error".

        The API object here exposes none of the stop methods, so every branch of
        the fallback chain fails. This used to return status="success" with
        verified=False buried in the result, so a caller checking only status -
        the field that exists to convey exactly this - believed traffic had
        stopped while it was still running.
        """
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=SimpleNamespace()),
        ):
            result = await client.stop_traffic(TARGET)

        assert result.status == "error"
        assert result.result is not None
        assert result.result["verified"] is False
        assert "error" in result.result

    @pytest.mark.asyncio
    async def test_connection_failure_becomes_an_error_response(self):
        """A generator that cannot be reached is reported, not raised."""
        client = make_client()

        with patch.object(
            client, "_get_api_client", side_effect=ConnectionError("refused")
        ):
            result = await client.stop_traffic(TARGET)

        assert result.status == "error"
        assert "refused" in result.result["error"]


def metrics_api(*responses):
    """Build an API mock whose get_metrics yields the given results in order.

    Args:
        responses: Objects (or exceptions) returned by successive get_metrics calls

    Returns:
        A MagicMock standing in for the snappi API object
    """
    api = MagicMock()
    api.get_metrics.side_effect = list(responses)
    return api


def flow(name, rate):
    """Build a flow metric with a transmit rate.

    Args:
        name: Flow name
        rate: frames_tx_rate value

    Returns:
        A simple object shaped like a snappi flow metric
    """
    return SimpleNamespace(name=name, frames_tx_rate=rate)


class TestVerifyTrafficStopped:
    """Polling flow metrics until transmit rates fall below the threshold."""

    def test_absent_flow_metrics_counts_as_stopped(self, fake_clock):
        """A generator reporting no flow metrics at all is treated as idle."""
        client = make_client()

        assert client._verify_traffic_stopped(metrics_api(SimpleNamespace())) is True

    def test_empty_flow_metrics_counts_as_stopped(self, fake_clock):
        """An empty metric list is treated as idle rather than as unknown."""
        client = make_client()
        api = metrics_api(SimpleNamespace(flow_metrics=[]))

        assert client._verify_traffic_stopped(api) is True

    def test_rates_below_the_threshold_count_as_stopped(self, fake_clock):
        """Residual near-zero rates do not keep the client waiting."""
        client = make_client()
        api = metrics_api(
            SimpleNamespace(flow_metrics=[flow("f1", 0.0), flow("f2", 0.05)])
        )

        assert client._verify_traffic_stopped(api) is True

    def test_a_running_flow_is_polled_until_it_drops(self, fake_clock):
        """Verification keeps polling while any flow is still transmitting."""
        client = make_client()
        api = metrics_api(
            SimpleNamespace(flow_metrics=[flow("f1", 1_000.0)]),
            SimpleNamespace(flow_metrics=[flow("f1", 0.0)]),
        )

        assert client._verify_traffic_stopped(api) is True
        assert api.get_metrics.call_count == 2

    def test_a_flow_that_never_stops_times_out(self, fake_clock):
        """A flow still running at the deadline yields False, not a hang."""
        client = make_client()
        api = MagicMock()
        api.get_metrics.return_value = SimpleNamespace(
            flow_metrics=[flow("f1", 500.0)]
        )

        assert client._verify_traffic_stopped(api, timeout=2) is False
        assert sum(fake_clock["sleeps"]) >= 2

    def test_metrics_errors_do_not_abort_verification(self, fake_clock):
        """Transient metrics failures are retried until the timeout expires."""
        client = make_client()
        api = MagicMock()
        api.get_metrics.side_effect = RuntimeError("metrics unavailable")

        assert client._verify_traffic_stopped(api, timeout=1) is False
        assert api.get_metrics.call_count >= 2

    def test_the_threshold_is_configurable(self, fake_clock):
        """A caller can widen the threshold to accept a higher residual rate."""
        client = make_client()
        api = metrics_api(SimpleNamespace(flow_metrics=[flow("f1", 5.0)]))

        assert client._verify_traffic_stopped(api, threshold=10.0) is True


class TestCaptureTools:
    """The async capture tools delegate to client_capture and never raise."""

    @pytest.mark.asyncio
    async def test_start_capture_success(self):
        """A successful start reports the port that capture was started on."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch(
                "otg_mcp.client.start_capture", return_value={"status": "success"}
            ) as start,
        ):
            result = await client.start_capture("p1", TARGET)

        assert result.status == "success"
        assert result.port == "p1"
        assert start.call_args[0][1] == "p1"

    @pytest.mark.asyncio
    async def test_start_capture_on_many_ports_reports_the_first(self):
        """Multi-port capture is reported against the first port named."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch("otg_mcp.client.start_capture", return_value={"status": "success"}),
        ):
            result = await client.start_capture(["p1", "p2"], TARGET)

        assert result.port == "p1"

    @pytest.mark.asyncio
    async def test_start_capture_with_no_ports_reports_an_empty_port(self):
        """An empty port list must not break response construction."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch("otg_mcp.client.start_capture", return_value={"status": "success"}),
        ):
            result = await client.start_capture([], TARGET)

        assert result.port == ""

    @pytest.mark.asyncio
    async def test_start_capture_failure_is_surfaced(self):
        """A failure reported by the capture helper becomes an error response."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch(
                "otg_mcp.client.start_capture",
                return_value={"status": "error", "error": "capture not enabled"},
            ),
        ):
            result = await client.start_capture("p1", TARGET)

        assert result.status == "error"
        assert result.data == {"error": "capture not enabled"}

    @pytest.mark.asyncio
    async def test_start_capture_failure_without_detail_still_reports(self):
        """An error with no message still produces a usable error response."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch("otg_mcp.client.start_capture", return_value={"status": "error"}),
        ):
            result = await client.start_capture("p1", TARGET)

        assert result.data == {"error": "Unknown error"}

    @pytest.mark.asyncio
    async def test_start_capture_connection_failure_is_surfaced(self):
        """An unreachable generator yields an error response, not a raise."""
        client = make_client()

        with patch.object(
            client, "_get_api_client", side_effect=ConnectionError("refused")
        ):
            result = await client.start_capture("p1", TARGET)

        assert result.status == "error"
        assert "refused" in result.data["error"]

    @pytest.mark.asyncio
    async def test_stop_capture_success_carries_warnings(self):
        """Warnings from the generator are passed through to the caller."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch(
                "otg_mcp.client.stop_capture",
                return_value={"status": "success", "warnings": ["port was idle"]},
            ),
        ):
            result = await client.stop_capture(["p1", "p2"], TARGET)

        assert result.status == "success"
        assert result.port == "p1"
        assert result.data == {"status": "stopped", "warnings": ["port was idle"]}

    @pytest.mark.asyncio
    async def test_stop_capture_failure_is_surfaced(self):
        """A stop failure becomes an error response naming the reason."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch(
                "otg_mcp.client.stop_capture",
                return_value={"status": "error", "error": "no capture running"},
            ),
        ):
            result = await client.stop_capture("p1", TARGET)

        assert result.status == "error"
        assert result.data == {"error": "no capture running"}

    @pytest.mark.asyncio
    async def test_stop_capture_with_no_ports_reports_an_empty_port(self):
        """An empty port list must not break response construction."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch("otg_mcp.client.stop_capture", return_value={"status": "success"}),
        ):
            result = await client.stop_capture([], TARGET)

        assert result.port == ""

    @pytest.mark.asyncio
    async def test_stop_capture_connection_failure_is_surfaced(self):
        """An unreachable generator yields an error response, not a raise."""
        client = make_client()

        with patch.object(
            client, "_get_api_client", side_effect=ConnectionError("refused")
        ):
            result = await client.stop_capture("p1", TARGET)

        assert result.status == "error"
        assert "refused" in result.data["error"]

    @pytest.mark.asyncio
    async def test_get_capture_returns_the_file_path_and_size(self):
        """A retrieved capture reports where it landed and how big it is."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch(
                "otg_mcp.client.get_capture",
                return_value={
                    "status": "success",
                    "file_path": "/tmp/capture_p1.pcap",
                    "size_bytes": 4096,
                    "capture_id": "capture_p1.pcap",
                },
            ),
        ):
            result = await client.get_capture("p1", target=TARGET)

        assert result.status == "success"
        assert result.file_path == "/tmp/capture_p1.pcap"
        assert result.capture_id == "capture_p1.pcap"
        assert result.data["size_bytes"] == 4096
        assert "warning" not in result.data

    @pytest.mark.asyncio
    async def test_an_empty_capture_is_flagged_as_such(self):
        """A zero-byte pcap is still a success, but carries a warning.

        Silently returning an empty file reads as a broken capture; the warning
        tells the caller the port simply received no frames.
        """
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch(
                "otg_mcp.client.get_capture",
                return_value={
                    "status": "success",
                    "file_path": "/tmp/empty.pcap",
                    "size_bytes": 0,
                },
            ),
        ):
            result = await client.get_capture("p1", target=TARGET)

        assert result.status == "success"
        assert result.data["warning"] == "capture is empty, no frames were received"

    @pytest.mark.asyncio
    async def test_get_capture_failure_is_surfaced(self):
        """A retrieval failure becomes an error response naming the reason."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch(
                "otg_mcp.client.get_capture",
                return_value={"status": "error", "error": "capture buffer empty"},
            ),
        ):
            result = await client.get_capture("p1", target=TARGET)

        assert result.status == "error"
        assert result.data == {"error": "capture buffer empty"}

    @pytest.mark.asyncio
    async def test_get_capture_connection_failure_is_surfaced(self):
        """An unreachable generator yields an error response, not a raise."""
        client = make_client()

        with patch.object(
            client, "_get_api_client", side_effect=ConnectionError("refused")
        ):
            result = await client.get_capture("p1", target=TARGET)

        assert result.status == "error"
        assert "refused" in result.data["error"]

    @pytest.mark.asyncio
    async def test_capture_helpers_receive_the_output_options(self):
        """Output directory and filename are forwarded to the capture helper."""
        client = make_client()

        with (
            patch.object(client, "_get_api_client", return_value=MagicMock()),
            patch(
                "otg_mcp.client.get_capture",
                return_value={
                    "status": "success",
                    "file_path": "/out/mine.pcap",
                    "size_bytes": 1,
                },
            ) as helper,
        ):
            await client.get_capture(
                "p1", output_dir="/out", target=TARGET, filename="mine"
            )

        assert helper.call_args.kwargs == {"output_dir": "/out", "filename": "mine"}


class CaptureBranch:
    """A capture branch of control_state exposing the enum constants."""

    START = "CAP_START"
    STOP = "CAP_STOP"
    RETRIEVE = "CAP_RETRIEVE"

    def __init__(self):
        self.state = None
        self.port_names = None
        self.port_name = None


class LegacyCaptureBranch:
    """A capture branch from a build without the enum constants."""

    def __init__(self):
        self.state = None
        self.port_names = None
        self.port_name = None


class CaptureControlState:
    """A control_state object whose choice can be set to CAPTURE."""

    CAPTURE = "cs.capture"

    def __init__(self, capture):
        self.choice = None
        if capture is not None:
            self.capture = capture


class ChoiceOnlyControlState:
    """A control_state that declares no CAPTURE choice at all."""

    def __init__(self):
        self.choice = None


def capture_branch(*fields, constants=True):
    """Build a capture branch exposing only the named fields.

    Args:
        fields: Attribute names the branch declares
        constants: Whether the enum constants are present

    Returns:
        An object shaped like a partially implemented capture branch
    """
    namespace = {}
    if constants:
        namespace.update(START="CAP_START", STOP="CAP_STOP", RETRIEVE="CAP_RETRIEVE")
    branch = type("PartialCaptureBranch", (), namespace)()
    for field_name in fields:
        setattr(branch, field_name, None)
    return branch


class CaptureControlStateApi:
    """An API whose only capture entry point is control_state."""

    def __init__(self, control_state, result=None):
        self._control_state = control_state
        self._result = result
        self.applied = []

    def control_state(self):
        """Return the control_state object under test."""
        return self._control_state

    def set_control_state(self, control_state):
        """Record the applied control state and return the canned result."""
        self.applied.append(control_state)
        return self._result


