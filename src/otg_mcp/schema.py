"""
Helpers for working with the OpenAPI documents targets serve.

Schemas are always fetched from the target itself, so there is nothing here that
loads or resolves versioned schema files. This module only navigates a document
that has already been retrieved.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def extract_component(schema: Dict[str, Any], component: str) -> Any:
    """Pull one component out of an OpenAPI document by dotted path.

    Args:
        schema: Parsed OpenAPI document
        component: Dotted path, e.g. "components.schemas.Flow"

    Returns:
        The addressed fragment of the document

    Raises:
        ValueError: If the path does not resolve
    """
    logger.info(f"Checking if component path requires special handling: {component}")
    if component.startswith("components.schemas."):
        logger.debug("Using special handling for components.schemas.X path")
        schema_name = component[len("components.schemas.") :]
        logger.debug(f"Extracted schema name: {schema_name}")

        try:
            schemas = schema["components"]["schemas"]

            logger.debug(f"Checking if schema {schema_name} exists directly")
            if schema_name in schemas:
                logger.info(f"Found schema {schema_name}")
                return schemas[schema_name]

            error_msg = f"Schema {schema_name} not found in components.schemas"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except KeyError as e:
            error_msg = f"Error accessing components.schemas: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    logger.info(f"Navigating to component: {component}")
    result: Any = schema

    try:
        for comp in component.split("."):
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
