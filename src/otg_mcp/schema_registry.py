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

    def __init__(self, custom_schemas_dir: Optional[str] = None):
        """
        Initialize the schema registry.

        Args:
            custom_schemas_dir: Optional path to custom schemas directory
        """
        logger.info("Initializing schema registry")
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self._available_schemas: Optional[List[str]] = None
        self._builtin_schemas_dir = os.path.join(os.path.dirname(__file__), "schemas")
        self._custom_schemas_dir = custom_schemas_dir

        logger.info(
            f"Schema registry initialized with built-in schemas directory: {self._builtin_schemas_dir}"
        )
        if self._custom_schemas_dir:
            logger.info(f"Custom schemas directory: {self._custom_schemas_dir}")

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
            self._available_schemas = []

            logger.debug("Checking custom schemas directory if specified")
            if self._custom_schemas_dir and os.path.exists(self._custom_schemas_dir):
                logger.info(
                    f"Scanning custom schemas directory: {self._custom_schemas_dir}"
                )
                try:
                    custom_schemas = [
                        d
                        for d in os.listdir(self._custom_schemas_dir)
                        if os.path.isdir(os.path.join(self._custom_schemas_dir, d))
                        and os.path.exists(
                            os.path.join(self._custom_schemas_dir, d, "openapi.yaml")
                        )
                    ]
                    self._available_schemas.extend(custom_schemas)
                    logger.info(
                        f"Found {len(custom_schemas)} schemas in custom directory"
                    )
                except Exception as e:
                    logger.warning(f"Error scanning custom schemas directory: {str(e)}")

            logger.debug("Checking built-in schemas directory")
            if os.path.exists(self._builtin_schemas_dir):
                logger.info(
                    f"Scanning built-in schemas directory: {self._builtin_schemas_dir}"
                )
                built_in_schemas = [
                    d
                    for d in os.listdir(self._builtin_schemas_dir)
                    if os.path.isdir(os.path.join(self._builtin_schemas_dir, d))
                    and os.path.exists(
                        os.path.join(self._builtin_schemas_dir, d, "openapi.yaml")
                    )
                ]

                logger.debug(
                    "Adding built-in schemas that don't conflict with custom schemas"
                )
                for schema in built_in_schemas:
                    if schema not in self._available_schemas:
                        self._available_schemas.append(schema)

                logger.info(
                    f"Found {len(built_in_schemas)} schemas in built-in directory"
                )

            logger.info(f"Total available schemas: {len(self._available_schemas)}")

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

    def _load_schema_from_path(self, path: str, version: str, source_type: str) -> bool:
        """
        Load schema from a specified path into the cache.

        Args:
            path: Path to the schema file
            version: Version identifier to use in cache
            source_type: Source type for logging ('custom' or 'built-in')

        Returns:
            True if schema was loaded successfully, False otherwise
        """
        logger.info(f"Loading schema from {source_type} path: {path}")
        try:
            with open(path, "r") as f:
                self.schemas[version] = yaml.safe_load(f)
            logger.info(f"Successfully loaded schema from {source_type} path")
            return True
        except Exception as e:
            logger.error(f"Error loading schema from {source_type} path: {str(e)}")
            return False

    def _parse_version(self, version: str) -> tuple:
        """
        Parse a version string into a comparable tuple.

        Args:
            version: Version string (e.g. "1_30_0", "1.30.0")

        Returns:
            Tuple of integers representing the version
        """
        parts = version.replace(".", "_").split("_")
        try:
            return tuple(int(part) for part in parts if part.isdigit())
        except ValueError:
            logger.warning(f"Could not parse all parts of version: {version}")
            return tuple()

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
            logger.debug("Checking custom schemas directory first if specified")
            success = False
            if self._custom_schemas_dir:
                custom_schema_path = os.path.join(
                    self._custom_schemas_dir, normalized, "openapi.yaml"
                )
                if os.path.exists(custom_schema_path):
                    success = self._load_schema_from_path(
                        custom_schema_path, normalized, "custom"
                    )

            logger.debug("Trying built-in path if not loaded from custom path")
            if not success:
                builtin_schema_path = os.path.join(
                    self._builtin_schemas_dir, normalized, "openapi.yaml"
                )
                if not self._load_schema_from_path(
                    builtin_schema_path, normalized, "built-in"
                ):
                    raise ValueError(f"Error loading schema {normalized}")

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

    def _get_parsed_versions(self, available_versions: List[str]) -> List[tuple]:
        """
        Parse a list of version strings into a list of (version_string, version_tuple) pairs.

        Args:
            available_versions: List of version strings

        Returns:
            List of tuples (version_string, version_tuple)
        """
        parsed_versions = []
        for version in available_versions:
            ver_tuple = self._parse_version(version)
            if ver_tuple:
                logger.debug("Including version tuple as it was successfully parsed")
                parsed_versions.append((version, ver_tuple))
        return parsed_versions

    def find_closest_schema_version(self, requested_version: str) -> str:
        """
        Find closest matching schema version from available schemas.

        Logic:
        1. Exact match if available
        2. Same major.minor with equal or lower patch
        3. Same major with highest available minor
        4. Latest available version as fallback

        Args:
            requested_version: The version to find a match for

        Returns:
            The closest matching available schema version

        Raises:
            ValueError: If no schemas are available
        """
        logger.info(f"Finding closest schema version to: {requested_version}")
        available_versions = self.get_available_schemas()

        if not available_versions:
            error_msg = "No schema versions available"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug("Checking for exact schema version match first")
        normalized = self._normalize_version(requested_version)
        if normalized in available_versions:
            logger.info(
                f"Found exact schema match for {requested_version}: {normalized}"
            )
            return normalized

        logger.debug("Parsing the requested version")
        req_version = self._parse_version(requested_version)
        if not req_version:
            logger.debug("Unable to parse version, returning latest schema version")
            return self.get_latest_schema_version()

        logger.debug(
            "Ensuring requested version has at least 3 components (major.minor.patch)"
        )
        if len(req_version) < 3:
            logger.debug("Padding requested version with zeros for missing components")
            req_version = req_version + (0,) * (3 - len(req_version))

        logger.debug("Getting all parsed versions")
        parsed_versions = self._get_parsed_versions(available_versions)
        if not parsed_versions:
            error_msg = "No valid schema versions available"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug(
            "Finding schema versions with same major.minor and equal or lower patch"
        )
        same_major_minor = []
        for version, ver in parsed_versions:
            if (
                len(ver) >= 3
                and ver[0] == req_version[0]
                and ver[1] == req_version[1]
                and ver[2] <= req_version[2]
            ):
                same_major_minor.append((version, ver))

        if same_major_minor:
            logger.debug("Sorting by version tuple and taking the highest")
            closest = sorted(same_major_minor, key=lambda x: x[1])[-1][0]
            logger.info(
                f"Using version {closest} with same major.minor as {requested_version}"
            )
            return closest

        logger.debug("Finding schema versions with same major version")
        same_major = []
        for version, ver in parsed_versions:
            if ver and ver[0] == req_version[0]:
                same_major.append((version, ver))

        if same_major:
            logger.debug("Sorting by version tuple and taking the highest")
            closest = sorted(same_major, key=lambda x: x[1])[-1][0]
            logger.info(
                f"Using version {closest} with same major as {requested_version}"
            )
            return closest

        logger.debug("Fallback to latest overall schema version")
        latest = sorted(parsed_versions, key=lambda x: x[1])[-1][0]
        logger.info(
            f"No matching version found, falling back to latest version {latest}"
        )
        return latest

    def get_latest_schema_version(self) -> str:
        """
        Get the latest available schema version.

        Returns:
            The latest schema version

        Raises:
            ValueError: If no schemas are available
        """
        logger.info("Getting latest schema version")
        available_versions = self.get_available_schemas()

        if not available_versions:
            error_msg = "No schema versions available"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug("Parsing and sorting versions using helper method")
        parsed_versions = self._get_parsed_versions(available_versions)

        if not parsed_versions:
            error_msg = "No valid schema versions available"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug("Sorting by version tuple and taking the highest version")
        latest = sorted(parsed_versions, key=lambda x: x[1])[-1][0]
        logger.info(f"Latest available schema version: {latest}")
        return latest
