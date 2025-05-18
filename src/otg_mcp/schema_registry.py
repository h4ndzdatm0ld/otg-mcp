"""
Schema registry for the Open Traffic Generator API.
Loads and provides access to OpenAPI schemas based on version.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class SchemaRegistry:
    """
    Registry for Open Traffic Generator API schemas.

    This class loads and provides access to OpenAPI schemas
    for the various versions of the OTG API.
    """

    def __init__(self):
        """Initialize the schema registry."""
        logger.info("Initializing schema registry")
        self.schemas = {}
        self._available_schemas = None
        self._schemas_dir = os.path.join(os.path.dirname(__file__), "schemas")
        logger.info(
            f"Schema registry initialized with schemas directory: {self._schemas_dir}"
        )

    def _normalize_version(self, version: str) -> str:
        """
        Normalize version string to directory format.

        Args:
            version: Version string (e.g. "1.30.0" or "1_30_0")

        Returns:
            Normalized version string using underscores (e.g. "1_30_0")
        """
        logger.debug(f"Normalizing version string: {version}")
        return version.replace(".", "_")

    def get_available_schemas(self) -> List[str]:
        """
        Get a list of available schema versions.

        Returns:
            List of available schema versions
        """
        logger.info("Getting available schemas")
        if self._available_schemas is None:
            logger.info("Scanning schemas directory for available versions")
            if not os.path.exists(self._schemas_dir):
                logger.warning(f"Schemas directory does not exist: {self._schemas_dir}")
                return []

            self._available_schemas = [
                d
                for d in os.listdir(self._schemas_dir)
                if os.path.isdir(os.path.join(self._schemas_dir, d))
                and os.path.exists(os.path.join(self._schemas_dir, d, "openapi.yaml"))
            ]
            logger.info(
                f"Found {len(self._available_schemas)} available schemas: {self._available_schemas}"
            )

        return self._available_schemas

    def schema_exists(self, version: str) -> bool:
        """
        Check if a schema version exists.

        Args:
            version: Schema version to check (e.g. "1.30.0" or "1_30_0")

        Returns:
            True if the schema exists, False otherwise
        """
        normalized = self._normalize_version(version)
        logger.debug(f"Checking if schema exists: {version} (normalized: {normalized})")
        return normalized in self.get_available_schemas()

    def list_schemas(self, version: str) -> List[str]:
        """
        List all schema keys for a specific version.

        Args:
            version: Schema version (e.g. "1.30.0" or "1_30_0")

        Returns:
            List of top-level schema keys

        Raises:
            ValueError: If the schema version does not exist
        """
        logger.info(f"Listing schemas for version: {version}")
        normalized = self._normalize_version(version)

        logger.info(f"Getting schema for version {normalized}")
        schema = self.get_schema(normalized)

        logger.debug("Returning top-level schema keys")
        keys = list(schema.keys())
        logger.info(f"Found {len(keys)} top-level keys in schema {version}")
        return keys

    def get_schema_components(
        self, version: str, path_prefix: str = "components.schemas"
    ) -> List[str]:
        """
        Get a list of component names in a schema.

        Args:
            version: Schema version (e.g. "1.30.0" or "1_30_0")
            path_prefix: The path prefix to look in (default: "components.schemas")

        Returns:
            List of component names

        Raises:
            ValueError: If the schema version or path does not exist
        """
        logger.info(
            f"Getting schema components for {version} with prefix {path_prefix}"
        )
        normalized = self._normalize_version(version)

        logger.info(f"Getting component at path {path_prefix}")
        component = self.get_schema(normalized, path_prefix)

        logger.debug("Returning component keys")
        if isinstance(component, dict):
            keys = list(component.keys())
            logger.info(f"Found {len(keys)} components at path {path_prefix}")
            return keys
        else:
            logger.warning(f"Component at {path_prefix} is not a dictionary")
            return []

    def get_schema(
        self, version: str, component: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get schema for the specified version and optional component.

        Args:
            version: Schema version (e.g., "1.30.0" or "1_30_0")
            component: Optional component path (e.g., "components.schemas.Flow.Router")
                       using dot notation to navigate the schema

        Returns:
            Dict containing the schema or component

        Raises:
            ValueError: If the schema version or component does not exist
        """
        logger.info(
            f"Getting schema for version: {version}, component: {component or 'all'}"
        )
        normalized = self._normalize_version(version)

        logger.info(f"Validating schema version exists: {version}")
        if not self.schema_exists(normalized):
            logger.error(f"Schema version not found: {version}")
            raise ValueError(f"Schema version {version} not found")

        logger.info(f"Loading schema if not already cached: {normalized}")
        if normalized not in self.schemas:
            schema_path = os.path.join(self._schemas_dir, normalized, "openapi.yaml")
            logger.info(f"Loading schema from {schema_path}")

            try:
                with open(schema_path, "r") as f:
                    self.schemas[normalized] = yaml.safe_load(f)
                logger.info(f"Successfully loaded schema version {normalized}")
            except Exception as e:
                logger.error(f"Error loading schema {normalized}: {str(e)}")
                raise ValueError(f"Error loading schema {normalized}: {str(e)}")

        if not component:
            logger.debug("Returning full schema")
            return self.schemas[normalized]

        logger.info(
            f"Checking if component path requires special handling: {component}"
        )
        if component.startswith("components.schemas."):
            logger.debug("Using special handling for components.schemas.X path")
            schema_name = component[len("components.schemas.") :]
            logger.debug(f"Extracted schema name: {schema_name}")

            logger.debug(f"Getting schemas dictionary for {normalized}")
            try:
                schemas = self.schemas[normalized]["components"]["schemas"]

                logger.debug(f"Checking if schema {schema_name} exists directly")
                if schema_name in schemas:
                    logger.info(f"Found schema {schema_name}")
                    return schemas[schema_name]

                logger.error(f"Schema {schema_name} not found in components.schemas")
                error_msg = f"Schema {schema_name} not found in components.schemas"
                logger.error(error_msg)
                raise ValueError(error_msg)

            except KeyError as e:
                error_msg = f"Error accessing components.schemas: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)

        logger.info("Using standard navigation through component path")
        logger.info(f"Navigating to component: {component}")
        components = component.split(".")
        result = self.schemas[normalized]

        try:
            for comp in components:
                if comp in result:
                    result = result[comp]
                else:
                    error_msg = f"Component {comp} not found in path {component}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
        except (TypeError, KeyError) as e:
            error_msg = f"Invalid component path {component}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Successfully retrieved component {component}")
        return result


logger.info("Creating a global schema registry instance for reuse")
_schema_registry = None


def get_schema_registry() -> SchemaRegistry:
    """
    Get the global schema registry instance.

    Returns:
        SchemaRegistry instance
    """
    global _schema_registry
    if _schema_registry is None:
        _schema_registry = SchemaRegistry()
    return _schema_registry
