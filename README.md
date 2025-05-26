# Open Traffic Generator MCP Server

[![codecov](https://codecov.io/gh/h4ndzdatm0ld/otg-mcp/graph/badge.svg?token=FCrRSKjGZz)](https://codecov.io/gh/h4ndzdatm0ld/otg-mcp) [![CI](https://github.com/h4ndzdatm0ld/otg-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/h4ndzdatm0ld/otg-mcp/actions/workflows/ci.yml)

MCP (Model Context Protocol) server implementation for Open Traffic Generator (OTG) API.

## Overview

The OTG MCP Server is a Python-based Model Context Protocol (MCP) to provide access to Open Traffic Generators (OTG) through a unified API. The server connects to traffic generators using a standardized configuration interface, providing a consistent way to interact with any traffic generator that respects OpenTrafficGenerator Models.

## Features

- **Configuration-Based Connection**: Connect to traffic generators via standardized configuration
- **OTG API Implementation**: Complete implementation of the Open Traffic Generator API
- **Multi-Target Support**: Connect to multiple traffic generators simultaneously
- **Type-Safe Models**: Pydantic models for configuration, metrics, and response data

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- [Ixia-C Deployment Guide](./docs/deployIxiaC_simple_testing.md): Simple testing with Ixia-C Community Edition
- [GitHub Flow](./docs/github-flow.md): Guidelines for GitHub workflow

## Configuration

The OTG MCP Server uses a JSON configuration file to define traffic generator targets and their ports.

Example configuration (`examples/trafficGeneratorConfig.json`):

```json
{
  "schemas": {
    "schema_path": "/path/to/custom/schemas/directory"
  },
  "targets": {
    "traffic-gen-1.example.com:8443": {
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

- `schemas`: Settings for schema management
  - `schema_path`: Optional path to directory containing custom schema files
- `targets`: Map of traffic generator targets
- `ports`: Configuration for each port on the target, with location and name

### Custom Schema Support

The OTG MCP Server supports loading schema files from user-defined directories, which is useful when:

- You have custom schemas for specific traffic generator versions
- You need to test with unreleased API versions
- You have special extensions to the standard OTG schemas

To use custom schemas:

1. Add a `schemas` section to your configuration file with the `schema_path` field pointing to your schema directory
2. Organize your custom schema files in the same version-based structure as the built-in schemas
3. Custom schemas will take priority over built-in schemas when both exist

Example directory structure for custom schemas:
```
/path/to/custom/schemas/
├── 1_28_0/
│   └── openapi.yaml
├── 1_29_0/
│   └── openapi.yaml
└── 1_31_0/  # Custom schema version not available in built-in schemas
    └── openapi.yaml
```

### API Version Handling

The OTG MCP Server automatically detects API versions from traffic generator targets:

1. When connecting to a target, the server queries its API version
2. If an exact matching schema version is available (versions 1.28.0 and newer are supported), it uses that schema
3. If no exact match exists, it follows this priority order to find the closest match:
   - Schema with same major.minor version and equal or lower patch version
   - Schema with same major version and highest available minor version
   - Latest available schema version as fallback
4. This process checks both custom schemas (if configured) and built-in schemas, with custom schemas taking priority

This intelligent version matching ensures optimal compatibility while allowing for custom schema extensions when needed.

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
    "command": "python",
    "args": [
      "/path/to/otg-mcp/src/otg_mcp/server.py",
      "--config-file",
      "/path/to/otg-mcp/examples/trafficGeneratorConfigWithCustomSchemas.json"
    ],
  }
}
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
│       ├── schemas/         # Built-in API schemas
│       │   ├── 1_28_0/      # Schema version 1.28.0
│       │   ├── 1_29_0/      # Schema version 1.29.0
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

## Release Process

For information about version management and releasing new versions of this package, see [RELEASE.md](./RELEASE.md).

Key points:
- Version management is handled through `pyproject.toml` only
- Follows semantic versioning with pre-release tags (`a0`, `b0`, `rc0`)
- Automated CI/CD pipeline handles testing and PyPI publishing

## License

This project is licensed under the terms of the license included in the repository.
