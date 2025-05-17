import json
import logging
import os
import socket
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class LoggingConfig(BaseSettings):
    """Configuration for logging."""

    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    @validator("LOG_LEVEL")
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        upper_v = v.upper()
        if upper_v not in valid_levels:
            logger.error(f"LOG_LEVEL must be one of {valid_levels}")
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        logger.info(f"Validated log level: {upper_v}")
        return upper_v


@dataclass
class DirectConnectionInfo:
    """Information about a direct connection to a traffic generator."""

    hostname: str
    name: str
    instance_id: str
    is_direct_hostname: bool = True
    local_port: Optional[int] = None  # noqa: E501


class PortConfig(BaseModel):
    """Configuration for a port on a traffic generator."""

    location: Optional[str] = Field(None, description="Location of the port (hostname:port)")
    name: Optional[str] = Field(None, description="Name of the port")
    interface: Optional[str] = Field(None, description="Interface name (backward compatibility)")

    @validator("location", pre=True, always=True)
    def validate_location(cls, v, values):
        """Validate location, using interface if location is not provided."""
        if v is None and "interface" in values and values["interface"] is not None:
            return values["interface"]
        return v

    @validator("name", pre=True, always=True)
    def validate_name(cls, v, values):
        """Validate name, using interface or location if name is not provided."""
        if v is None:
            if "interface" in values and values["interface"] is not None:
                return values["interface"]
            if "location" in values and values["location"] is not None:
                return values["location"]
        return v


class TargetConfig(BaseModel):
    """Configuration for a traffic generator target."""

    apiVersion: str = Field(
        default="1_30_0", description="API schema version to use for this target"
    )
    ports: Dict[str, PortConfig] = Field(
        default_factory=dict, description="Port configurations mapped by port name"
    )


class TargetsConfig(BaseSettings):
    """Configuration for all available traffic generator targets."""

    targets: Dict[str, TargetConfig] = Field(
        default_factory=dict,
        description="Target configurations mapped by hostname:port",
    )


class DirectConnectionConfig(BaseSettings):
    """Configuration for direct connections to traffic generators."""

    DEFAULT_HOST: str = Field(
        default="localhost", description="Default hostname to use"
    )
    DEFAULT_PORT: int = Field(default=443, description="Default port to use")


class Config:
    """Main configuration for the MCP server."""

    def __init__(self, config_file: Optional[str] = None):
        self.logging = LoggingConfig()
        self.direct = DirectConnectionConfig()
        self.targets = TargetsConfig()

        logger.info("Initializing configuration")
        if config_file:
            logger.info(f"Loading configuration from file: {config_file}")
            self.load_config_file(config_file)
        elif not self.targets.targets:
            logger.info("No targets defined - adding default development target")
            example_target = TargetConfig(
                ports={
                    "p1": PortConfig(location="localhost:5555", name="p1", interface=None),
                    "p2": PortConfig(location="localhost:5555", name="p2", interface=None),
                }
            )
            self.targets.targets["localhost:8443"] = example_target

    def load_config_file(self, config_file_path: str) -> None:
        """
        Load the traffic generator configuration from a JSON file.

        Args:
            config_file_path: Path to the JSON configuration file

        Raises:
            FileNotFoundError: If the config file doesn't exist
            json.JSONDecodeError: If the config file isn't valid JSON
            ValueError: If the config file doesn't have the expected structure
        """
        logger.info(f"Loading traffic generator configuration from: {config_file_path}")

        if not os.path.exists(config_file_path):
            error_msg = f"Configuration file not found: {config_file_path}"
            logger.critical(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            with open(config_file_path, "r") as file:
                config_data = json.load(file)

            logger.info("Validating configuration structure")
            if "targets" not in config_data:
                error_msg = "Configuration file must contain a 'targets' property"
                logger.critical(error_msg)
                raise ValueError(error_msg)

            logger.info("Clearing existing targets and initializing new configuration")
            self.targets = TargetsConfig()

            logger.info("Processing each target in configuration")
            for hostname, target_data in config_data["targets"].items():
                if not isinstance(target_data, dict) or "ports" not in target_data:
                    error_msg = f"Target '{hostname}' must contain a 'ports' dictionary"
                    logger.error(error_msg)
                    continue

                logger.info(f"Creating target config for {hostname}")
                api_version = target_data.get("apiVersion", "1.30.0")
                logger.info(f"Target {hostname} using API version: {api_version}")
                target_config = TargetConfig(apiVersion=api_version)

                logger.info(f"Processing port configurations for {hostname}")
                if "ports" in target_data:
                    for port_name, port_data in target_data["ports"].items():
                        if not isinstance(port_data, dict):
                            error_msg = f"Port '{port_name}' for target '{hostname}' must be a dictionary"
                            logger.error(error_msg)
                            continue

                        if "location" not in port_data:
                            error_msg = f"Port '{port_name}' for target '{hostname}' must contain a 'location' property"
                            logger.error(error_msg)
                            continue

                        logger.debug(f"Setting name for port {port_name}")
                        name = port_data.get("name", port_name)

                        logger.debug(
                            f"Creating port config for {port_name} with location {port_data['location']}"
                        )
                        target_config.ports[port_name] = PortConfig(
                            location=port_data["location"], name=name, interface=None
                        )
                else:
                    logger.warning(
                        f"Target '{hostname}' does not contain a 'ports' dictionary"
                    )

                logger.info(f"Adding target {hostname} to configuration")
                self.targets.targets[hostname] = target_config

            logger.info(
                f"Successfully loaded configuration with {len(self.targets.targets)} targets"
            )
            logger.info(
                f"Successfully loaded configuration with {len(self.targets.targets)} targets"
            )

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in configuration file: {str(e)}"
            logger.critical(error_msg)
            raise
        except Exception as e:
            error_msg = f"Error loading configuration: {str(e)}"
            logger.critical(error_msg)
            raise

    def setup_logging(self):
        """Configure logging based on the provided settings."""
        try:
            log_level = getattr(logging, self.logging.LOG_LEVEL)
            print(f"Setting up logging at level {self.logging.LOG_LEVEL}")

            logger.info(
                "Setting up both basic config and console handler for comprehensive logging"
            )
            logging.basicConfig(
                level=log_level,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )

            logger.info("Configuring root logger")
            root_logger = logging.getLogger()
            root_logger.setLevel(log_level)

            logger.info(f"Setting module logger to level {log_level}")
            module_logger = logging.getLogger("otg_mcp")
            module_logger.setLevel(log_level)

            logger.info("Checking if root logger has handlers, adding if needed")
            if not root_logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(log_level)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)
                print("Added console handler to root logger")

            logger.info("Logging system initialized with handlers and formatters")
            logger.info(f"Logging configured at level {self.logging.LOG_LEVEL}")
        except Exception as e:
            print(f"CRITICAL ERROR setting up logging: {str(e)}")
            import traceback

            print(f"Stack trace: {traceback.format_exc()}")
            logger.critical(f"Failed to set up logging: {str(e)}")
            logger.critical(f"Stack trace: {traceback.format_exc()}")

    def discover_instances(self) -> List[DirectConnectionInfo]:
        """
        Discover available traffic generators.

        This method returns an empty list since we don't use AWS-based discovery.
        """
        logger.info("Instance discovery disabled (using direct connections only)")
        return []

    def get_available_port(self) -> int:
        """Get an available port starting from a range."""
        logger.debug("Starting port discovery from port 8000")
        port = 8000
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                logger.debug(f"Checking if port {port} is available")
                if s.connect_ex(("localhost", port)) != 0:
                    logger.info(f"Found available port: {port}")
                    return port
                port += 1
                if port > 65535:
                    logger.error("No available ports found")
                    raise RuntimeError("No available ports found")


logger.info("Creating a global config instance")
config = Config()


def get_config() -> Config:
    """Get the global config instance."""
    return config
