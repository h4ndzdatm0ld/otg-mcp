"""OTG MCP Server implementation.

This module implements a Model Context Protocol (MCP) server that provides access to
Open Traffic Generator (OTG) APIs via direct connections to traffic generators.
"""

import argparse
import logging
import sys
import traceback
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from fastmcp import FastMCP
from pydantic import Field

from otg_mcp.client import OtgClient
from otg_mcp.config import Config
from otg_mcp.models import (
    CaptureResponse,
    ConfigResponse,
    ControlResponse,
    HealthStatus,
    MetricsResponse,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class OtgMcpServer:
    """OTG MCP Server that provides access to traffic generators.

    This server provides a unified API that adheres to the
    Open Traffic Generator specification.

    Attributes:
        mcp: FastMCP instance that handles tool registration and execution
    """

    def __init__(self, config_file: str):
        """Initialize the server and register all tools and endpoints.

        Args:
            config_file: Path to the configuration file
        """
        try:
            logger.info("Initializing config with the provided file")
            config = Config(config_file)

            logger.info("Setting up logging configuration")
            config.setup_logging()

            logger.info("Creating the FastMCP instance")
            self.mcp: FastMCP = FastMCP("otg-mcp-server", log_level="INFO")

            logger.info("Initializing schema registry")
            custom_schema_path = None
            if hasattr(config, "schemas") and config.schemas.schema_path:
                custom_schema_path = config.schemas.schema_path
                logger.info(
                    f"Using custom schema path from config: {custom_schema_path}"
                )

            from otg_mcp.schema_registry import SchemaRegistry

            self.schema_registry = SchemaRegistry(custom_schema_path)

            logger.info("Initializing OTG client with schema registry")
            self.client = OtgClient(config=config, schema_registry=self.schema_registry)

            logger.info("Registering all endpoints")
            self._register_tools()

        except Exception as e:
            logger.critical(f"Failed to initialize server: {str(e)}")
            logger.critical(f"Stack trace: {traceback.format_exc()}")
            raise

    def _register_tools(self):
        """Automatically register all methods starting with 'tool_' as MCP tools."""
        logger.info("Discovering and registering tools")

        count = 0
        for attr_name in dir(self):
            logger.debug(f"Checking attribute: {attr_name}")
            if attr_name.startswith("_") or not callable(getattr(self, attr_name)):
                logger.debug(f"Skipping non-tool attribute: {attr_name}")
                continue

            if attr_name.startswith("tool_"):
                method = getattr(self, attr_name)
                tool_name = attr_name[5:]
                logger.debug(
                    f"Found tool method: {attr_name}, registering as: {tool_name}"
                )
                logger.info(f"Registering tool: {tool_name}")
                self.mcp.add_tool(method, name=tool_name)
                count += 1

        logger.info(f"Registered {count} tools successfully")

    async def tool_set_config(
        self,
        config: Annotated[
            Dict[str, Any], Field(description="The configuration to set")
        ],
        target: Annotated[
            str, Field(description="Target traffic generator hostname or IP address")
        ],
    ) -> ConfigResponse:
        """Set the configuration of the traffic generator and retrieve the applied configuration."""
        logger.info(f"Tool: set_config for target {target}")
        return await self.client.set_config(target=target, config=config)

    async def tool_get_config(
        self, target: Annotated[str, Field(description="Target traffic generator")]
    ) -> ConfigResponse:
        """Get the current configuration of the traffic generator."""
        logger.info(f"Tool: get_config for target {target}")
        return await self.client.get_config(target=target)

    async def tool_get_metrics(
        self,
        flow_names: Annotated[
            Optional[Union[str, List[str]]],
            Field(description="Optional flow name(s) to get metrics for"),
        ] = None,
        port_names: Annotated[
            Optional[Union[str, List[str]]],
            Field(description="Optional port name(s) to get metrics for"),
        ] = None,
        target: Annotated[
            Optional[str], Field(description="Optional target traffic generator")
        ] = None,
    ) -> MetricsResponse:
        """Get metrics from the traffic generator."""
        logger.info(
            f"Tool: get_metrics for target {target}, flow_names={flow_names}, port_names={port_names}"
        )
        return await self.client.get_metrics(
            flow_names=flow_names, port_names=port_names, target=target
        )

    async def tool_start_traffic(
        self, target: Annotated[str, Field(description="Target traffic generator")]
    ) -> ControlResponse:
        """Start traffic generation."""
        logger.info(f"Tool: start_traffic for target {target}")
        return await self.client.start_traffic(target=target)

    async def tool_stop_traffic(
        self, target: Annotated[str, Field(description="Target traffic generator")]
    ) -> ControlResponse:
        """Stop traffic generation."""
        logger.info(f"Tool: stop_traffic for target {target}")
        return await self.client.stop_traffic(target=target)

    async def tool_start_capture(
        self,
        port_name: Annotated[
            str, Field(description="Name of the port to capture packets on")
        ],
        target: Annotated[str, Field(description="Target traffic generator")],
    ) -> CaptureResponse:
        """Start packet capture on a port."""
        logger.info(f"Tool: start_capture for port {port_name} on target {target}")
        return await self.client.start_capture(target=target, port_name=port_name)

    async def tool_stop_capture(
        self,
        port_name: Annotated[
            str, Field(description="Name of the port to stop capturing packets on")
        ],
        target: Annotated[str, Field(description="Target traffic generator")],
    ) -> CaptureResponse:
        """Stop packet capture on a port."""
        logger.info(f"Tool: stop_capture for port {port_name} on target {target}")
        return await self.client.stop_capture(target=target, port_name=port_name)

    async def tool_get_capture(
        self,
        port_name: Annotated[
            str, Field(description="Name of the port to get capture from")
        ],
        target: Annotated[str, Field(description="Target traffic generator")],
        output_dir: Annotated[
            Optional[str],
            Field(description="Directory to save the capture file (default: /tmp)"),
        ] = None,
    ) -> CaptureResponse:
        """
        Get packet capture from a port and save it to a file.

        The capture data is saved as a .pcap file that can be opened with tools like Wireshark.
        """
        logger.info(f"Tool: get_capture for port {port_name} on target {target}")
        return await self.client.get_capture(
            target=target, port_name=port_name, output_dir=output_dir
        )

    async def tool_get_available_targets(self) -> Dict[str, Dict[str, Any]]:
        """Get all available traffic generator targets with comprehensive information."""
        logger.info("Tool: get_available_targets")
        return await self.client.get_available_targets()

    async def tool_health(
        self,
        target: Annotated[
            Optional[str],
            Field(
                description="Optional target to check. If None, checks all available targets"
            ),
        ] = None,
    ) -> HealthStatus:
        """Health check tool."""
        logger.info(f"Tool: health for {target or 'all targets'}")
        return await self.client.health(target)

    async def tool_get_schemas_for_target(
        self,
        target_name: Annotated[str, Field(description="Name of the target")],
        schema_names: Annotated[
            List[str],
            Field(
                description='List of schema names to retrieve (e.g., ["Flow", "Port"] or ["components.schemas.Flow"])'
            ),
        ],
    ) -> Dict[str, Any]:
        """Get schemas for a specific target's API version."""
        logger.info(
            f"Tool: get_schemas_for_target for {target_name}, schemas {schema_names}"
        )
        return await self.client.get_schemas_for_target(target_name, schema_names)

    async def tool_list_schemas_for_target(
        self, target_name: Annotated[str, Field(description="Name of the target")]
    ) -> List[str]:
        """List available schemas for a specific target's API version."""
        logger.info(f"Tool: list_schemas_for_target for {target_name}")
        return await self.client.list_schemas_for_target(target_name)

    def run(self, transport: Literal["stdio", "sse"] = "stdio"):
        """Run the server with the specified transport mechanism.

        Args:
            transport: Transport to use (stdio or sse)
        """
        try:
            self.mcp.run(transport=transport)
        except Exception as e:
            logger.critical(f"Error running server: {str(e)}")
            logger.critical(f"Stack trace: {traceback.format_exc()}")
            raise


def run_server() -> None:
    """Run the OTG MCP Server."""
    try:
        logger.info("Parsing command-line arguments")
        parser = argparse.ArgumentParser(description="OTG MCP Server")
        parser.add_argument(
            "--config-file",
            type=str,
            required=True,
            help="Path to the traffic generator configuration file",
        )
        parser.add_argument(
            "--transport",
            type=str,
            choices=["stdio", "sse"],
            default="stdio",
            help="Transport mechanism to use (stdio or sse)",
        )

        args = parser.parse_args()

        logger.info("Initializing and running the server with the config file")
        server = OtgMcpServer(config_file=args.config_file)
        server.run(transport=args.transport)  # type: ignore
    except Exception as e:
        logger.critical(f"Server failed with error: {str(e)}")
        logger.critical(f"Stack trace: {traceback.format_exc()}")
        sys.exit(1)


def main() -> None:
    """Legacy entry point for backward compatibility."""
    run_server()


if __name__ == "__main__":
    run_server()
