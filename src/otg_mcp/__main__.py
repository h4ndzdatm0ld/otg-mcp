import logging
import sys
import traceback

from .server import run_server

logger = logging.getLogger(__name__)

logger.info("Setting logging level to INFO for all otg_mcp modules")
for name in logging.root.manager.loggerDict:
    if name.startswith("otg_mcp"):
        logging.getLogger(name).setLevel(logging.INFO)

if __name__ == "__main__":
    try:
        logger.info("Starting OTG MCP Server via __main__")

        logger.info("Logging Python environment information")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Python executable: {sys.executable}")

        logger.info("Starting OTG MCP server via run_server()")
        run_server()
        logger.info("Server execution completed normally")
        sys.exit(0)
    except ImportError as e:
        error_message = f"IMPORT ERROR: Failed to import required module: {str(e)}"
        logger.critical(error_message)
        logger.critical(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
    except Exception as e:
        error_message = f"CRITICAL ERROR: Server failed to start: {str(e)}"
        logger.critical(error_message)
        logger.critical(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
