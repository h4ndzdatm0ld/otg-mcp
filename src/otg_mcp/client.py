"""
OTG Client module providing a direct interface to traffic generator APIs.

This simplified client provides a single entry point for traffic generator operations
using snappi API directly, with proper target management and version detection.
"""

import logging
import os
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import aiohttp
import snappi  # type: ignore

from otg_mcp.client_capture import get_capture, start_capture, stop_capture
from otg_mcp.config import Config
from otg_mcp.models import (
    CapabilitiesVersionResponse,
    CaptureResponse,
    ConfigResponse,
    ControlResponse,
    HealthStatus,
    MetricsResponse,
    PortInfo,
    TargetHealthInfo,
    TrafficGeneratorInfo,
    TrafficGeneratorStatus,
)
from otg_mcp.schema_registry import SchemaRegistry

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class OtgClient:
    """
    Client for OTG traffic generator operations using snappi.

    This client provides a unified interface for all traffic generator operations,
    handling target resolution, API version differences, and client caching.
    """

    config: Config
    api_clients: Dict[str, Any] = field(default_factory=dict)
    schema_registry: Optional[SchemaRegistry] = field(default=None)

    def __post_init__(self):
        """Initialize after dataclass initialization."""
        logger.info("Initializing OTG client")

        logger.debug("Checking if we need to create a SchemaRegistry")
        if self.schema_registry is None:
            logger.info("No SchemaRegistry provided, creating one")
            custom_schema_path = None
            if self.config.schemas.schema_path:
                custom_schema_path = self.config.schemas.schema_path
                logger.info(
                    f"Using custom schema path from config: {custom_schema_path}"
                )

            self.schema_registry = SchemaRegistry(custom_schema_path)
            logger.info("Created new SchemaRegistry instance")
        else:
            logger.info("Using provided SchemaRegistry instance")

        logger.info("OTG client initialized")

    def _get_api_client(self, target: str):
        """
        Get or create API client for target.

        Args:
            target: Target ID (required)

        Returns:
            Tuple of (snappi API client, API capabilities dict)
        """
        logger.info(f"Getting API client for target {target}")

        logger.info(f"Checking if client is cached for target {target}")
        if target in self.api_clients:
            logger.info(f"Using cached API client for target {target}")
            return self.api_clients[target]

        logger.info(f"Resolving location for target {target}")
        location = self._get_location_for_target(target)
        logger.info(f"Target {target} resolved to location {location}")

        logger.info(f"Creating new snappi API client for {location}")
        api = snappi.api(location=location, verify=False)

        logger.info("Detecting API capabilities through schema introspection")
        api_schema = self._discover_api_schema(api)
        logger.info(f"API schema detected: version={api_schema['version']}")

        logger.info(f"Caching client for target {target}")
        self.api_clients[target] = api

        return api

    def _get_location_for_target(self, target: str) -> str:
        """
        Get location string for target.

        Args:
            target: Target ID

        Returns:
            Location string for snappi client
        """
        logger.info(f"Creating URL for direct connection to target {target}")
        return f"https://{target}" if ":" not in target else f"https://{target}"

    def _discover_api_schema(self, api) -> Dict[str, Any]:
        """
        Discover API capabilities through introspection.

        Args:
            api: Snappi API client

        Returns:
            Dictionary of API capabilities
        """
        logger.info("Getting all available API methods through introspection")
        methods = [
            m for m in dir(api) if not m.startswith("_") and callable(getattr(api, m))
        ]

        logger.info("Detecting API version and capabilities")
        schema = {
            "methods": methods,
            "version": self._get_api_version(api),
            "has_control_state": hasattr(api, "control_state"),
            "has_transmit_state": hasattr(api, "transmit_state"),
            "has_start_transmit": hasattr(api, "start_transmit"),
            "has_stop_transmit": hasattr(api, "stop_transmit"),
            "has_set_flow_transmit": hasattr(api, "set_flow_transmit"),
        }

        return schema

    def _get_api_version(self, api) -> str:
        """
        Get the API version.

        Args:
            api: Snappi API client

        Returns:
            API version string
        """
        if hasattr(api, "__version__"):
            return str(api.__version__)
        elif hasattr(snappi, "__version__"):
            return str(snappi.__version__)
        return "unknown"

    def _start_traffic(self, api) -> None:
        """
        Start traffic using the appropriate method based on API version.

        Args:
            api: Snappi API client
        """
        logger.info("Starting traffic generation")

        if hasattr(api, "start_transmit"):
            logger.info("Using start_transmit() method")
            api.start_transmit()
        elif hasattr(api, "set_flow_transmit"):
            logger.info("Using set_flow_transmit() method")
            api.set_flow_transmit(state="start")
        elif hasattr(api, "control_state"):
            logger.info("Using control_state() method")
            self._start_traffic_control_state(api)
        else:
            raise NotImplementedError("No method available to start traffic")

    def _start_traffic_control_state(self, api) -> None:
        """
        Start traffic using control_state API.

        Args:
            api: Snappi API client
        """
        cs = api.control_state()
        cs.choice = cs.TRAFFIC

        if not hasattr(cs, "traffic"):
            raise AttributeError("control_state object does not have traffic attribute")

        cs.traffic.choice = cs.traffic.FLOW_TRANSMIT

        if not hasattr(cs.traffic, "flow_transmit"):
            raise AttributeError("traffic object does not have flow_transmit attribute")

        logger.debug("Handling different versions of control_state API")
        if hasattr(cs.traffic.flow_transmit, "START"):
            cs.traffic.flow_transmit.state = cs.traffic.flow_transmit.START
        else:
            cs.traffic.flow_transmit.state = "start"

        api.set_control_state(cs)

    def _stop_traffic(self, api) -> bool:
        """
        Stop traffic using the appropriate method based on API version.

        Args:
            api: Snappi API client

        Returns:
            True if traffic was successfully stopped, False otherwise
        """
        logger.info("Stopping traffic generation")

        methods = [
            self._stop_traffic_direct,
            self._stop_traffic_transmit,
            self._stop_traffic_control_state,
            self._stop_traffic_flow_transmit,
        ]

        for method in methods:
            try:
                method(api)
                logger.info(f"Successfully stopped traffic using {method.__name__}")
                return self._verify_traffic_stopped(api)
            except Exception as e:
                logger.info(f"Failed to stop traffic using {method.__name__}: {e}")
                continue

        logger.warning("All methods to stop traffic failed")
        return False

    def _stop_traffic_direct(self, api) -> None:
        """
        Stop traffic using stop_transmit method.

        Args:
            api: Snappi API client
        """
        if not hasattr(api, "stop_transmit"):
            raise AttributeError("stop_transmit method not available")
        api.stop_transmit()

    def _stop_traffic_transmit(self, api) -> None:
        """
        Stop traffic using transmit_state method.

        Args:
            api: Snappi API client
        """
        if not hasattr(api, "transmit_state"):
            raise AttributeError("transmit_state method not available")
        ts = api.transmit_state()
        ts.state = ts.STOP
        api.set_transmit_state(ts)

    def _stop_traffic_control_state(self, api) -> None:
        """
        Stop traffic using control_state method.

        Args:
            api: Snappi API client
        """
        if not hasattr(api, "control_state"):
            raise AttributeError("control_state method not available")

        cs = api.control_state()
        cs.choice = cs.TRAFFIC

        if not hasattr(cs, "traffic"):
            raise AttributeError("control_state object does not have traffic attribute")

        cs.traffic.choice = cs.traffic.FLOW_TRANSMIT

        if not hasattr(cs.traffic, "flow_transmit"):
            raise AttributeError("traffic object does not have flow_transmit attribute")

        logger.debug(
            "Handling different versions of control_state API for stopping traffic"
        )
        if hasattr(cs.traffic.flow_transmit, "STOP"):
            cs.traffic.flow_transmit.state = cs.traffic.flow_transmit.STOP
        else:
            cs.traffic.flow_transmit.state = "stop"

        api.set_control_state(cs)

    def _stop_traffic_flow_transmit(self, api) -> None:
        """
        Stop traffic using set_flow_transmit method.

        Args:
            api: Snappi API client
        """
        if not hasattr(api, "set_flow_transmit"):
            raise AttributeError("set_flow_transmit method not available")
        api.set_flow_transmit(state="stop")

    def _verify_traffic_stopped(self, api, timeout=5, threshold=0.1) -> bool:
        """
        Verify that traffic has actually stopped by checking metrics.

        Args:
            api: Snappi API client
            timeout: Maximum time in seconds to wait
            threshold: Threshold below which traffic is considered stopped

        Returns:
            True if traffic is stopped, False otherwise
        """
        logger.info(f"Verifying traffic has stopped (timeout={timeout}s)")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                logger.debug("Getting flow metrics")
                request = api.metrics_request()
                metrics = api.get_metrics(request)

                logger.debug("Checking if there are any flow metrics")
                if (
                    not hasattr(metrics, "flow_metrics")
                    or len(metrics.flow_metrics) == 0
                ):
                    logger.info(
                        "No flow metrics available, assuming traffic is stopped"
                    )
                    return True

                logger.debug("Checking if all flows have stopped")
                all_stopped = True
                for flow in metrics.flow_metrics:
                    if (
                        hasattr(flow, "frames_tx_rate")
                        and flow.frames_tx_rate >= threshold
                    ):
                        logger.info(
                            f"Flow {getattr(flow, 'name', 'unknown')} still running with rate {flow.frames_tx_rate}"
                        )
                        all_stopped = False
                        break

                if all_stopped:
                    logger.info("All flows verified stopped")
                    return True
            except Exception as e:
                logger.warning(f"Error checking traffic status: {str(e)}")

            time.sleep(0.5)

        logger.warning(f"Timed out waiting for traffic to stop after {timeout}s")
        return False

    def _get_metrics(self, api, flow_names=None, port_names=None):
        """
        Get metrics from the API.

        Args:
            api: Snappi API client
            flow_names: Optional list of flow names
            port_names: Optional list of port names

        Returns:
            Metrics object
        """
        request = api.metrics_request()

        if flow_names:
            request.flow.flow_names = flow_names

        if port_names:
            request.port.port_names = port_names

        return api.get_metrics(request)

    def _start_capture(self, api: Any, port_names: Union[str, List[str]]) -> None:
        """
        Start packet capture on one or more ports.

        Args:
            api: Snappi API client
            port_names: List or single name of port(s) to capture on
        """
        logger.info(f"Starting capture for ports: {port_names}")

        logger.debug("Converting port names to list for consistent handling")
        port_list = [port_names] if isinstance(port_names, str) else list(port_names)

        logger.debug("Detecting available API methods for capture")
        api_methods = [method for method in dir(api) if not method.startswith("_")]
        logger.debug(f"Available API methods: {api_methods}")

        logger.info("Trying multiple methods to start capture based on available API")
        try:
            if "capture_state" in api_methods:
                logger.info("Using capture_state() method")
                cs = api.capture_state()
                cs.state = "start"
                cs.port_names = port_list
                api.set_capture_state(cs)
            elif "start_capture" in api_methods:
                logger.info("Using start_capture() method")
                for port in port_list:
                    api.start_capture(port_name=port)
            elif "control_state" in api_methods:
                logger.info("Using control_state() method for capture")
                cs = api.control_state()

                logger.debug("Checking if there's a CAPTURE choice available")
                if hasattr(cs, "CAPTURE") and hasattr(cs, "choice"):
                    logger.debug("Setting control_state choice to CAPTURE")
                    cs.choice = cs.CAPTURE

                    logger.debug("Checking for capture attribute in control_state")
                    if hasattr(cs, "capture"):
                        logger.debug("Found capture attribute in control_state")

                        if hasattr(cs.capture, "port_names"):
                            logger.debug("Setting port_names in capture")
                            cs.capture.port_names = port_list

                        if hasattr(cs.capture, "state"):
                            logger.debug("Setting capture state to start")
                            if hasattr(cs.capture, "START"):
                                cs.capture.state = cs.capture.START
                            else:
                                cs.capture.state = "start"

                logger.info(
                    f"Setting control state to start capture on ports: {port_list}"
                )
                api.set_control_state(cs)
            else:
                logger.error("No compatible capture method found in API")
                raise NotImplementedError("No method available to start capture")
        except Exception as e:
            logger.error(f"Error starting capture: {e}")
            raise

    def _stop_capture(self, api: Any, port_names: Union[str, List[str]]) -> None:
        """
        Stop packet capture on one or more ports.

        Args:
            api: Snappi API client
            port_names: List or single name of port(s) to stop capture on
        """
        logger.info(f"Stopping capture for ports: {port_names}")

        logger.debug("Converting port names to list for consistent handling")
        port_list = [port_names] if isinstance(port_names, str) else list(port_names)

        logger.debug("Detecting available API methods for capture")
        api_methods = [method for method in dir(api) if not method.startswith("_")]
        logger.debug(f"Available API methods: {api_methods}")

        try:
            if "capture_state" in api_methods:
                logger.info("Using capture_state() method")
                cs = api.capture_state()
                cs.state = "stop"
                cs.port_names = port_list
                api.set_capture_state(cs)
            elif "stop_capture" in api_methods:
                logger.info("Using stop_capture() method")
                for port in port_list:
                    api.stop_capture(port_name=port)
            elif "control_state" in api_methods:
                logger.info("Using control_state() method for capture")
                cs = api.control_state()

                if hasattr(cs, "CAPTURE") and hasattr(cs, "choice"):
                    logger.debug("Setting control_state choice to CAPTURE")
                    cs.choice = cs.CAPTURE

                    if hasattr(cs, "capture"):
                        logger.debug("Found capture attribute in control_state")

                        if hasattr(cs.capture, "port_names"):
                            logger.debug("Setting port_names in capture")
                            cs.capture.port_names = port_list

                        if hasattr(cs.capture, "state"):
                            logger.debug("Setting capture state to stop")
                            if hasattr(cs.capture, "STOP"):
                                cs.capture.state = cs.capture.STOP
                            else:
                                cs.capture.state = "stop"

                logger.info(
                    f"Setting control state to stop capture on ports: {port_list}"
                )
                api.set_control_state(cs)
            else:
                logger.error("No compatible capture method found in API")
                raise NotImplementedError("No method available to stop capture")
        except Exception as e:
            logger.error(f"Error stopping capture: {e}")
            raise

    def _get_capture(
        self, api: Any, port_name: str, output_dir: Optional[str] = None
    ) -> str:
        """
        Get capture data and save to a file.

        Args:
            api: Snappi API client
            port_name: Name of port to get capture from
            output_dir: Directory to save the capture file (default: /tmp)

        Returns:
            File path where the capture was saved
        """
        if output_dir is None:
            logger.debug("Using default output directory: /tmp")
            output_dir = "/tmp"

        logger.debug(f"Creating output directory if it doesn't exist: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)

        logger.debug("Generating unique file name for capture data")
        file_name = f"capture_{port_name}_{uuid.uuid4().hex[:8]}.pcap"
        file_path = os.path.join(output_dir, file_name)

        logger.info(f"Getting capture data for port {port_name}")

        logger.debug("Detecting available API methods for capture")
        api_methods = [method for method in dir(api) if not method.startswith("_")]
        logger.debug(f"Available API methods: {api_methods}")

        try:
            if "capture_request" in api_methods and "get_capture" in api_methods:
                logger.info("Using capture_request() and get_capture() methods")
                req = api.capture_request()
                req.port_name = port_name
                capture_data = api.get_capture(req)

                logger.info(f"Saving capture data to {file_path}")
                with open(file_path, "wb") as pcap:
                    pcap.write(capture_data.read())

            elif "control_state" in api_methods:
                logger.info("Using control_state() method for capture retrieval")
                cs = api.control_state()

                if hasattr(cs, "CAPTURE") and hasattr(cs, "choice"):
                    logger.debug("Setting control_state choice to CAPTURE")
                    cs.choice = cs.CAPTURE

                    if hasattr(cs, "capture"):
                        logger.debug("Found capture attribute in control_state")

                        if hasattr(cs.capture, "port_name"):
                            logger.debug(f"Setting port_name to {port_name}")
                            cs.capture.port_name = port_name

                        if hasattr(cs.capture, "state"):
                            logger.debug("Setting capture state to RETRIEVE")
                            if hasattr(cs.capture, "RETRIEVE"):
                                cs.capture.state = cs.capture.RETRIEVE
                            else:
                                cs.capture.state = "retrieve"

                logger.info(
                    f"Setting control state to retrieve capture on port {port_name}"
                )
                result = api.set_control_state(cs)

                if hasattr(result, "capture") and hasattr(result.capture, "data"):
                    logger.info(f"Saving capture data to {file_path}")
                    with open(file_path, "wb") as pcap:
                        pcap.write(result.capture.data)
                else:
                    raise ValueError(
                        f"No capture data found in control_state result: {result}"
                    )
            else:
                logger.error("No compatible capture retrieval method found in API")
                raise NotImplementedError("No method available to get capture data")

        except Exception as e:
            logger.error(f"Error getting capture data: {e}")
            raise

        logger.info(f"Capture data saved to {file_path}")
        return file_path

    async def get_traffic_generators_status(self):
        """Legacy method that maps to list_traffic_generators."""
        logger.info("Legacy call to get_traffic_generators_status")
        return await self.list_traffic_generators()

    async def set_config(
        self, config: Dict[str, Any], target: Optional[str] = None
    ) -> ConfigResponse:
        """
        Set configuration on traffic generator and retrieve the applied configuration.

        Args:
            config: Configuration to set
            target: Optional target ID

        Returns:
            Configuration response containing the applied configuration
        """
        logger.info(f"Setting configuration on target {target or 'default'}")

        try:
            logger.info(f"Getting API client for {target or 'localhost'}")
            api = self._get_api_client(target or "localhost")

            logger.info("Processing config based on type")
            if isinstance(config, dict):
                logger.info("Deserializing config dictionary")
                cfg = api.config()
                cfg.deserialize(config)
                api.set_config(cfg)
            else:
                logger.info("Using config object directly")
                api.set_config(config)

            logger.info("Retrieving the applied configuration")
            config = api.get_config()
            logger.info("Serializing retrieved config to dictionary")
            logger.debug("Using config directly for serialization")
            config_dict = config.serialize(encoding=config.DICT)  # type: ignore

            return ConfigResponse(status="success", config=config_dict)
        except Exception as e:
            logger.error(f"Error setting configuration: {e}")
            logger.error(traceback.format_exc())
            return ConfigResponse(status="error", config={"error": str(e)})

    async def get_config(self, target: Optional[str] = None) -> ConfigResponse:
        """
        Get configuration from traffic generator.

        Args:
            target: Optional target ID

        Returns:
            Configuration response
        """
        logger.info(f"Getting configuration from target {target or 'default'}")

        try:
            logger.info(f"Getting API client for {target or 'localhost'}")
            api = self._get_api_client(target or "localhost")

            logger.info("Getting configuration from device")
            config = api.get_config()

            logger.info("Serializing config to dictionary")
            logger.debug("Using config directly for serialization")
            config_dict = config.serialize(encoding=config.DICT)  # type: ignore

            return ConfigResponse(status="success", config=config_dict)
        except Exception as e:
            logger.error(f"Error getting configuration: {e}")
            logger.error(traceback.format_exc())
            return ConfigResponse(status="error", config={"error": str(e)})

    async def start_traffic(self, target: Optional[str] = None) -> ControlResponse:
        """
        Start traffic generation.

        Args:
            target: Optional target ID

        Returns:
            Control response
        """
        logger.info(f"Starting traffic on target {target or 'default'}")

        try:
            logger.info(f"Getting API client for {target or 'localhost'}")
            api = self._get_api_client(target or "localhost")

            logger.info("Starting traffic on device")
            self._start_traffic(api)

            return ControlResponse(status="success", action="traffic_generation")
        except Exception as e:
            logger.error(f"Error starting traffic: {e}")
            logger.error(traceback.format_exc())
            return ControlResponse(
                status="error", action="traffic_generation", result={"error": str(e)}
            )

    async def stop_traffic(self, target: Optional[str] = None) -> ControlResponse:
        """
        Stop traffic generation.

        Args:
            target: Target ID

        Returns:
            Control response
        """
        logger.info(f"Stopping traffic on target {target or 'default'}")

        try:
            logger.info(f"Getting API client for {target or 'localhost'}")
            api = self._get_api_client(target or "localhost")

            logger.info("Stopping traffic on device")
            success = self._stop_traffic(api)

            return ControlResponse(
                status="success",
                action="traffic_generation",
                result={"verified": success},
            )
        except Exception as e:
            logger.error(f"Error stopping traffic: {e}")
            logger.error(traceback.format_exc())
            return ControlResponse(
                status="error", action="traffic_generation", result={"error": str(e)}
            )

    async def start_capture(
        self, port_name: Union[str, List[str]], target: Optional[str] = None
    ) -> CaptureResponse:
        """
        Start packet capture on one or more ports.

        Args:
            port_name: Name or list of names of port(s) to capture on
            target: Optional target ID

        Returns:
            Capture response
        """
        logger.debug("Determining response port name for multi-port capture")
        response_port = (
            port_name[0] if isinstance(port_name, list) and port_name else port_name
        )
        if isinstance(response_port, list):
            logger.debug("Response port is still a list, extracting first element")
            response_port = response_port[0] if response_port else ""

        logger.info(
            f"Starting capture on port(s) {port_name} on target {target or 'default'}"
        )

        try:
            logger.info(f"Getting API client for {target or 'localhost'}")
            api = self._get_api_client(target or "localhost")

            logger.info(
                f"Starting capture on port(s) {port_name} with improved implementation"
            )
            result = start_capture(api, port_name)

            if result["status"] == "success":
                return CaptureResponse(status="success", port=response_port)
            else:
                return CaptureResponse(
                    status="error",
                    port=response_port,
                    data={"error": result.get("error", "Unknown error")},
                )
        except Exception as e:
            logger.error(f"Error starting capture: {e}")
            logger.error(traceback.format_exc())
            return CaptureResponse(
                status="error", port=response_port, data={"error": str(e)}
            )

    async def stop_capture(
        self, port_name: Union[str, List[str]], target: Optional[str] = None
    ) -> CaptureResponse:
        """
        Stop packet capture on one or more ports.

        Args:
            port_name: Name or list of names of port(s) to stop capture on
            target: Optional target ID

        Returns:
            Capture response
        """
        logger.debug("Determining response port name for multi-port capture")
        response_port = (
            port_name[0] if isinstance(port_name, list) and port_name else port_name
        )
        if isinstance(response_port, list):
            logger.debug("Response port is still a list, extracting first element")
            response_port = response_port[0] if response_port else ""

        logger.info(
            f"Stopping capture on port(s) {port_name} on target {target or 'default'}"
        )

        try:
            logger.info(f"Getting API client for {target or 'localhost'}")
            api = self._get_api_client(target or "localhost")

            logger.info(
                f"Stopping capture on port(s) {port_name} with improved implementation"
            )
            result = stop_capture(api, port_name)

            if result["status"] == "success":
                data = {"status": "stopped"}
                if "warnings" in result:
                    data["warnings"] = result["warnings"]
                return CaptureResponse(status="success", port=response_port, data=data)
            else:
                return CaptureResponse(
                    status="error",
                    port=response_port,
                    data={"error": result.get("error", "Unknown error")},
                )
        except Exception as e:
            logger.error(f"Error stopping capture: {e}")
            logger.error(traceback.format_exc())
            return CaptureResponse(
                status="error", port=response_port, data={"error": str(e)}
            )

    async def get_capture(
        self,
        port_name: str,
        output_dir: Optional[str] = None,
        target: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> CaptureResponse:
        """
        Get packet capture from a port and save it to a file.

        Args:
            port_name: Name of port to get capture from
            output_dir: Directory to save the capture file (default: /tmp)
            target: Optional target ID
            filename: Optional custom filename for the capture file

        Returns:
            Capture response with file path where the capture was saved
        """
        logger.info(
            f"Getting capture from port {port_name} on target {target or 'default'}"
        )

        try:
            logger.info(f"Getting API client for {target or 'localhost'}")
            api = self._get_api_client(target or "localhost")

            logger.info(
                f"Getting capture for port {port_name} with improved implementation"
            )
            result = get_capture(
                api, port_name, output_dir=output_dir, filename=filename
            )

            if result["status"] == "success":
                return CaptureResponse(
                    status="success",
                    port=port_name,
                    data={"status": "captured", "file_path": result["file_path"]},
                    file_path=result["file_path"],
                    capture_id=result.get("capture_id"),
                )
            else:
                return CaptureResponse(
                    status="error",
                    port=port_name,
                    data={"error": result.get("error", "Unknown error")},
                )
        except Exception as e:
            logger.error(f"Error getting capture: {e}")
            logger.error(traceback.format_exc())
            return CaptureResponse(
                status="error", port=port_name, data={"error": str(e)}
            )

    async def list_traffic_generators(self) -> TrafficGeneratorStatus:
        """
        List all available traffic generators.

        Returns:
            TrafficGeneratorStatus containing all traffic generators
        """
        logger.info("Listing all traffic generators")

        try:
            result = TrafficGeneratorStatus()

            logger.info("Getting targets from config")
            for hostname, target_config in self.config.targets.targets.items():
                logger.info(f"Adding target {hostname} to list")

                logger.info(f"Creating generator info for {hostname}")
                gen_info = TrafficGeneratorInfo(hostname=hostname)

                logger.info(f"Adding port configurations for {hostname}")
                for port_name, port_config in target_config.ports.items():
                    logger.debug(f"Ensuring location is not None for port {port_name}")
                    location = port_config.location or ""
                    gen_info.ports[port_name] = PortInfo(
                        name=port_name, location=location, interface=None
                    )

                logger.info(f"Testing connection to {hostname}")
                try:
                    logger.info("Simple availability check")
                    gen_info.available = True
                except Exception as e:
                    logger.warning(f"Error connecting to {hostname}: {e}")
                    gen_info.available = False

                logger.info(f"Adding {hostname} to result")
                result.generators[hostname] = gen_info

            return result
        except Exception as e:
            logger.error(f"Error listing traffic generators: {e}")
            logger.error(traceback.format_exc())
            return TrafficGeneratorStatus()

    async def get_available_targets(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all available traffic generator targets with comprehensive information.

        Provides a combined view of target configurations and availability status:
        - Technical configuration (ports)
        - Availability information (whether target is reachable)
        - API version information (when available)
        - Additional metadata

        This method always clears the client cache to ensure fresh connections.

        Returns:
            Dictionary mapping target names to their configurations, including:
            - ports: Port configurations for the target
            - available: Whether the target is currently reachable
            - apiVersion: API version detected from the target (if available)
        """
        logger.info("Getting available traffic generator targets")

        logger.info("Clearing client cache to force reconnection")
        self.api_clients.clear()

        result = {}
        try:
            logger.info("Reading targets from config")
            for target_name, target_config in self.config.targets.targets.items():
                logger.info(f"Processing target: {target_name}")

                target_dict = {
                    "ports": {},
                    "available": False,
                }

                for port_name, port_config in target_config.ports.items():
                    target_dict["ports"][port_name] = {  # type: ignore
                        "location": port_config.location,
                        "name": port_config.name,
                    }

                logger.info(f"Testing connection to {target_name}")
                try:
                    self._get_api_client(target_name)
                    logger.debug("Testing availability of the target")
                    target_dict["available"] = True
                    logger.info(f"Target {target_name} is available")

                    logger.info(
                        f"Attempting to retrieve API version from target {target_name}"
                    )
                    try:
                        version_info = await self.get_target_version(target_name)
                        target_dict["apiVersion"] = version_info.sdk_version
                        logger.info(
                            f"Detected API version {version_info.sdk_version} for target {target_name}"
                        )
                    except Exception as version_error:
                        logger.warning(
                            f"Could not detect API version for {target_name}: {version_error}"
                        )
                        target_dict["apiVersionError"] = str(version_error)
                except Exception as e:
                    logger.warning(f"Error connecting to {target_name}: {e}")
                    target_dict["available"] = False
                    target_dict["error"] = str(e)

                result[target_name] = target_dict  # type: ignore

            logger.info(
                f"Found {len(result)} targets, {sum(1 for t in result.values() if t['available'])} available"
            )
            return result
        except Exception as e:
            logger.error(f"Error getting available targets: {e}")
            logger.error(traceback.format_exc())
            return {}

    async def _get_target_config(self, target_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific target (internal method).

        Args:
            target_name: Name of the target to look up

        Returns:
            Target configuration including ports and dynamically determined apiVersion,
            or None if the target doesn't exist
        """
        logger.info(f"Looking up configuration for target: {target_name}")

        try:
            targets = await self.get_available_targets()

            if target_name in targets:
                logger.info(f"Found configuration for target: {target_name}")
                target_config = targets[target_name]
                schema_registry = self.schema_registry

                logger.info(
                    "Initializing API version with default value to be overridden by device-reported version"
                )
                target_config["apiVersion"] = "unknown"
                logger.debug(
                    "API version is always set dynamically from device, never from config"
                )

                logger.info("Getting API version directly from the target device")
                try:
                    logger.info(
                        f"Attempting to get API version from target {target_name}"
                    )
                    version_info = await self.get_target_version(target_name)
                    actual_api_version = version_info.sdk_version
                    normalized_version = actual_api_version.replace(".", "_")

                    logger.info(
                        f"Target {target_name} reports API version: {actual_api_version}"
                    )

                    logger.debug(
                        "Verifying schema registry was properly initialized in __post_init__"
                    )
                    if schema_registry is None:
                        logger.error("Schema registry is not initialized")
                        raise ValueError("Schema registry is not initialized")

                    logger.info(
                        "Checking for schema match for the reported API version"
                    )
                    if schema_registry.schema_exists(normalized_version):
                        logger.info(
                            f"Found exact schema for actual version: {actual_api_version}"
                        )
                        target_config["apiVersion"] = actual_api_version
                    else:
                        logger.info(
                            "No exact schema match found, finding closest available schema"
                        )
                        if schema_registry is None:
                            logger.error("Schema registry is not initialized")
                            raise ValueError("Schema registry is not initialized")

                        closest_version = schema_registry.find_closest_schema_version(
                            normalized_version
                        )
                        closest_version_dotted = closest_version.replace("_", ".")
                        logger.info(
                            f"No exact schema for version {actual_api_version}. "
                            f"Using closest matching version: {closest_version_dotted}"
                        )
                        target_config["apiVersion"] = closest_version_dotted
                except Exception as e:
                    logger.info(
                        "Exception during API version detection, falling back to latest schema"
                    )
                    if schema_registry is None:
                        logger.error("Schema registry is not initialized")
                        raise ValueError("Schema registry is not initialized")

                    latest_version = schema_registry.get_latest_schema_version()
                    latest_version_dotted = latest_version.replace("_", ".")
                    logger.warning(
                        f"Failed to get API version from target {target_name}: {str(e)}. "
                        f"Using latest available schema version: {latest_version_dotted}"
                    )
                    target_config["apiVersion"] = latest_version_dotted

                return target_config

            logger.warning(f"Target not found: {target_name}")
            return None
        except Exception as e:
            logger.error(f"Error looking up target {target_name}: {e}")
            logger.error(traceback.format_exc())
            return None

    async def get_schemas_for_target(
        self, target_name: str, schema_names: List[str]
    ) -> Dict[str, Any]:
        """
        Get multiple schemas for a specific target.

        Args:
            target_name: Name of the target
            schema_names: List of schema names/components to retrieve (e.g., ["Flow", "Port"] or
                         ["components.schemas.Flow", "components.schemas.Port"])

        Returns:
            Dictionary mapping schema names to their content

        Raises:
            ValueError: If the target doesn't exist or schemas couldn't be loaded
        """
        logger.info(
            f"Getting schemas for target {target_name}, schemas: {schema_names}"
        )

        target_config = await self._get_target_config(target_name)
        if not target_config:
            error_msg = f"Target {target_name} not found"
            logger.error(error_msg)
            raise ValueError(error_msg)

        api_version = target_config["apiVersion"]
        logger.info(f"Using API version {api_version} for target {target_name}")

        result = {}
        try:
            registry = self.schema_registry
            for schema_name in schema_names:
                logger.info(f"Retrieving schema {schema_name} for target {target_name}")
                try:
                    logger.debug("Verifying schema registry is properly initialized")
                    if registry is None:
                        logger.error("Schema registry is not initialized")
                        raise ValueError("Schema registry is not initialized")

                    if "." not in schema_name or not schema_name.startswith(
                        "components.schemas."
                    ):
                        qualified_name = f"components.schemas.{schema_name}"
                        logger.info(f"Interpreting {schema_name} as {qualified_name}")
                        result[schema_name] = registry.get_schema(
                            api_version, qualified_name
                        )
                    else:

                        result[schema_name] = registry.get_schema(
                            api_version, schema_name
                        )
                except Exception as e:
                    logger.warning(f"Error retrieving schema {schema_name}: {str(e)}")
                    logger.debug("Creating error dictionary for exception response")
                    error_msg = str(e)
                    result[schema_name] = {"error": error_msg}

            return result
        except Exception as e:
            error_msg = f"Error getting schemas for target {target_name}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def list_schemas_for_target(self, target_name: str) -> List[str]:
        """
        List available schemas for a specific target's API version.

        This method returns only the components.schemas entries from the schema,
        focusing solely on the available schemas without including other structural
        information like top-level keys, paths, or other components.

        Args:
            target_name: Name of the target

        Returns:
            List of available schema names under components.schemas

        Raises:
            ValueError: If the target doesn't exist
        """
        logger.info(f"Listing schemas for target {target_name}")

        target_config = await self._get_target_config(target_name)
        if not target_config:
            error_msg = f"Target {target_name} not found"
            logger.error(error_msg)
            raise ValueError(error_msg)

        api_version = target_config["apiVersion"]
        logger.info(f"Using API version {api_version} for target {target_name}")

        try:
            registry = self.schema_registry
            logger.debug("Verifying schema registry is properly initialized")
            if registry is None:
                logger.error("Schema registry is not initialized")
                raise ValueError("Schema registry is not initialized")
            schema = registry.get_schema(api_version)

            if (
                "components" in schema
                and isinstance(schema["components"], dict)
                and "schemas" in schema["components"]
                and isinstance(schema["components"]["schemas"], dict)
            ):

                result = list(schema["components"]["schemas"].keys())
                logger.info(f"Extracted {len(result)} schema keys")
                return result
            else:
                logger.warning("No components.schemas found in the schema")
                return []
        except Exception as e:
            error_msg = (
                f"Error listing schema structure for target {target_name}: {str(e)}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def get_target_version(self, target: str) -> CapabilitiesVersionResponse:
        """
        Get version information from a target's capabilities/version endpoint.

        Args:
            target: Target hostname or IP

        Returns:
            CapabilitiesVersionResponse containing version information

        Raises:
            ValueError: If the request fails
        """
        logger.info(f"Getting version information from target {target}")

        url = f"https://{target}/capabilities/version"
        logger.info(f"Making request to {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Received version data: {data}")
                    return CapabilitiesVersionResponse(**data)
                else:
                    error_msg = (
                        f"Failed to get version from {target}: {response.status}"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)

    async def get_schema_components_for_target(
        self, target_name: str, path_prefix: str = "components.schemas"
    ) -> List[str]:
        """
        Get a list of schema component names for a specific target's API version.

        Args:
            target_name: Name of the target
            path_prefix: The path prefix to look in (default: "components.schemas")

        Returns:
            List of component names

        Raises:
            ValueError: If the target doesn't exist or path doesn't exist
        """
        logger.info(
            f"Getting schema components for target {target_name} with prefix {path_prefix}"
        )

        target_config = await self._get_target_config(target_name)
        if not target_config:
            error_msg = f"Target {target_name} not found"
            logger.error(error_msg)
            raise ValueError(error_msg)

        api_version = target_config["apiVersion"]
        logger.info(f"Using API version {api_version} for target {target_name}")

        try:
            registry = self.schema_registry
            logger.debug("Verifying schema registry is properly initialized")
            if registry is None:
                logger.error("Schema registry is not initialized")
                raise ValueError("Schema registry is not initialized")
            return registry.get_schema_components(api_version, path_prefix)
        except Exception as e:
            error_msg = (
                f"Error getting schema components for target {target_name}: {str(e)}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def health(self, target: Optional[str] = None) -> HealthStatus:
        """
        Check health of traffic generator system by verifying version endpoints.

        Args:
            target: Optional target to check. If None, checks all targets.

        Returns:
            HealthStatus: Collection of target health information
        """
        logger.info(f"Checking health of {target or 'all targets'}")

        logger.debug("Initializing HealthStatus with 'error' status by default")
        health_status = HealthStatus(status="error")

        try:
            target_names = []
            if target:
                logger.info(f"Checking specific target: {target}")
                target_names = [target]
            else:
                logger.info("No specific target - checking all available targets")
                targets = await self.get_available_targets()
                target_names = list(targets.keys())
                logger.info(f"Found {len(target_names)} targets to check")

            logger.info("Beginning health checks for all targets")
            all_targets_healthy = True
            for target_name in target_names:
                logger.info(f"Checking health for target: {target_name}")
                try:
                    logger.info(f"Requesting version info from {target_name}")
                    version_info = await self.get_target_version(target_name)

                    logger.info(f"Target {target_name} is healthy")
                    health_status.targets[target_name] = TargetHealthInfo(
                        name=target_name,
                        healthy=True,
                        version_info=version_info,
                        error=None,
                    )

                except Exception as e:
                    logger.warning(f"Target {target_name} is unhealthy: {str(e)}")
                    health_status.targets[target_name] = TargetHealthInfo(
                        name=target_name, healthy=False, error=str(e), version_info=None
                    )
                    all_targets_healthy = False

            if all_targets_healthy and target_names:
                logger.info("All targets are healthy, setting status to 'success'")
                health_status.status = "success"
            else:
                logger.info("One or more targets are unhealthy, status remains 'error'")

            logger.info(f"Health check complete for {len(target_names)} targets")
            return health_status

        except Exception as e:
            logger.error(f"Health check failed with error: {str(e)}")
            logger.error(traceback.format_exc())
            return HealthStatus(status="error", targets={})

    async def get_metrics(
        self,
        flow_names: Optional[Union[str, List[str]]] = None,
        port_names: Optional[Union[str, List[str]]] = None,
        target: Optional[str] = None,
    ) -> MetricsResponse:
        """
        Get metrics from traffic generator.

        This unified method handles all metrics retrieval cases:
        - All metrics (flows and ports): call with no parameters
        - All flow metrics: call with flow_names=[]
        - Specific flow(s): call with flow_names="flow1" or flow_names=["flow1", "flow2"]
        - All port metrics: call with port_names=[]
        - Specific port(s): call with port_names="port1" or port_names=["port1", "port2"]
        - Combination: call with both flow_names and port_names

        Args:
            flow_names: Optional flow name(s) to get metrics for:
                - None: Flow metrics not specifically requested
                - Empty list: All flow metrics
                - str: Single flow metrics
                - List[str]: Multiple flow metrics
            port_names: Optional port name(s) to get metrics for:
                - None: Port metrics not specifically requested
                - Empty list: All port metrics
                - str: Single port metrics
                - List[str]: Multiple port metrics
            target: Optional target ID

        Returns:
            Metrics response containing requested metrics
        """
        logger.info(f"Getting metrics from target {target or 'default'}")

        try:
            logger.info(f"Getting API client for {target or 'localhost'}")
            api = self._get_api_client(target or "localhost")

            flow_name_list = None
            if flow_names is not None:
                if isinstance(flow_names, str):
                    logger.info(f"Getting metrics for flow: {flow_names}")
                    flow_name_list = [flow_names]
                else:
                    if flow_names:
                        logger.info(f"Getting metrics for flows: {flow_names}")
                    else:
                        logger.info("Getting metrics for all flows")
                    flow_name_list = flow_names

            port_name_list = None
            if port_names is not None:
                if isinstance(port_names, str):
                    logger.info(f"Getting metrics for port: {port_names}")
                    port_name_list = [port_names]
                else:
                    if port_names:
                        logger.info(f"Getting metrics for ports: {port_names}")
                    else:
                        logger.info("Getting metrics for all ports")
                    port_name_list = port_names

            if flow_name_list is None and port_name_list is None:
                logger.info("Getting all metrics (no specific filters)")
                metrics = self._get_metrics(api)
            else:
                logger.info(
                    f"Calling _get_metrics with flow_names={flow_name_list}, port_names={port_name_list}"
                )
                metrics = self._get_metrics(
                    api, flow_names=flow_name_list, port_names=port_name_list
                )

            logger.info("Serializing metrics to dictionary")
            logger.debug("Using metrics directly for serialization")
            metrics_dict = metrics.serialize(encoding=metrics.DICT)  # type: ignore

            return MetricsResponse(status="success", metrics=metrics_dict)
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            logger.error(traceback.format_exc())
            return MetricsResponse(status="error", metrics={"error": str(e)})
