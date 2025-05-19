#!/usr/bin/env python3
"""
OTG-MCP Packet Capture Example

This script demonstrates how to perform packet capture operations with traffic generators
using the Open Traffic Generator (OTG) Model Context Protocol (MCP). The example showcases
best practices for implementing capture functionality in both standalone mode and with
traffic generation.

# Packet Capture Architecture

The packet capture process with OTG follows these key steps:

1. Configuration Phase:
   - Define port(s) with proper locations in the configuration
   - Add capture configuration to the ports you want to capture on
   - Apply the configuration to the traffic generator using set_config()

2. Start Capture Phase:
   - Create a control_state object with PORT choice
   - Set port.choice to CAPTURE
   - Set port.capture.state to START
   - Specify port_names to capture on
   - Apply using set_control_state()

3. Traffic Generation Phase (Optional):
   - Start traffic using traffic.flow_transmit.START if needed
   - Wait for traffic to complete or for a specified duration

4. Stop Capture Phase:
   - Create a control_state object with PORT choice
   - Set port.choice to CAPTURE
   - Set port.capture.state to STOP
   - Specify same port_names as in start phase
   - Apply using set_control_state()

5. Retrieve Capture Phase:
   - Create a capture_request object
   - Set port_name to the port to retrieve from
   - Call get_capture() to retrieve the PCAP data
   - Write the data to a file

# Port Configuration Considerations

For successful packet capture, ports must be properly configured:
- Ports must be defined with correct locations (IP:port format)
- Ports must be included in the captures configuration
- Port names must match between configuration and control state operations

# API Compatibility Notes

Different target versions may have variations in capture API:
- Some targets use direct capture_state() method
- Others use control_state() with PORT choice
- Port location must be valid and accessible from the client

# Usage Examples

1. Basic packet capture:
   python capture_example.py --api https://api:8443 --port p1 --port-location server:5555

2. Capture with traffic generation:
   python capture_example.py --api https://api:8443 --run-traffic --tx-port p1:server1:5555 --rx-port p2:server2:5556
"""

import argparse
import logging
import os
import sys
import time
import uuid

import snappi


def configure_ports_with_capture(api, port_names_and_locations):
    """
    Configure ports with capture capability.

    Args:
        api: Snappi API instance
        port_names_and_locations: Dictionary of {port_name: location}

    Returns:
        Configuration object with ports and captures configured
    """
    logger.info("Configuring ports with capture capability")

    # Create config
    config = api.config()

    # Add ports to config
    for port_name, location in port_names_and_locations.items():
        config.ports.port(name=port_name, location=location)
        logger.info(f"Added port {port_name} at location {location}")

    # Configure capture
    if not hasattr(config, "captures"):
        logger.error("Configuration does not support captures")
        return None

    cap = config.captures.capture(name="port_capture")[-1]
    cap.port_names = list(port_names_and_locations.keys())
    logger.info(f"Configured capture on ports: {cap.port_names}")

    # Apply configuration
    logger.info("Applying port and capture configuration")
    result = api.set_config(config)

    if hasattr(result, "warnings") and result.warnings:
        logger.info(f"Configuration warnings: {result.warnings}")

    return config


def start_capture(api, port_names):
    """
    Start packet capture on specified ports.

    Args:
        api: Snappi API instance
        port_names: List of port names to capture on

    Returns:
        True if capture started successfully, False otherwise
    """
    logger.info(f"Starting packet capture on ports: {port_names}")

    try:
        # Create control state
        cs = api.control_state()
        cs.choice = cs.PORT
        cs.port.choice = cs.port.CAPTURE
        cs.port.capture.state = cs.port.capture.START
        cs.port.capture.port_names = port_names

        # Apply control state
        result = api.set_control_state(cs)

        if hasattr(result, "warnings") and result.warnings:
            logger.info(f"Start capture warnings: {result.warnings}")

        return True
    except Exception as e:
        logger.error(f"Error starting capture: {e}")
        return False


def stop_capture(api, port_names):
    """
    Stop packet capture on specified ports.

    Args:
        api: Snappi API instance
        port_names: List of port names to stop capture on

    Returns:
        True if capture stopped successfully, False otherwise
    """
    logger.info(f"Stopping packet capture on ports: {port_names}")

    try:
        # Create control state
        cs = api.control_state()
        cs.choice = cs.PORT
        cs.port.choice = cs.port.CAPTURE
        cs.port.capture.state = cs.port.capture.STOP
        cs.port.capture.port_names = port_names

        # Apply control state
        result = api.set_control_state(cs)

        if hasattr(result, "warnings") and result.warnings:
            logger.info(f"Stop capture warnings: {result.warnings}")

        return True
    except Exception as e:
        logger.error(f"Error stopping capture: {e}")
        return False


def get_capture(api, port_name, output_dir=None, filename=None):
    """
    Get capture data from a port and save to a file.

    Args:
        api: Snappi API instance
        port_name: Name of port to get capture from
        output_dir: Directory to save capture file (default: /tmp)
        filename: Name of the output file (default: auto-generated based on port name)

    Returns:
        Path to saved capture file if successful, None otherwise
    """
    try:
        # Set default output directory
        if output_dir is None:
            output_dir = "/tmp"

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename if not provided
        if filename is None:
            filename = f"capture_{port_name}_{uuid.uuid4().hex[:8]}.pcap"
        elif not filename.endswith('.pcap'):
            # Ensure filename has .pcap extension
            filename = f"{filename}.pcap"

        file_path = os.path.join(output_dir, filename)
        logger.info(f"Getting capture data for port {port_name}")

        # Create capture request
        req = api.capture_request()
        req.port_name = port_name

        # Get capture data
        logger.info(f"Saving capture data to {file_path}")
        pcap_bytes = api.get_capture(req)

        # Save to file
        with open(file_path, 'wb') as pcap_file:
            pcap_file.write(pcap_bytes.read())

        logger.info(f"Capture successfully saved to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error getting capture data: {e}")
        return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("capture-example")


def run_capture_test(api_address, port_name, verify_ssl=False, output_dir=None, duration=5, port_location=None):
    """
    Run a complete packet capture test using the refactored capture functions.

    Args:
        api_address: Address of the traffic generator API
        port_name: Name of the port to capture on
        verify_ssl: Whether to verify SSL certificates
        output_dir: Directory to save the capture file (default: /tmp)
        duration: Duration to capture packets in seconds
        port_location: Optional location for the port (format: 'hostname:port')
        
    Returns:
        Path to the capture file if successful, None otherwise
    """
    logger.info(f"Connecting to traffic generator API at {api_address}")
    
    try:
        # Create snappi API client
        api = snappi.api(location=api_address, verify=verify_ssl)
        
        # If port_location is provided, use it. Otherwise, try to find it in the current config
        if port_location:
            logger.info(f"Using provided port location: {port_location}")
        else:
            # Try to get the port location from the current config
            logger.info("Getting current configuration to find port location")
            current_config = api.get_config()

            for port in current_config.ports:
                if port.name == port_name:
                    port_location = port.location
                    logger.info(f"Found existing port {port_name} at location {port_location}")
                    break

            # If port not found with location, use a default
            if port_location is None:
                # For actual traffic generator tests, we need a location with IP:port format
                port_location = "localhost:5555"
                logger.info(f"No location found for port {port_name}, using default location: {port_location}")

        # Configure ports with capture capability
        port_config = {port_name: port_location}
        config = configure_ports_with_capture(api, port_config)
        if not config:
            logger.error("Failed to configure port with capture capability")
            return None
            
        # Start packet capture
        if not start_capture(api, [port_name]):
            logger.error("Failed to start capture")
            return None

        # Wait for traffic to be captured
        logger.info(f"Capture started, running for {duration} seconds...")
        time.sleep(duration)
        
        # Stop packet capture
        if not stop_capture(api, [port_name]):
            logger.error("Failed to stop capture")
            return None

        # Get capture data and save to file
        filename = f"capture_{port_name}_{uuid.uuid4().hex[:8]}.pcap"
        file_path = get_capture(api, port_name, output_dir=output_dir, filename=filename)

        if file_path:
            logger.info("Capture test completed successfully")
            return file_path
        else:
            logger.error("Failed to retrieve capture data")
            return None

    except Exception as e:
        logger.error(f"Error during capture test: {str(e)}")
        return None


def wait_for_flow_metrics(api, expected_packets, timeout=30, interval=1):
    """
    Wait for flow metrics to match expected packet count.

    Args:
        api: Snappi API client
        expected_packets: Expected number of packets
        timeout: Maximum time to wait in seconds
        interval: Check interval in seconds
        
    Returns:
        True if metrics reached expected values, False otherwise
    """
    start_time = time.time()
    logger.info(f"Waiting for flow metrics to show {expected_packets} packets...")
    
    while time.time() - start_time < timeout:
        try:
            # Create metrics request
            req = api.metrics_request()
            req.flow.flow_names = []  # Get all flows
            
            # Get metrics
            res = api.get_metrics(req)
            flow_metrics = res.flow_metrics
            
            if not flow_metrics:
                logger.info("No flow metrics available yet")
                time.sleep(interval)
                continue

            # Check if packets match expected count
            tx_packets = sum(flow.frames_tx for flow in flow_metrics)
            rx_packets = sum(flow.frames_rx for flow in flow_metrics)
            
            logger.info(f"Current metrics - Tx: {tx_packets}, Rx: {rx_packets}, Expected: {expected_packets}")

            if tx_packets == expected_packets and rx_packets == expected_packets:
                logger.info("Flow metrics match expected packet count")
                return True
        except Exception as e:
            logger.warning(f"Error getting metrics: {e}")

        time.sleep(interval)
        
    logger.warning(f"Timeout waiting for metrics to match expected packet count: {expected_packets}")
    return False


def create_and_run_traffic_with_capture(api_address, tx_port, rx_port, packet_count=10, verify_ssl=False, output_dir=None):
    """
    Create a traffic configuration, run traffic with capture, and save the capture.

    Args:
        api_address: Address of the traffic generator API
        tx_port: Transmit port name and location (name:location)
        rx_port: Receive port name and location (name:location)
        packet_count: Number of packets to send
        verify_ssl: Whether to verify SSL certificates
        output_dir: Directory to save capture files
        
    Returns:
        Dictionary with capture file paths
    """
    logger.info(f"Setting up traffic and capture between ports {tx_port} and {rx_port}")

    # Parse port information
    tx_name, tx_location = tx_port.split(":", 1)
    rx_name, rx_location = rx_port.split(":", 1)

    # Create API client
    api = snappi.api(location=api_address, verify=verify_ssl)

    # Create config with ports
    cfg = api.config()
    # Add ports to the config (no need to store references as we don't use them)
    cfg.ports.port(name=tx_name, location=tx_location)
    cfg.ports.port(name=rx_name, location=rx_location)

    # Configure capture on both ports
    cap = cfg.captures.capture(name="traffic_capture")[-1]
    cap.port_names = [tx_name, rx_name]

    # Create a basic flow
    flow = cfg.flows.flow(name="simple_flow")[-1]
    flow.tx_rx.port.tx_name = tx_name
    flow.tx_rx.port.rx_name = rx_name

    # Configure packet with Ethernet + IPv4 headers
    eth, ip = flow.packet.ethernet().ipv4()
    eth.src.value = "00:11:22:33:44:55"
    eth.dst.value = "00:11:22:33:44:66"
    ip.src.value = "192.168.1.1"
    ip.dst.value = "192.168.1.2"

    # Set flow duration to fixed packet count
    flow.duration.fixed_packets.packets = packet_count
    flow.metrics.enable = True

    # Apply configuration
    logger.info("Applying traffic and capture configuration")
    api.set_config(cfg)

    # Start capture
    logger.info("Starting packet capture")
    cs = api.control_state()
    cs.choice = cs.PORT
    cs.port.choice = cs.port.CAPTURE
    cs.port.capture.state = cs.port.capture.START
    cs.port.capture.port_names = cap.port_names
    api.set_control_state(cs)

    # Start traffic
    logger.info("Starting traffic transmission")
    ts = api.control_state()
    ts.choice = ts.TRAFFIC
    ts.traffic.choice = ts.traffic.FLOW_TRANSMIT
    ts.traffic.flow_transmit.state = ts.traffic.flow_transmit.START
    api.set_control_state(ts)

    # Wait for traffic to complete
    wait_for_flow_metrics(api, packet_count)

    # Stop capture
    logger.info("Stopping packet capture")
    cs = api.control_state()
    cs.choice = cs.PORT
    cs.port.choice = cs.port.CAPTURE
    cs.port.capture.state = cs.port.capture.STOP
    cs.port.capture.port_names = cap.port_names
    api.set_control_state(cs)

    # Prepare output directory
    if output_dir is None:
        output_dir = "/tmp"
    os.makedirs(output_dir, exist_ok=True)
    
    # Get capture data from both ports
    captures = {}
    for port_name in cap.port_names:
        # Use custom filename based on port name
        filename = f"{port_name}_capture.pcap"

        # Use our modular get_capture function
        file_path = get_capture(api, port_name, output_dir=output_dir, filename=filename)

        if file_path:
            captures[port_name] = file_path
        else:
            logger.error(f"Failed to get capture data for port {port_name}")
            
    return captures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Packet capture example using snappi API")
    parser.add_argument("--api", default="https://localhost:8443", help="Traffic generator API address")
    parser.add_argument("--port", default="p1", help="Port name to capture on")
    parser.add_argument("--port-location", help="Port location (e.g. 'localhost:5555')")
    parser.add_argument("--no-verify", action="store_true", help="Disable SSL verification")
    parser.add_argument("--output", help="Directory to save capture file (default: /tmp)")
    parser.add_argument("--duration", type=int, default=5, help="Capture duration in seconds")
    parser.add_argument("--run-traffic", action="store_true", help="Create and run traffic in addition to capture")
    parser.add_argument("--tx-port", help="Traffic transmit port (format: name:location)")
    parser.add_argument("--rx-port", help="Traffic receive port (format: name:location)")
    parser.add_argument("--packet-count", type=int, default=10, help="Number of packets to send")

    args = parser.parse_args()

    verify_ssl = not args.no_verify

    if args.run_traffic:
        if not args.tx_port or not args.rx_port:
            print("When using --run-traffic, both --tx-port and --rx-port are required")
            sys.exit(1)

        captures = create_and_run_traffic_with_capture(
            api_address=args.api,
            tx_port=args.tx_port,
            rx_port=args.rx_port,
            packet_count=args.packet_count,
            verify_ssl=verify_ssl,
            output_dir=args.output
        )

        if captures:
            print("\nCapture completed successfully!")
            for port, file_path in captures.items():
                print(f"PCAP file for {port} saved to: {file_path}")
            sys.exit(0)
        else:
            print("\nCapture test failed!")
            sys.exit(1)
    else:
        # Create port_kwargs dict with port_location if specified
        port_kwargs = {}
        if args.port_location:
            port_kwargs['port_location'] = args.port_location

        file_path = run_capture_test(
            api_address=args.api,
            port_name=args.port,
            verify_ssl=verify_ssl,
            output_dir=args.output,
            duration=args.duration,
            **port_kwargs
        )

        if file_path:
            print("\nCapture completed successfully!")
            print(f"PCAP file saved to: {file_path}")
            sys.exit(0)
        else:
            print("\nCapture test failed!")
            sys.exit(1)
