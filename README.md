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

- [Next-Gen Network Testing with Open Traffic Generator MCP Server](https://medium.com/@hugotinoco/next-gen-network-testing-with-open-traffic-generator-mcp-server-061e0685d7d9):
  an introduction to what this server is for and how it fits into a testing workflow
- [Deploying a traffic generator](./ansible/README.md): Ansible roles that build an OTG generator, including DPDK
- [GitHub Flow](./docs/github-flow.md): Guidelines for GitHub workflow

## Configuration

The OTG MCP Server uses a JSON configuration file to define traffic generator targets and their ports.

Example configuration (`examples/trafficGeneratorConfig.json`):

```json
{
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

- `targets`: Map of traffic generator targets
- `ports`: Configuration for each port on the target, with location and name

### Schemas

Schemas are not shipped with this server and there is nothing to configure. Each
target publishes the OpenAPI document it actually implements at
`/docs/openapi.json`, and the server fetches that document from the target the
first time a schema is needed, then reuses it for the life of the process.

Because the cache is keyed by target, several generators running different
software versions each keep their own schema, and `get_schemas_for_target`
always describes the contract the target really implements rather than a version
guessed locally.

A target that does not publish its document cannot answer the schema tools; those
calls fail with a message naming the endpoint that was tried. The traffic,
capture, metrics and health tools are unaffected.

## Deploying a traffic generator

`ansible/` turns a bare Linux host into an OTG traffic generator this server can
drive. It installs Docker and the network tooling, deploys the Ixia-C containers,
optionally binds NICs to DPDK for 10G line rate, and verifies the result by
transmitting a real flow.

Ansible runs in a container, so Docker is the only local requirement, and Ansible
is deliberately **not** a dependency of the `otg_mcp` package.

```bash
cd ansible
cp inventory/hosts.yml.example inventory/hosts.yml   # edit: host, interface, driver
docker compose run --rm ansible deploy
```

Other verbs: `verify` (read-only health check), `check` (dry run), `dpdk` and
`revert-dpdk` (bind or release NICs), `ping`. See [ansible/README.md](./ansible/README.md)
for the inventory format, the af_packet vs DPDK tradeoff, and the host-level
traps it detects.

The inventory hostname should be the address you will use as the target key in
this server's config, since a target's key *is* its address.


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

# Install dependencies (dev tooling plus pytest)
pip install -e ".[dev,test]"
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
      "get_capture",
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
      "-m",
      "otg_mcp",
      "--config-file",
      "/path/to/otg-mcp/examples/trafficGeneratorConfig.json"
    ]
  }
}
```

The `autoApprove` list must match the tool names registered by the server. Tool
names are derived from `OtgMcpServer` methods by stripping the `tool_` prefix, so
adding or renaming a `tool_*` method means updating this list.


## Development

### Project Structure

```
.
├── ansible/                 # Deployment: builds an OTG generator on a remote host
│   ├── site.yml             # Full deploy
│   ├── dpdk.yml             # Bind NICs to DPDK
│   ├── dpdk-revert.yml      # Return NICs to the kernel driver
│   ├── docker-compose.yml   # Control node: docker compose run --rm ansible deploy
│   └── roles/               # preflight, sudo_compat, docker, net_utils, otgen, dpdk, ixia_c, verify
├── docs/                    # Documentation
│   └── github-flow.md       # GitHub workflow documentation
├── src/                     # Source code
│   └── otg_mcp/             # Main package
│       ├── models/          # Data models
│       │   ├── __init__.py  # Model exports
│       │   └── models.py    # Model definitions
│       ├── __init__.py      # Package initialization
│       ├── __main__.py      # Entry point
│       ├── client.py        # Traffic generator client
│       ├── config.py        # Configuration management
│       ├── schema.py        # OpenAPI document navigation
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
├── pyproject.toml           # Project metadata, dependencies, and version
└── requirements.txt         # Lock file for the default hatch environment
```

### Key Components

1. **MCP Server**: Implements the Model Context Protocol interface
2. **Configuration Manager**: Handles traffic generator configuration and connections
3. **OTG Client**: Client for interacting with traffic generators
4. **Schema Fetching**: Retrieves each target's own OpenAPI document on demand
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
