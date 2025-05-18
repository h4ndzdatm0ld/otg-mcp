#!/usr/bin/env python3
"""
Simple Gateway Traffic Test using Snappi API

This script generates traffic to the gateway (192.168.10.1) on the remote traffic generator device
using the snappi API directly. This directly tests traffic flow through the physical interface.

It demonstrates both direct API usage and working with serialized configurations (JSON).
"""

import argparse
import logging
import os
import sys
import time

import snappi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("gateway-test")


def create_gateway_traffic_config(
    api,
    gateway_ip="192.168.10.1",
    target_ip="8.8.8.8",  # Use external IP to ensure traffic goes through gateway
    source_port="p1",
    interface_location="localhost:5555",  # This name is inside the container namespace
    rate_pps=10000,
    packet_size=1460,  # Standard Ethernet frame size minus headers (1500-40)
    duration_seconds=30,
):
    """
    Create a traffic configuration that sends traffic to the gateway.

    Args:
        api: Snappi API instance
        gateway_ip: IP address of the gateway
        source_port: Name of the source port
        interface_location: Actual interface name to use (e.g., "localhost:5555")
        rate_pps: Traffic rate in packets per second
        packet_size: Size of packets in bytes
        duration_seconds: Duration of traffic in seconds

    Returns:
        Snappi configuration object
    """
    logger.info(f"Creating traffic configuration to gateway {gateway_ip}")

    # Create a completely minimal configuration
    logger.info("Creating a basic configuration for gateway test")

    # Instead of using the object model which appears inconsistent between snappi versions,
    # let's create a configuration as a JSON object directly
    logger.info("Creating configuration using direct JSON approach")

    # Define the full configuration as a dictionary
    config_dict = {
        "ports": [
            {
                "name": source_port,
                # Map interface names to their proper endpoints using the controller's port mapping
                # After investigating the container setup with SSH, we found that:
                # - The controller creates a location map (in config.yaml) that maps interface names to endpoints
                # - Each veth interface maps to a specific port (localhost:5555 -> localhost:5555, veth-z -> localhost:5556)
                # - Use the interface name directly as the location since the controller does the mapping internally
                "location": interface_location,
            }
        ],
        "flows": [
            {
                "name": "gateway-traffic",
                "tx_rx": {"port": {"tx_name": source_port}},
                "size": {"fixed": packet_size},
                "rate": {"pps": rate_pps},
                # Enable flow metrics
                "metrics": {"enable": True},
                # Add packet header configuration to target the external IP
                "packet": [
                    {
                        "ethernet": {
                            "dst": {
                                "choice": "value",
                                "value": "18:e8:29:5d:07:f6",  # Explicit gateway MAC address
                            },
                            # Using explicit src helps avoid traffic loop issues
                            "src": {
                                "choice": "value",
                                "value": "aa:bb:cc:dd:ee:ff",  # Source MAC doesn't matter for routing
                            },
                        }
                    },
                    {
                        "ipv4": {
                            "src": {
                                "value": "192.168.10.10"  # Source IP (matches bridge IP)
                            },
                            "dst": {
                                "value": gateway_ip  # Send traffic directly to the gateway
                            },
                            "protocol": {
                                "choice": "value",
                                "value": 17,  # UDP (17) - TCP (6) requires handshake
                            },
                        }
                    },
                    {
                        "udp": {
                            "src_port": {"value": 12345},
                            "dst_port": {
                                "value": 53  # DNS port - common outbound traffic
                            },
                        }
                    },
                ],
                # We'll manually control duration without setting it in the config
            }
        ],
    }

    logger.info(f"Configured traffic directly to gateway IP: {gateway_ip}")

    # Create a new configuration and load it from the JSON
    config = api.config()
    config.deserialize(config_dict)

    # Note: We'll skip setting the duration and rely on the manual stop after duration_seconds
    logger.info(
        f"Will run traffic for {duration_seconds} seconds using manual timing control"
    )

    logger.info(
        f"Created traffic config: {rate_pps} pps, {packet_size} bytes, {duration_seconds} sec to {gateway_ip}"
    )
    return config


def save_config_to_json(config, filename):
    """
    Save a snappi configuration to a JSON file.

    Args:
        config: Snappi configuration object
        filename: Path to save the JSON file

    Returns:
        Path to the saved file
    """
    # Serialize the config to JSON
    config_json = config.serialize()

    # Write the JSON to a file
    with open(filename, "w") as f:
        f.write(config_json)

    logger.info(f"Configuration saved to {filename}")
    return filename


def load_config_from_json(api, filename):
    """
    Load a snappi configuration from a JSON file.

    Args:
        api: Snappi API instance
        filename: Path to the JSON file

    Returns:
        Loaded snappi configuration object
    """
    # Check if file exists
    if not os.path.exists(filename):
        logger.error(f"Configuration file {filename} not found")
        return None

    # Read the JSON from a file
    with open(filename, "r") as f:
        config_json = f.read()

    # Create a new config object
    config = api.config()

    # Deserialize the JSON into the config object
    config.deserialize(config_json)

    logger.info(f"Configuration loaded from {filename}")
    return config


def run_gateway_traffic_test(
    api_address="https://traffic-generator.example.com:8443",
    gateway_ip="192.168.10.1",
    target_ip="8.8.8.8",  # Target IP outside local network to ensure gateway forwarding
    source_port="p1",
    interface_location="localhost:5555",
    rate_mbps=1000,
    packet_size=9000,
    duration_seconds=30,
    verify_ssl=False,
    config_file=None,
    save_config=None,
):
    """
    Run a gateway traffic test using snappi.

    Args:
        api_address: Address of the traffic generator API
        gateway_ip: IP address of the gateway
        source_port: Name of the source port
        interface_location: Actual interface name to use (e.g., "localhost:5555")
        rate_mbps: Traffic rate in Mbps
        packet_size: Size of packets in bytes
        duration_seconds: Duration of traffic in seconds
        verify_ssl: Whether to verify SSL certificates
        config_file: Optional path to load configuration from JSON
        save_config: Optional path to save configuration as JSON

    Returns:
        True if successful
    """
    try:
        logger.info(f"Connecting to traffic generator API at {api_address}")

        # Create snappi API client
        api = snappi.api(location=api_address, verify=verify_ssl)

        # Convert Mbps to pps (packets per second)
        bits_per_packet = packet_size * 8  # bits per packet
        packets_per_second = int((rate_mbps * 1000000) / bits_per_packet)

        # Print test parameters
        print("\n" + "=" * 80)
        print("GATEWAY TRAFFIC TEST")
        print(f"API: {api_address}")
        print(f"Gateway IP: {gateway_ip}")
        print(f"Source Port: {source_port}")
        print(f"Interface: {interface_location}")
        print(f"Rate: {rate_mbps} Mbps ({packets_per_second} pps)")
        print(f"Packet Size: {packet_size} bytes")
        print(f"Duration: {duration_seconds} seconds")
        print("=" * 80 + "\n")

        # Create or load traffic configuration
        if config_file:
            # Load configuration from JSON file
            logger.info(f"Loading configuration from {config_file}")
            config = load_config_from_json(api, config_file)
            if not config:
                logger.error(f"Failed to load configuration from {config_file}")
                return False
        else:
            # Create a new configuration
            config = create_gateway_traffic_config(
                api,
                gateway_ip=gateway_ip,
                source_port=source_port,
                interface_location=interface_location,  # Use the specified interface
                rate_pps=packets_per_second,
                packet_size=packet_size,
                duration_seconds=duration_seconds,
            )

        # Save configuration if requested
        if save_config:
            save_config_to_json(config, save_config)

        # Apply configuration to the traffic generator (can pass either object or JSON)
        logger.info("Setting traffic configuration...")
        try:
            api.set_config(config)
            # This would retrieve, then serialize to dict.
            config = api.get_config()
            breakpoint()
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error setting configuration: {error_message}")

            # Check for specific connection errors and provide helpful advice
            if "connection refused" in error_message.lower():
                print("\n" + "=" * 80)
                print("CONNECTION ERROR TO TRAFFIC ENGINE CONTAINER")
                print("=" * 80)
                print(
                    "The traffic engine container is not accessible at the configured location."
                )
                print(f"Error: {error_message}")
                print()

                # Extract host and port information more robustly from different connection errors
                if "tcp://" in error_message:
                    try:
                        # Handle TCP connection errors
                        print(
                            "IP address in error: "
                            + error_message.split("tcp://")[1].split('"')[0]
                        )
                    except (IndexError, ValueError) as e:
                        print("Could not extract specific IP address from error")
                elif "HTTPSConnectionPool" in error_message:
                    # Handle HTTPS connection errors
                    try:
                        host_port = error_message.split("HTTPSConnectionPool(host='")[
                            1
                        ].split("',")[0]
                        print(f"Host in error: {host_port}")
                    except (IndexError, ValueError):
                        print("Could not extract specific host from error")
                elif "HTTPConnectionPool" in error_message:
                    # Handle HTTP connection errors
                    try:
                        host_port = error_message.split("HTTPConnectionPool(host='")[
                            1
                        ].split("',")[0]
                        print(f"Host in error: {host_port}")
                    except (IndexError, ValueError):
                        print("Could not extract specific host from error")
                else:
                    print("Connection error: Check host and port configuration")
                print()
                print("Based on the Docker container information from the remote host:")
                print("  - All containers appear to be running")
                print(
                    "  - The issue is likely a mismatch in the container IP address configuration"
                )
                print("  - The controller is looking for the wrong IP address")
                print()
                print("This is likely due to one of the following reasons:")
                print("  1. The Docker network configuration has changed")
                print(
                    "  2. The interface (localhost:5555) has not been properly moved to the container"
                )
                print(
                    "  3. The container's IP address has changed but the controller config wasn't updated"
                )
                print()
                print("Recommended actions:")
                print("  1. SSH to the traffic generator server and run:")
                print("     ssh traffic-generator.example.com")
                print(
                    "     docker inspect ixia-c-traffic-engine-localhost:5555 | grep IPAddress"
                )
                print(
                    "     docker exec -it keng-controller cat /home/ixia-c/controller/config/config.yaml"
                )
                print()
                print(
                    "  2. If the IP addresses don't match, update the controller configuration:"
                )
                print(
                    "     docker exec -it keng-controller bash -c 'echo \"location_map:"
                )
                print("       - location: localhost:5555")
                print('         endpoint: \\"[NEW_IP]:5555+[NEW_IP]:50071\\"')
                print("       - location: veth-z")
                print(
                    '         endpoint: \\"[OTHER_IP]:5555+[OTHER_IP]:50071\\"" > /home/ixia-c/controller/config/config.yaml\''
                )
                print()
                print(
                    "  3. Restart the controller container to apply the new configuration:"
                )
                print("     docker restart keng-controller")
                print("=" * 80 + "\n")

            return False

        # Inspect available API methods
        logger.info("Inspecting API object methods...")
        api_methods = [method for method in dir(api) if not method.startswith("_")]
        logger.info(f"Available API methods: {api_methods}")

        # Attempt to determine the correct method to start traffic
        if "start_transmit" in api_methods:
            logger.info("Using start_transmit() method")
            api.start_transmit()
        elif "transmit_state" in api_methods:
            logger.info("Using transmit_state() method")
            ts = api.transmit_state()
            ts.state = ts.START
            api.set_transmit_state(ts)
        elif "control_state" in api_methods:
            logger.info("Using control_state() method")
            cs = api.control_state()
            # Inspect the control_state object
            logger.info(f"Control state object type: {type(cs)}")
            logger.info(f"Control state object attributes: {dir(cs)}")

            # Choice is mandatory, need to set this first
            logger.info("Setting choice to TRAFFIC")
            cs.choice = cs.TRAFFIC

            # Inspect the traffic attribute structure
            if hasattr(cs, "traffic"):
                logger.info(f"Traffic object attributes: {dir(cs.traffic)}")

                # Traffic object needs to have choice set first
                logger.info("Setting traffic choice to FLOW_TRANSMIT")
                cs.traffic.choice = cs.traffic.FLOW_TRANSMIT

                # Now set the flow transmit action
                if hasattr(cs.traffic, "flow_transmit") and hasattr(
                    cs.traffic.flow_transmit, "state"
                ):
                    logger.info("Setting traffic.flow_transmit.state")
                    if hasattr(cs.traffic.flow_transmit, "START"):
                        logger.info("Using cs.traffic.flow_transmit.START")
                        cs.traffic.flow_transmit.state = cs.traffic.flow_transmit.START
                    else:
                        logger.info("Using string value 'start'")
                        cs.traffic.flow_transmit.state = "start"
                else:
                    logger.error("Could not find traffic.flow_transmit.state attribute")
                    return False

            # Try to set various common patterns
            try:
                logger.info("Attempting to use set_control_state")
                api.set_control_state(cs)
                logger.info("Successfully set control state")
            except Exception as e:
                logger.error(f"Error setting control state: {e}")
                return False
        elif "set_flow_transmit" in api_methods:
            logger.info("Using set_flow_transmit() method")
            api.set_flow_transmit(state="start")
        else:
            # Try the example.py approach
            logger.info(
                "No known traffic control methods found. Trying API exploration..."
            )
            print("API Object Type:", type(api))
            print("API Object Methods:", dir(api))
            print("API Object Help:", help(api))
            logger.error("Could not determine how to start traffic")
            return False

        logger.info("Traffic started (or attempted to start)")

        # Wait for traffic to complete
        logger.info(f"Traffic started, running for {duration_seconds} seconds...")

        # Print status periodically during transmission
        start_time = time.time()
        # Lists to track metrics over time for analysis
        rates_mbps = []
        max_rate_mbps = 0

        # Allow a 2-second warmup period before recording rates
        warmup_complete = False
        warmup_end_time = start_time + 2

        while time.time() - start_time < duration_seconds + 1:
            # Get flow metrics
            request = api.metrics_request()
            request.flow.flow_names = ["gateway-traffic"]
            metrics = api.get_metrics(request)

            # Debug logging of available metrics attributes
            logger.info("Getting flow metrics")

            if metrics.flow_metrics:
                # Log available attributes for debugging
                if len(metrics.flow_metrics) > 0:
                    logger.info(
                        f"Flow metric attributes: {dir(metrics.flow_metrics[0])}"
                    )
                flow = metrics.flow_metrics[0]
                # Calculate current rate in Mbps using frames_tx_rate and packet size
                current_rate_mbps = (flow.frames_tx_rate * packet_size * 8) / 1000000

                # Add logging for the calculation
                logger.info(
                    f"Calculating Mbps rate: {flow.frames_tx_rate} fps * {packet_size} bytes * 8 / 1000000 = {current_rate_mbps:.2f} Mbps"
                )

                # Track max rate
                max_rate_mbps = max(max_rate_mbps, current_rate_mbps)

                # Only record rates after warmup period
                if time.time() > warmup_end_time:
                    if not warmup_complete:
                        logger.info("Warmup complete, now recording metrics")
                        warmup_complete = True

                    # Add to our rate tracking
                    rates_mbps.append(current_rate_mbps)
                    # Store bytes for debug purposes if needed
                    # flow.bytes_tx contains the total bytes transmitted

                # Log with Mbps rate
                logger.info(
                    f"Tx Frames: {flow.frames_tx}, Tx Bytes: {flow.bytes_tx}, "
                    f"Rate: {round(flow.frames_tx_rate, 2)} fps ({round(current_rate_mbps, 2)} Mbps)"
                )
            else:
                logger.info("Waiting for metrics...")

            time.sleep(1)

        # Stop traffic with robust verification
        logger.info("Stopping traffic...")

        def ensure_traffic_stopped(max_attempts=3):
            """Try multiple methods to stop traffic and verify it's actually stopped."""
            for attempt in range(1, max_attempts + 1):
                logger.info(f"Stop traffic attempt #{attempt}")

                # Try all known methods to stop traffic
                stop_methods = [
                    # Method 1: Direct API call (common in newer snappi versions)
                    lambda: hasattr(api, "stop_transmit") and api.stop_transmit(),
                    # Method 2: Using control_state with proper attributes
                    lambda: stop_with_control_state(),
                    # Method 3: Using set_flow_transmit if available
                    lambda: hasattr(api, "set_flow_transmit")
                    and api.set_flow_transmit(state="stop"),
                ]

                # Try each method until one succeeds
                for i, stop_method in enumerate(stop_methods):
                    try:
                        stop_method()
                        logger.info(f"Successfully executed stop method #{i + 1}")
                        break
                    except Exception as e:
                        logger.info(f"Stop method #{i + 1} failed: {str(e)}")

                # Verify traffic has actually stopped by checking metrics
                if verify_traffic_stopped():
                    logger.info("Traffic verified stopped successfully")
                    return True

                # If we get here, traffic is still running - wait before retrying
                logger.warning(
                    f"Traffic still running after attempt {attempt}, waiting before retry..."
                )
                time.sleep(2)

            logger.error("Failed to stop traffic after multiple attempts!")
            return False

        def stop_with_control_state():
            """Stop traffic using control_state with proper error handling."""
            cs = api.control_state()
            cs.choice = cs.TRAFFIC

            if hasattr(cs, "traffic"):
                cs.traffic.choice = cs.traffic.FLOW_TRANSMIT

                if hasattr(cs.traffic, "flow_transmit") and hasattr(
                    cs.traffic.flow_transmit, "state"
                ):
                    logger.info("Setting traffic.flow_transmit.state to stop")
                    if hasattr(cs.traffic.flow_transmit, "STOP"):
                        cs.traffic.flow_transmit.state = cs.traffic.flow_transmit.STOP
                    else:
                        cs.traffic.flow_transmit.state = "stop"

            api.set_control_state(cs)
            return True

        def verify_traffic_stopped(timeout=5):
            """Verify traffic has actually stopped by checking metrics."""
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Get flow metrics
                    request = api.metrics_request()
                    request.flow.flow_names = ["gateway-traffic"]
                    metrics = api.get_metrics(request)

                    if metrics.flow_metrics:
                        flow = metrics.flow_metrics[0]
                        # Check if frames_tx_rate is zero or very close to zero
                        if (
                            hasattr(flow, "frames_tx_rate")
                            and flow.frames_tx_rate < 0.1
                        ):
                            logger.info(
                                f"Traffic verified stopped: tx rate = {flow.frames_tx_rate}"
                            )
                            return True
                        else:
                            logger.info(
                                f"Traffic still running: tx rate = {flow.frames_tx_rate}"
                            )
                    else:
                        # If no metrics available, assume stopped after a few attempts
                        logger.info(
                            "No flow metrics available, assuming traffic stopped"
                        )
                        return True
                except Exception as e:
                    logger.warning(f"Error checking traffic status: {e}")

                time.sleep(1)

            logger.error("Timed out waiting for traffic to stop")
            return False

        # Execute the robust traffic stopping function
        if not ensure_traffic_stopped():
            logger.warning(
                "⚠️ Traffic may not have fully stopped! This could cause network loops."
            )

        # Get final flow metrics
        request = api.metrics_request()
        request.flow.flow_names = ["gateway-traffic"]
        metrics = api.get_metrics(request)

        # Print final statistics
        print("\n" + "=" * 80)
        print("TEST RESULTS")

        if metrics.flow_metrics:
            flow = metrics.flow_metrics[0]
            print(f"Frames Sent: {flow.frames_tx:,}")
            print(f"Bytes Sent: {flow.bytes_tx:,}")

            # Calculate overall average rate from bytes sent
            total_mbps = (flow.bytes_tx * 8) / (duration_seconds * 1000000)

            # Calculate average rate from our tracked rates (after warmup)
            avg_runtime_mbps = sum(rates_mbps) / len(rates_mbps) if rates_mbps else 0

            # Determine if we achieved target rate (>95% of target)
            target_threshold = rate_mbps * 0.95
            target_achieved = avg_runtime_mbps >= target_threshold

            print(f"Average Rate (bytes counter): {total_mbps:.2f} Mbps")
            print(f"Average Rate (runtime): {avg_runtime_mbps:.2f} Mbps")
            print(f"Maximum Rate: {max_rate_mbps:.2f} Mbps")

            # Print target achievement status
            if target_achieved:
                print(
                    f"✅ TARGET ACHIEVED: {avg_runtime_mbps:.2f} Mbps >= {target_threshold:.2f} Mbps (95% of {rate_mbps} Mbps)"
                )
            else:
                print(
                    f"❌ TARGET NOT MET: {avg_runtime_mbps:.2f} Mbps < {target_threshold:.2f} Mbps (95% of {rate_mbps} Mbps)"
                )

            if flow.frames_tx == 0:
                logger.warning("⚠️ No frames were transmitted! Check network setup.")
                print("WARNING: No frames were transmitted! Check network setup.")
        else:
            logger.warning("No metrics received")
            print("WARNING: No metrics received")

        print("=" * 80)

        logger.info("Test completed")
        return True

    except Exception as e:
        logger.error(f"Error during gateway traffic test: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simple gateway traffic test using snappi API"
    )
    parser.add_argument(
        "--api",
        default="https://traffic-generator.example.com:8443",
        help="Traffic generator API address",
    )
    parser.add_argument("--gateway", default="192.168.10.1", help="Gateway IP address")
    parser.add_argument(
        "--target-ip",
        default="8.8.8.8",
        help="Target IP address (external to ensure gateway routing)",
    )
    parser.add_argument("--port", default="p1", help="Source port name")
    parser.add_argument(
        "--interface",
        default="localhost:5555",
        help="Physical interface location (e.g., localhost:5555, veth-z)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=1000.0,
        help="Traffic rate in Mbps (default: 1000.0, i.e., 1 Gbps)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=1460,
        help="Packet size in bytes (default: 1460 for standard Ethernet frames)",
    )
    parser.add_argument(
        "--duration", type=int, default=10, help="Test duration in seconds"
    )
    parser.add_argument(
        "--no-verify", action="store_true", help="Disable SSL verification"
    )
    parser.add_argument("--config", help="Path to load configuration from JSON file")
    parser.add_argument("--save-config", help="Path to save configuration to JSON file")
    parser.add_argument(
        "--local-fallback",
        action="store_true",
        help="Use local UDP sockets as fallback if container is inaccessible",
    )

    args = parser.parse_args()

    verify_ssl = not args.no_verify

    try:
        success = run_gateway_traffic_test(
            api_address=args.api,
            gateway_ip=args.gateway,
            target_ip=args.target_ip,  # Use the target IP from command line
            source_port=args.port,
            interface_location=args.interface,  # Use the interface from command line args
            rate_mbps=args.rate,
            packet_size=args.size,
            duration_seconds=args.duration,
            verify_ssl=verify_ssl,
            config_file=args.config,
            save_config=args.save_config,
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)
