"""
Tests for the packet capture helpers in ``otg_mcp.client_capture``.

These helpers are the only place that builds snappi's three-level capture control
state (``choice`` -> ``port.choice`` -> ``port.capture.state``) and the only place
that writes a ``.pcap`` to disk. Every function here swallows exceptions and
returns a status dictionary instead of raising, because the MCP tools that call
them report errors to the client rather than failing the request, so both the
success and the failure shape of those dictionaries are pinned below.

No real hardware is involved: the snappi API object is a fake that records what
was set on it.
"""

import io
import os

import pytest

from otg_mcp.client_capture import get_capture, start_capture, stop_capture


class FakeCaptureControl:
    """Stand-in for ``control_state().port.capture``."""

    START = "START"
    STOP = "STOP"

    def __init__(self):
        """Start out with nothing selected, as snappi does."""
        self.state = None
        self.port_names = None


class FakePortControl:
    """Stand-in for ``control_state().port``."""

    CAPTURE = "CAPTURE"

    def __init__(self):
        """Create the nested capture control state."""
        self.choice = None
        self.capture = FakeCaptureControl()


class FakeControlState:
    """Stand-in for the object returned by ``api.control_state()``."""

    PORT = "PORT"

    def __init__(self):
        """Create the nested port control state."""
        self.choice = None
        self.port = FakePortControl()


class FakeCaptureRequest:
    """Stand-in for the object returned by ``api.capture_request()``."""

    def __init__(self):
        """Start with no port selected."""
        self.port_name = None


class FakeResult:
    """A ``set_control_state`` result, optionally carrying warnings."""

    def __init__(self, warnings=None):
        """Attach warnings only when given, so ``hasattr`` can be exercised."""
        if warnings is not None:
            self.warnings = warnings


class FakeApi:
    """Minimal fake snappi API client recording calls made against it."""

    def __init__(self, result=None, pcap_bytes=b"", raise_on=None):
        """Configure the canned responses and optional failure point.

        Args:
            result: Object returned by ``set_control_state``.
            pcap_bytes: Payload returned by ``get_capture``.
            raise_on: Name of the method that should raise instead of returning.
        """
        self.result = result if result is not None else FakeResult()
        self.pcap_bytes = pcap_bytes
        self.raise_on = raise_on
        self.applied_states = []
        self.capture_requests = []

    def _maybe_raise(self, name):
        """Raise a RuntimeError if this method is the configured failure point."""
        if self.raise_on == name:
            raise RuntimeError(f"{name} blew up")

    def control_state(self):
        """Return a fresh control state object."""
        self._maybe_raise("control_state")
        return FakeControlState()

    def set_control_state(self, cs):
        """Record the applied control state and return the canned result."""
        self._maybe_raise("set_control_state")
        self.applied_states.append(cs)
        return self.result

    def capture_request(self):
        """Return a fresh capture request object."""
        self._maybe_raise("capture_request")
        return FakeCaptureRequest()

    def get_capture(self, req):
        """Record the request and return the canned pcap payload as a stream."""
        self._maybe_raise("get_capture")
        self.capture_requests.append(req)
        return io.BytesIO(self.pcap_bytes)


class TestStartCapture:
    """Behaviour of ``start_capture``."""

    def test_single_port_name_is_wrapped_in_a_list(self):
        """A bare string port name becomes a one-element list.

        Callers may pass either form; snappi only accepts a list, so a string that
        leaked through unwrapped would be sent as a list of characters.
        """
        api = FakeApi()

        result = start_capture(api, "p1")

        assert result == {"status": "success", "warnings": []}
        assert api.applied_states[0].port.capture.port_names == ["p1"]

    def test_control_state_choices_are_set_for_starting_capture(self):
        """All three nested choices plus START are set before applying state.

        Snappi rejects a control state where any level of the choice chain is
        unset, so this is the contract that makes capture work at all.
        """
        api = FakeApi()

        result = start_capture(api, ["p1", "p2"])

        assert result["status"] == "success"
        applied = api.applied_states[0]
        assert applied.choice == FakeControlState.PORT
        assert applied.port.choice == FakePortControl.CAPTURE
        assert applied.port.capture.state == FakeCaptureControl.START
        assert applied.port.capture.port_names == ["p1", "p2"]

    def test_warnings_from_the_target_are_returned(self):
        """Warnings reported by the generator are surfaced to the caller.

        Starting capture often succeeds with warnings (for example a port already
        capturing), and dropping them would hide that from the operator.
        """
        api = FakeApi(result=FakeResult(warnings=["already capturing"]))

        result = start_capture(api, "p1")

        assert result == {"status": "success", "warnings": ["already capturing"]}

    def test_result_without_warnings_attribute_yields_empty_warnings(self):
        """A result object lacking ``warnings`` still produces an empty list.

        Older snappi releases return results with no warnings attribute at all,
        and the response shape must not change because of that.
        """
        api = FakeApi(result=FakeResult())

        result = start_capture(api, "p1")

        assert result == {"status": "success", "warnings": []}

    def test_failure_is_reported_as_an_error_dictionary(self):
        """An exception from snappi becomes a status/error dictionary.

        The MCP tool layer reports failures in-band rather than raising, so this
        function must never propagate an exception.
        """
        api = FakeApi(raise_on="set_control_state")

        result = start_capture(api, "p1")

        assert result["status"] == "error"
        assert "set_control_state blew up" in result["error"]


class TestStopCapture:
    """Behaviour of ``stop_capture``."""

    def test_single_port_name_is_wrapped_in_a_list(self):
        """A bare string port name becomes a one-element list, as for start."""
        api = FakeApi()

        result = stop_capture(api, "p1")

        assert result == {"status": "success", "warnings": []}
        assert api.applied_states[0].port.capture.port_names == ["p1"]

    def test_control_state_choices_are_set_for_stopping_capture(self):
        """Stopping uses the same choice chain but the STOP state.

        Using START here would silently restart capture instead of stopping it.
        """
        api = FakeApi()

        result = stop_capture(api, ["p1", "p2"])

        assert result["status"] == "success"
        applied = api.applied_states[0]
        assert applied.choice == FakeControlState.PORT
        assert applied.port.choice == FakePortControl.CAPTURE
        assert applied.port.capture.state == FakeCaptureControl.STOP
        assert applied.port.capture.port_names == ["p1", "p2"]

    def test_warnings_from_the_target_are_returned(self):
        """Warnings reported while stopping are surfaced to the caller."""
        api = FakeApi(result=FakeResult(warnings=["capture was not running"]))

        result = stop_capture(api, ["p1"])

        assert result == {"status": "success", "warnings": ["capture was not running"]}

    def test_result_without_warnings_attribute_yields_empty_warnings(self):
        """A result object lacking ``warnings`` still produces an empty list."""
        api = FakeApi(result=FakeResult())

        result = stop_capture(api, ["p1"])

        assert result == {"status": "success", "warnings": []}

    def test_failure_is_reported_as_an_error_dictionary(self):
        """An exception from snappi becomes a status/error dictionary."""
        api = FakeApi(raise_on="control_state")

        result = stop_capture(api, "p1")

        assert result["status"] == "error"
        assert "control_state blew up" in result["error"]


class TestGetCapture:
    """Behaviour of ``get_capture``."""

    def test_capture_bytes_are_written_to_a_generated_pcap_file(self, tmp_path):
        """Captured bytes land on disk and the reported metadata matches the file.

        The returned ``file_path``/``size_bytes`` are what an operator uses to
        find and open the capture, so they must describe the file actually
        written.
        """
        payload = b"\xd4\xc3\xb2\xa1payload"
        api = FakeApi(pcap_bytes=payload)

        result = get_capture(api, "p1", output_dir=str(tmp_path))

        assert result["status"] == "success"
        assert result["port"] == "p1"
        assert result["capture_id"].startswith("capture_p1_")
        assert result["capture_id"].endswith(".pcap")
        assert result["file_path"] == os.path.join(tmp_path, result["capture_id"])
        assert result["size_bytes"] == len(payload)
        with open(result["file_path"], "rb") as written:
            assert written.read() == payload
        assert api.capture_requests[0].port_name == "p1"

    def test_generated_filenames_are_unique_per_call(self, tmp_path):
        """Two captures on the same port do not overwrite each other.

        The auto-generated name carries a uuid suffix precisely so repeated
        captures accumulate rather than clobber.
        """
        api = FakeApi(pcap_bytes=b"one")

        first = get_capture(api, "p1", output_dir=str(tmp_path))
        second = get_capture(api, "p1", output_dir=str(tmp_path))

        assert first["file_path"] != second["file_path"]

    def test_custom_filename_gains_a_pcap_extension(self, tmp_path):
        """A custom name without an extension is saved as ``<name>.pcap``.

        Tools that open captures dispatch on the extension, so it is added for
        the caller rather than left off.
        """
        api = FakeApi(pcap_bytes=b"data")

        result = get_capture(api, "p1", output_dir=str(tmp_path), filename="mycapture")

        assert result["capture_id"] == "mycapture.pcap"
        assert os.path.exists(os.path.join(tmp_path, "mycapture.pcap"))

    def test_custom_filename_with_extension_is_left_alone(self, tmp_path):
        """A custom name already ending in ``.pcap`` is not doubled up."""
        api = FakeApi(pcap_bytes=b"data")

        result = get_capture(api, "p1", output_dir=str(tmp_path), filename="mine.pcap")

        assert result["capture_id"] == "mine.pcap"
        assert result["file_path"] == os.path.join(tmp_path, "mine.pcap")

    def test_missing_output_directory_is_created(self, tmp_path):
        """A nested output directory that does not exist yet is created.

        Callers pass a per-run directory, so requiring them to pre-create it
        would turn every first capture into an error.
        """
        target_dir = tmp_path / "runs" / "capture-1"
        api = FakeApi(pcap_bytes=b"data")

        result = get_capture(api, "p1", output_dir=str(target_dir))

        assert result["status"] == "success"
        assert target_dir.is_dir()

    def test_empty_capture_still_produces_a_file(self, tmp_path):
        """A port that captured nothing yields a zero-byte file, not an error.

        An empty capture is a legitimate result (no matching traffic) and must be
        distinguishable from a failure to retrieve the capture.
        """
        api = FakeApi(pcap_bytes=b"")

        result = get_capture(api, "p1", output_dir=str(tmp_path))

        assert result["status"] == "success"
        assert result["size_bytes"] == 0
        assert os.path.exists(result["file_path"])

    def test_output_directory_defaults_to_tmp(self):
        """Omitting ``output_dir`` writes into ``/tmp``.

        The default is part of the tool contract: clients that pass no directory
        are told where the file went, so the documented default is pinned.
        """
        api = FakeApi(pcap_bytes=b"data")

        result = get_capture(api, "p1", filename="otg-mcp-default-dir-test.pcap")

        try:
            assert result["status"] == "success"
            assert result["file_path"] == os.path.join(
                "/tmp", "otg-mcp-default-dir-test.pcap"
            )
            assert os.path.exists(result["file_path"])
        finally:
            if result["file_path"] and os.path.exists(result["file_path"]):
                os.remove(result["file_path"])

    def test_retrieval_failure_reports_an_error_with_no_file_path(self, tmp_path):
        """A failure fetching the capture returns error metadata, not a path.

        ``file_path`` and ``capture_id`` are explicitly nulled so a client cannot
        try to open a file that was never written.
        """
        api = FakeApi(raise_on="get_capture")

        result = get_capture(api, "p1", output_dir=str(tmp_path))

        assert result["status"] == "error"
        assert "get_capture blew up" in result["error"]
        assert result["port"] == "p1"
        assert result["file_path"] is None
        assert result["capture_id"] is None

    def test_unwritable_output_directory_reports_an_error(self, tmp_path):
        """An output directory that is really a file is reported as an error.

        Directory creation happens before any device call, and that failure must
        follow the same in-band error contract.
        """
        blocker = tmp_path / "not-a-directory"
        blocker.write_bytes(b"")
        api = FakeApi(pcap_bytes=b"data")

        result = get_capture(api, "p1", output_dir=str(blocker))

        assert result["status"] == "error"
        assert result["file_path"] is None


@pytest.mark.parametrize("capture_fn", [start_capture, stop_capture])
def test_port_name_list_is_copied_not_aliased(capture_fn):
    """The caller's list is copied before being handed to snappi.

    Aliasing the caller's list would let later mutations on their side change the
    control state that was already applied.
    """
    api = FakeApi()
    ports = ["p1"]

    capture_fn(api, ports)
    ports.append("p2")

    assert api.applied_states[0].port.capture.port_names == ["p1"]
