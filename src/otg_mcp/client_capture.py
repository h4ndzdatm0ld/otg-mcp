"""
OTG Client Capture module providing specialized capture functionality.

This module contains improved implementations for packet capture operations
with proper control state handling.
"""

import logging
import os
import uuid
from typing import Dict, List, Optional, Union, Any

logger = logging.getLogger(__name__)


def start_capture(api: Any, port_names: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Start packet capture on one or more ports with proper control state handling.

    Args:
        api: Snappi API client
        port_names: List or single name of port(s) to capture on

    Returns:
        Dictionary with status and result information
    """
    logger.info(f"Starting capture for ports: {port_names}")

    logger.debug("Converting port names to list for consistent handling")
    port_list = [port_names] if isinstance(port_names, str) else list(port_names)

    try:
        logger.debug("Creating control state with all required choices properly set")
        cs = api.control_state()

        logger.debug("Setting first-level choice to PORT")
        cs.choice = cs.PORT

        logger.debug("Setting second-level choice to CAPTURE for port control state")
        cs.port.choice = cs.port.CAPTURE

        logger.debug("Setting third-level choice: capture state to START")
        cs.port.capture.state = cs.port.capture.START

        logger.debug(f"Setting port names to capture on: {port_list}")
        cs.port.capture.port_names = port_list

        logger.debug("Applying control state")
        logger.info(f"Setting control state to start capture on ports: {port_list}")
        result = api.set_control_state(cs)

        logger.debug("Checking for warnings in the result")
        warnings = []
        if hasattr(result, "warnings") and result.warnings:
            warnings = result.warnings
            logger.info(f"Start capture warnings: {warnings}")

        return {"status": "success", "warnings": warnings}

    except Exception as e:
        logger.error(f"Error starting capture: {e}")
        return {"status": "error", "error": str(e)}


def stop_capture(api: Any, port_names: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Stop packet capture on one or more ports with proper control state handling.

    Args:
        api: Snappi API client
        port_names: List or single name of port(s) to stop capture on

    Returns:
        Dictionary with status and result information
    """
    logger.info(f"Stopping capture for ports: {port_names}")

    logger.debug("Converting port names to list for consistent handling")
    port_list = [port_names] if isinstance(port_names, str) else list(port_names)

    try:
        logger.debug("Creating control state with all required choices properly set")
        cs = api.control_state()

        logger.debug("Setting first-level choice to PORT")
        cs.choice = cs.PORT

        logger.debug("Setting second-level choice to CAPTURE for port control state")
        cs.port.choice = cs.port.CAPTURE

        logger.debug("Setting third-level choice: capture state to STOP")
        cs.port.capture.state = cs.port.capture.STOP

        logger.debug(f"Setting port names to capture on: {port_list}")
        cs.port.capture.port_names = port_list

        logger.debug("Applying control state")
        logger.info(f"Setting control state to stop capture on ports: {port_list}")
        result = api.set_control_state(cs)

        logger.debug("Checking for warnings in the result")
        warnings = []
        if hasattr(result, "warnings") and result.warnings:
            warnings = result.warnings
            logger.info(f"Stop capture warnings: {warnings}")

        return {"status": "success", "warnings": warnings}

    except Exception as e:
        logger.error(f"Error stopping capture: {e}")
        return {"status": "error", "error": str(e)}


def get_capture(
    api: Any,
    port_name: str,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get capture data from a port and save it to a file.

    Args:
        api: Snappi API client
        port_name: Name of port to get capture from
        output_dir: Directory to save the capture file (default: /tmp)
        filename: Optional custom filename (default: auto-generated)

    Returns:
        Dictionary with status, file path, and capture data info
    """
    logger.info(f"Getting capture data for port {port_name}")

    try:
        logger.debug("Setting default output directory if not provided")
        if output_dir is None:
            output_dir = "/tmp"

        logger.debug(f"Creating output directory if it doesn't exist: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)

        logger.debug("Handling filename generation")
        if filename is None:
            filename = f"capture_{port_name}_{uuid.uuid4().hex[:8]}.pcap"
            logger.debug(f"Generated unique filename: {filename}")
        elif not filename.endswith(".pcap"):
            logger.debug(f"Adding .pcap extension to filename: {filename}")
            filename = f"{filename}.pcap"

        file_path = os.path.join(output_dir, filename)
        logger.info(f"Will save capture data to {file_path}")

        logger.debug("Creating capture request with port name")
        req = api.capture_request()
        req.port_name = port_name

        logger.debug("Requesting capture data from the device")
        logger.info("Retrieving capture data")
        pcap_bytes = api.get_capture(req)

        logger.debug("Writing capture data to output file")
        with open(file_path, "wb") as pcap_file:
            pcap_file.write(pcap_bytes.read())

        logger.info(f"Capture successfully saved to {file_path}")

        return {
            "status": "success",
            "file_path": file_path,
            "capture_id": filename,
            "port": port_name,
            "size_bytes": os.path.getsize(file_path),
        }

    except Exception as e:
        logger.error(f"Error getting capture data: {e}")
        return {
            "status": "error",
            "error": str(e),
            "port": port_name,
            "file_path": None,
            "capture_id": None,
        }
