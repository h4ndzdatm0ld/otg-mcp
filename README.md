# OTG MCP Server

[![codecov](https://codecov.io/gh/h4ndzdatm0ld/otg-mcp/graph/badge.svg?token=FCrRSKjGZz)](https://codecov.io/gh/h4ndzdatm0ld/otg-mcp) [![CI](https://github.com/h4ndzdatm0ld/otg-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/h4ndzdatm0ld/otg-mcp/actions/workflows/ci.yml)

MCP (Model Context Protocol) server implementation for Open Traffic Generator (OTG) API.

## Overview

The OTG MCP Server is a Python-based Model Context Protocol (MCP) to provide access to Open Traffic Generators (OTG) through a unified API. The server connects to traffic generators using a standardized configuration interface, providing a consistent way to interact with these devices regardless of vendor or location.

## Features

- **Configuration-Based Connection**: Connect to traffic generators via standardized configuration
- **OTG API Implementation**: Complete implementation of the Open Traffic Generator API
- **Multi-Target Support**: Connect to multiple traffic generators simultaneously
- **Type-Safe Models**: Pydantic models for configuration, metrics, and response data
- **Resilient Connections**: Automatic reconnect and retry logic for reliability

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- [Ixia-C Deployment Guide](./docs/deployIxiaC_simple_testing.md): Simple testing with Ixia-C Community Edition
- [GitHub Flow](./docs/github-flow.md): Guidelines for GitHub workflow

## Configuration

The OTG MCP Server uses a JSON configuration file to define traffic generator targets and their ports.

Example configuration (`examples/trafficGeneratorConfig.json`):

```json
{
  "targets": {
    "traffic-gen-1.example.com:8443": {
      "apiVersion": "1.30.0",
      "ports": {
        "p1": {
          "location": "localhost:5555",
          "name": "p1"
        },
        "p2": {
          "location": "localhost:5556",
          "name": "p2"
        }
      }
    },
    "traffic-gen-2.example.com:8443": {
      "apiVersion": "1.30.0",
      "ports": {
        "p1": {
          "location": "localhost:5555",
          "name": "p1"
        }
      }
    }
  }
}
```

Key elements in the configuration:
- `targets`: Map of traffic generator targets
- `apiVersion`: API schema version to use for each target
- `ports`: Configuration for each port on the target, with location and name

## Testing with deployIxiaC

The project includes a utility script `deploy/deployIxiaC.sh` that helps set up and deploy Ixia-C for testing purposes. This script:

- Pulls necessary Docker images for Ixia-C
- Sets up the environment with the correct networking
- Configures the test environment for OTG API usage

To use this utility:

```bash
# Navigate to the deploy directory
cd deploy

# Run the deployment script (requires Docker)
./deployIxiaC.sh
```

Refer to the [Ixia-C Deployment Guide](./docs/deployIxiaC_simple_testing.md) for more detailed information about using Ixia-C with this project.

## Examples

The project includes examples showing how to:

- Connect to traffic generators
- Configure traffic flows
- Start and stop traffic
- Collect and analyze metrics

See the examples in the `examples/` directory:

- `trafficGeneratorConfig.json`: Example configuration for traffic generators
- `simple_gateway_test.py`: Example script for basic testing of API executions

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Access to traffic generator hardware or virtual devices
- Configuration file for target traffic generators

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd <repository-directory>

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Docker Container

The OTG MCP Server can also be run as a Docker container, available from the GitHub Container Registry:

```bash
# Pull the container image
docker pull ghcr.io/h4ndzdatm0ld/otg-mcp:latest

# Run the container with your configuration
docker run -v $(pwd)/examples:/app/examples -p 8443:8443 ghcr.io/h4ndzdatm0ld/otg-mcp:latest --config-file examples/trafficGeneratorConfig.json
```

This approach eliminates the need for local Python environment setup and ensures consistent execution across different platforms.

### MCP Server Configuration Example

When integrating with an MCP client application, you can use the following configuration example to specify the OTG MCP Server as a tool provider:

> NOTE: Or use `uvx`

```json
{
  "OpenTrafficGenerator - MCP": {
    "autoApprove": [
      "get_available_targets",
      "get_config",
      "get_metrics",
      "get_schemas_for_target",
      "health",
      "list_schemas_for_target",
      "set_config",
      "start_capture",
      "start_traffic",
      "stop_capture",
      "stop_traffic"
    ],
    "disabled": false,
    "timeout": 60,
    "command": "python",
    "args": [
      "/path/to/otg-mcp/src/otg_mcp/server.py",
      "--config-file",
      "/path/to/otg-mcp/examples/trafficGeneratorConfig.json"
    ],
    "transportType": "stdio"
  }
}
```

Key elements in this configuration:
- `autoApprove`: Tools that can be executed without explicit approval
- `timeout`: Maximum time in seconds allowed for operations
- `command` and `args`: How to launch the OTG MCP Server
- `transportType`: Communication method (stdio or SSE)

### Running the Server

```bash
# Start the server with a configuration file
python -m otg_mcp.server --config-file examples/trafficGeneratorConfig.json
```

### Running Examples

```bash
# Run the simple gateway test example
python examples/simple_gateway_test.py
```

## Development

### Project Structure

```
.
├── docs/                    # Documentation
│   ├── deployIxiaC_simple_testing.md # Ixia-C testing guide
│   └── github-flow.md       # GitHub workflow documentation
├── deploy/                  # Deployment scripts
│   └── deployIxiaC.sh       # Script for deploying Ixia-C testing environment
├── src/                     # Source code
│   └── otg_mcp/             # Main package
│       ├── models/          # Data models
│       │   ├── __init__.py  # Model exports
│       │   └── models.py    # Model definitions
│       ├── schemas/         # API schemas
│       │   └── 1_30_0/      # Schema version 1.30.0
│       ├── __init__.py      # Package initialization
│       ├── __main__.py      # Entry point
│       ├── client.py        # Traffic generator client
│       ├── config.py        # Configuration management
│       ├── schema_registry.py # Schema management
│       └── server.py        # MCP server implementation
├── examples/                # Example scripts and configurations
│   ├── trafficGeneratorConfig.json # Example configuration
│   └── simple_gateway_test.py      # Example test script
├── tests/                   # Test suite
│   ├── fixtures/            # Test fixtures
│   └── ...                  # Various test files
├── .gitignore               # Git ignore file
├── Dockerfile               # Docker build file
├── LICENSE                  # License file
├── README.md                # This file
├── pyproject.toml           # Project metadata
├── requirements.txt         # Dependencies
└── setup.py                 # Package setup
```

### Key Components

1. **MCP Server**: Implements the Model Context Protocol interface
2. **Configuration Manager**: Handles traffic generator configuration and connections
3. **OTG Client**: Client for interacting with traffic generators
4. **Schema Registry**: Manages API schemas for different traffic generator versions
5. **Models**: Pydantic models for representing data structures

### Code Quality

The project maintains high code quality standards:

- **Type Safety**: Full mypy type hinting
- **Testing**: Comprehensive pytest coverage
- **Documentation**: Google docstring format for all code
- **Logging**: Used throughout the codebase instead of comments
- **Data Models**: Pydantic models for validation and serialization

## Contributing

1. Ensure all code includes proper type hints
2. Follow Google docstring format
3. Add comprehensive tests for new features
4. Use logging rather than comments for important operations
5. Update documentation for any API or behavior changes

## License

This project is licensed under the terms of the license included in the repository.
