import json
import logging
import os
from typing import Dict, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
)
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

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Reject log levels outside the standard set.

        Args:
            v: Candidate log level

        Returns:
            The level upper-cased

        Raises:
            ValueError: If the level is not a standard logging level
        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        upper_v = v.upper()
        if upper_v not in valid_levels:
            logger.error(f"LOG_LEVEL must be one of {valid_levels}")
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        logger.info(f"Validated log level: {upper_v}")
        return upper_v


class PortConfig(BaseModel):
    """Configuration for a port on a traffic generator."""

    location: Optional[str] = Field(
        None,
        description="Location of the port (hostname:port)",
        validate_default=True,
    )
    name: Optional[str] = Field(
        None, description="Name of the port", validate_default=True
    )
    interface: Optional[str] = Field(
        None, description="Interface name (backward compatibility)"
    )

    @field_validator("location", mode="before")
    @classmethod
    def validate_location(
        cls, v: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        """Fall back to interface when location is not provided.

        validate_default keeps this running when the field is omitted, matching
        the always=True behaviour this validator had before the Pydantic V2 port.
        info.data holds only the fields validated before this one, so it mirrors
        the V1 values mapping exactly.

        Args:
            v: Supplied location, if any
            info: Validation context carrying previously validated fields

        Returns:
            The location to use
        """
        if v is None and info.data.get("interface") is not None:
            logger.debug("Deriving port location from interface")
            return info.data["interface"]
        return v

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Fall back to interface, then location, when name is not provided.

        Args:
            v: Supplied name, if any
            info: Validation context carrying previously validated fields

        Returns:
            The name to use
        """
        if v is None:
            if info.data.get("interface") is not None:
                logger.debug("Deriving port name from interface")
                return info.data["interface"]
            if info.data.get("location") is not None:
                logger.debug("Deriving port name from location")
                return info.data["location"]
        return v


class TargetConfig(BaseModel):
    """Configuration for a traffic generator target."""

    ports: Dict[str, PortConfig] = Field(
        default_factory=dict, description="Port configurations mapped by port name"
    )

    model_config = ConfigDict(extra="forbid")


class TargetsConfig(BaseSettings):
    """Configuration for all available traffic generator targets."""

    targets: Dict[str, TargetConfig] = Field(
        default_factory=dict,
        description="Target configurations mapped by hostname:port",
    )


class SchemaConfig(BaseSettings):
    """Configuration for schema handling."""

    schema_path: Optional[str] = Field(
        default=None, description="Path to directory containing custom schema files"
    )


class Config:
    """Main configuration for the MCP server."""

    def __init__(self, config_file: Optional[str] = None):
        self.logging = LoggingConfig()
        self.targets = TargetsConfig()
        self.schemas = SchemaConfig()

        logger.info("Initializing configuration")
        if config_file:
            logger.info(f"Loading configuration from file: {config_file}")
            self.load_config_file(config_file)
        elif not self.targets.targets:
            logger.info("No targets defined - adding default development target")
            example_target = TargetConfig(
                ports={
                    "p1": PortConfig(
                        location="localhost:5555", name="p1", interface=None
                    ),
                    "p2": PortConfig(
                        location="localhost:5555", name="p2", interface=None
                    ),
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

                logger.info("Validating target configuration using Pydantic model")
                try:
                    target_config = TargetConfig(**target_data)
                except ValidationError as e:
                    error_msg = (
                        f"Invalid target configuration for '{hostname}': {str(e)}"
                    )
                    logger.error(error_msg)
                    if "extra fields not permitted" in str(e):
                        logger.error(
                            "The configuration contains fields that are not allowed. "
                            "apiVersion should not be included in target configuration."
                        )
                    continue

                logger.info(f"Adding target {hostname} to configuration")
                self.targets.targets[hostname] = target_config

            logger.info("Checking for schema path in configuration")
            self._load_schema_path(config_data)

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

    def _load_schema_path(self, config_data: dict) -> None:
        """
        Resolve the custom schema directory from loaded configuration data.

        The documented location is a nested "schemas" object:
        {"schemas": {"schema_path": "/path/to/schemas"}}. A top-level
        "schema_path" key is also honored for backward compatibility.

        Args:
            config_data: Parsed contents of the configuration file
        """
        schema_path = None
        source = None

        logger.info("Looking for schema_path in the nested 'schemas' object")
        schemas_section = config_data.get("schemas")
        if isinstance(schemas_section, dict):
            schema_path = schemas_section.get("schema_path")
            source = "schemas.schema_path"
        elif schemas_section is not None:
            logger.warning(
                f"Ignoring 'schemas' property because it is not an object: {schemas_section!r}"
            )

        if schema_path is None:
            logger.info("Falling back to the legacy top-level 'schema_path' key")
            if "schema_path" in config_data:
                schema_path = config_data["schema_path"]
                source = "schema_path"
                logger.warning(
                    "Top-level 'schema_path' is deprecated, "
                    "move it under the 'schemas' object instead"
                )

        if schema_path is None:
            logger.info("No custom schema path configured, using built-in schemas only")
            return

        logger.info(f"Found {source} in config: {schema_path}")
        if os.path.exists(schema_path):
            self.schemas.schema_path = schema_path
            logger.info(f"Using custom schema path: {schema_path}")
        else:
            logger.warning(f"Specified schema path does not exist: {schema_path}")

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
