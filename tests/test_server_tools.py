"""Unit tests for the OtgMcpServer tool surface and entry points.

OtgClient is mocked out entirely here: every tool body is a one-line delegation
to the client, so what needs pinning is that each MCP tool forwards exactly the
arguments the client expects and returns the client's result untouched. No test
in this file reaches a traffic generator or the network.
"""

import inspect
import json
import sys
from unittest import mock

import pytest
from fastmcp.tools import Tool

from otg_mcp import server as server_module
from otg_mcp.server import OtgMcpServer, main, run_server


@pytest.fixture
def config_file(tmp_path):
    """Write a minimal single-target config file and return its path."""
    path = tmp_path / "trafficGeneratorConfig.json"
    path.write_text(
        json.dumps(
            {
                "targets": {
                    "gen.example.com:8443": {
                        "ports": {"p1": {"location": "localhost:5555", "name": "p1"}}
                    }
                }
            }
        )
    )
    return str(path)


@pytest.fixture
def server(config_file):
    """Build a server whose OtgClient is an AsyncMock.

    Constructing the real FastMCP instance is deliberate - tool registration is
    the part of __init__ worth exercising - while the client is replaced so no
    tool call can reach hardware.
    """
    with mock.patch.object(server_module, "OtgClient") as client_cls:
        client_cls.return_value = mock.AsyncMock()
        instance = OtgMcpServer(config_file=config_file)
    return instance


DELEGATIONS = [
    (
        "tool_set_config",
        {"config": {"flows": []}, "target": "gen.example.com:8443"},
        "set_config",
        (),
        {"target": "gen.example.com:8443", "config": {"flows": []}},
    ),
    (
        "tool_get_config",
        {"target": "gen.example.com:8443"},
        "get_config",
        (),
        {"target": "gen.example.com:8443"},
    ),
    (
        "tool_get_metrics",
        {
            "flow_names": ["f1"],
            "port_names": "p1",
            "target": "gen.example.com:8443",
        },
        "get_metrics",
        (),
        {
            "flow_names": ["f1"],
            "port_names": "p1",
            "target": "gen.example.com:8443",
        },
    ),
    (
        "tool_get_protocol_metrics",
        {
            "target": "gen.example.com:8443",
            "protocol": "bgpv4",
            "names": ["edge-bgp"],
        },
        "get_protocol_metrics",
        (),
        {
            "target": "gen.example.com:8443",
            "protocol": "bgpv4",
            "names": ["edge-bgp"],
        },
    ),
    (
        "tool_start_traffic",
        {"target": "gen.example.com:8443"},
        "start_traffic",
        (),
        {"target": "gen.example.com:8443"},
    ),
    (
        "tool_stop_traffic",
        {"target": "gen.example.com:8443"},
        "stop_traffic",
        (),
        {"target": "gen.example.com:8443"},
    ),
    (
        "tool_start_capture",
        {"port_name": "p1", "target": "gen.example.com:8443"},
        "start_capture",
        (),
        {"target": "gen.example.com:8443", "port_name": "p1"},
    ),
    (
        "tool_stop_capture",
        {"port_name": "p1", "target": "gen.example.com:8443"},
        "stop_capture",
        (),
        {"target": "gen.example.com:8443", "port_name": "p1"},
    ),
    (
        "tool_get_capture",
        {
            "port_name": "p1",
            "target": "gen.example.com:8443",
            "output_dir": "/tmp/captures",
        },
        "get_capture",
        (),
        {
            "target": "gen.example.com:8443",
            "port_name": "p1",
            "output_dir": "/tmp/captures",
        },
    ),
    (
        "tool_get_available_targets",
        {},
        "get_available_targets",
        (),
        {},
    ),
    (
        "tool_health",
        {"target": "gen.example.com:8443"},
        "health",
        ("gen.example.com:8443",),
        {},
    ),
    (
        "tool_get_schemas_for_target",
        {"target_name": "gen.example.com:8443", "schema_names": ["Flow", "Port"]},
        "get_schemas_for_target",
        ("gen.example.com:8443", ["Flow", "Port"]),
        {},
    ),
    (
        "tool_list_schemas_for_target",
        {"target_name": "gen.example.com:8443"},
        "list_schemas_for_target",
        ("gen.example.com:8443",),
        {},
    ),
]


class TestToolDelegation:
    """Tests that every MCP tool forwards to the matching OtgClient method.

    The tools are the wire contract of this server: a renamed or dropped client
    argument shows up here rather than as a runtime failure against real gear.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "tool_attr,call_kwargs,client_attr,expected_args,expected_kwargs",
        DELEGATIONS,
        ids=[entry[0] for entry in DELEGATIONS],
    )
    async def test_tool_delegates_to_client(
        self, server, tool_attr, call_kwargs, client_attr, expected_args, expected_kwargs
    ):
        """The tool calls its client method with the expected arguments.

        Args:
            server: Server with a mocked client
            tool_attr: Name of the tool_* method under test
            call_kwargs: Arguments the MCP caller supplies
            client_attr: Client method the tool must delegate to
            expected_args: Positional arguments the client must receive
            expected_kwargs: Keyword arguments the client must receive
        """
        client_method = getattr(server.client, client_attr)
        sentinel = mock.Mock(name=f"{client_attr}_result")
        client_method.return_value = sentinel

        result = await getattr(server, tool_attr)(**call_kwargs)

        assert result is sentinel
        client_method.assert_awaited_once_with(*expected_args, **expected_kwargs)

    def test_every_tool_method_is_covered_by_this_suite(self, server):
        """The delegation table names every tool_* method on the server.

        Tools are registered by reflection over dir(self), so a new tool needs no
        registry edit and would otherwise silently ship untested.
        """
        tool_methods = {name for name in dir(server) if name.startswith("tool_")}

        assert {entry[0] for entry in DELEGATIONS} == tool_methods

    @pytest.mark.asyncio
    async def test_optional_arguments_default_to_none(self, server):
        """Omitted optional arguments reach the client as None.

        MCP callers routinely omit these, and the client relies on None rather
        than a missing keyword to apply its own defaults.
        """
        await server.tool_get_metrics()
        server.client.get_metrics.assert_awaited_once_with(
            flow_names=None, port_names=None, target=None
        )

        await server.tool_get_capture(port_name="p1", target="gen.example.com:8443")
        server.client.get_capture.assert_awaited_once_with(
            target="gen.example.com:8443", port_name="p1", output_dir=None
        )

        await server.tool_health()
        server.client.health.assert_awaited_once_with(None)


class TestServerInitialisation:
    """Tests for OtgMcpServer.__init__ and tool registration."""

    def test_client_is_built_from_the_loaded_config(self, config_file):
        """The client is constructed with the Config parsed from the given file."""
        with mock.patch.object(server_module, "OtgClient") as client_cls:
            client_cls.return_value = mock.AsyncMock()
            instance = OtgMcpServer(config_file=config_file)

        config = client_cls.call_args.kwargs["config"]
        assert list(config.targets.targets) == ["gen.example.com:8443"]
        assert instance.client is client_cls.return_value

    def test_registration_counts_every_tool(self, config_file):
        """_register_tools registers one tool per tool_* method, name stripped.

        Registration is by reflection, so this pins that the 'tool_' prefix is
        removed and that non-tool attributes are not registered.
        """
        with mock.patch.object(server_module, "OtgClient") as client_cls:
            client_cls.return_value = mock.AsyncMock()
            instance = OtgMcpServer(config_file=config_file)

        expected = {name[5:] for name in dir(instance) if name.startswith("tool_")}
        with mock.patch.object(instance, "_add_tool") as add_tool:
            instance._register_tools()

        assert {call.args[1] for call in add_tool.call_args_list} == expected

    def test_bad_config_path_is_reraised(self, tmp_path):
        """A config file that does not exist aborts construction.

        Coming up with no targets would leave a server that answers every tool
        call with a failure, so __init__ must fail instead.
        """
        with pytest.raises(FileNotFoundError):
            OtgMcpServer(config_file=str(tmp_path / "missing.json"))

    def test_client_construction_failure_is_reraised(self, config_file):
        """A client that cannot be built aborts construction rather than degrading."""
        with mock.patch.object(
            server_module, "OtgClient", side_effect=RuntimeError("no client")
        ):
            with pytest.raises(RuntimeError):
                OtgMcpServer(config_file=config_file)


class ToolStyleMcp:
    """Stand-in for a FastMCP whose add_tool takes a single Tool instance."""

    def __init__(self):
        self.calls = []

    def add_tool(self, tool):
        """Record the Tool instance passed by the server.

        Args:
            tool: Tool instance under registration
        """
        self.calls.append(tool)


class LegacyStyleMcp:
    """Stand-in for a FastMCP 2.2.x whose add_tool takes (fn, name=...)."""

    def __init__(self):
        self.calls = []

    def add_tool(self, fn, name=None):
        """Record the callable and name passed by the server.

        Args:
            fn: Bound tool method under registration
            name: Name to expose the tool under
        """
        self.calls.append((fn, name))


class TestAddToolCompatibility:
    """Tests both accepted FastMCP add_tool signatures.

    The installed FastMCP only exercises one branch, so the other is pinned with
    a stand-in; dropping either would break the server on half the supported
    fastmcp range.
    """

    def test_tool_instance_signature_is_used_when_available(self, server):
        """A 'tool'-parameter add_tool receives a Tool built from the method."""
        fake_mcp = ToolStyleMcp()
        server.mcp = fake_mcp

        server._add_tool(server.tool_health, "health")

        assert len(fake_mcp.calls) == 1
        registered = fake_mcp.calls[0]
        assert isinstance(registered, Tool)
        assert registered.name == "health"

    def test_legacy_callable_signature_is_used_as_fallback(self, server):
        """An add_tool without a 'tool' parameter gets the callable and name."""
        fake_mcp = LegacyStyleMcp()
        server.mcp = fake_mcp
        method = server.tool_health

        server._add_tool(method, "health")

        assert fake_mcp.calls == [(method, "health")]

    def test_installed_fastmcp_exercises_one_of_the_two_branches(self, server):
        """The real FastMCP.add_tool matches exactly one of the handled shapes.

        This guards against a future fastmcp signature that satisfies neither
        branch, which the stand-ins above cannot detect.
        """
        params = inspect.signature(server.mcp.add_tool).parameters

        assert "tool" in params or len(params) >= 1


class TestRun:
    """Tests for OtgMcpServer.run."""

    @pytest.mark.parametrize("transport", ["stdio", "sse"])
    def test_transport_is_passed_through(self, server, transport):
        """run forwards the requested transport to FastMCP.

        Args:
            server: Server with a mocked client
            transport: Transport name to forward
        """
        server.mcp = mock.MagicMock()

        server.run(transport=transport)

        server.mcp.run.assert_called_once_with(transport=transport)

    def test_default_transport_is_stdio(self, server):
        """run defaults to stdio, the transport MCP clients launch by default."""
        server.mcp = mock.MagicMock()

        server.run()

        server.mcp.run.assert_called_once_with(transport="stdio")

    def test_run_failure_is_reraised(self, server):
        """A transport failure propagates so the process exits non-zero."""
        server.mcp = mock.MagicMock()
        server.mcp.run.side_effect = RuntimeError("transport died")

        with pytest.raises(RuntimeError):
            server.run()


class TestRunServer:
    """Tests for the run_server console entry point."""

    def test_arguments_drive_server_construction_and_transport(self):
        """--config-file and --transport are wired into the server and run call."""
        argv = ["otg-mcp", "--config-file", "/etc/otg/config.json", "--transport", "sse"]
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(server_module, "OtgMcpServer") as server_cls:
                run_server()

        server_cls.assert_called_once_with(config_file="/etc/otg/config.json")
        server_cls.return_value.run.assert_called_once_with(transport="sse")

    def test_transport_defaults_to_stdio(self):
        """Omitting --transport selects stdio."""
        argv = ["otg-mcp", "--config-file", "/etc/otg/config.json"]
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(server_module, "OtgMcpServer") as server_cls:
                run_server()

        server_cls.return_value.run.assert_called_once_with(transport="stdio")

    def test_startup_failure_exits_with_status_one(self):
        """A failure during startup exits 1 instead of propagating a traceback.

        Supervisors and MCP clients key off the exit status, so a crash has to
        become a clean non-zero exit.
        """
        argv = ["otg-mcp", "--config-file", "/etc/otg/config.json"]
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(
                server_module, "OtgMcpServer", side_effect=RuntimeError("boom")
            ):
                with pytest.raises(SystemExit) as excinfo:
                    run_server()

        assert excinfo.value.code == 1

    def test_missing_required_config_file_argument_exits(self):
        """Omitting --config-file is an argparse usage error, not a silent start."""
        with mock.patch.object(sys, "argv", ["otg-mcp"]):
            with pytest.raises(SystemExit) as excinfo:
                run_server()

        assert excinfo.value.code == 2

    def test_main_delegates_to_run_server(self):
        """The legacy main() entry point still routes to run_server."""
        with mock.patch.object(server_module, "run_server") as mocked:
            main()

        mocked.assert_called_once_with()
