# OTG MCP Server

MCP (Model Context Protocol) server implementation for Open Traffic Generator (OTG) API.

## Overview

The OTG MCP Server is a Python-based Model Context Protocol (MCP) to provide access to Open Traffic Generators (OTG) through a unified API. The server connects to traffic generators using a standardized configuration interface, providing a consistent way to interact with these devices regardless of vendor or location.

## Features

- **Configuration-Based Connection**: Connect to traffic generators via standardized configuration
- **OTG API Implementation**: Complete implementation of the Open Traffic Generator API
- **Multi-Target Support**: Connect to multiple traffic generators simultaneously
- **Type-Safe Client**: Generate Python clients from OpenAPI specifications
- **Resilient Connections**: Automatic reconnect and retry logic for reliability

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- [Ixia-C Deployment Guide](./docs/deployIxiaC_simple_testing.md): Simple testing with Ixia-C Community Edition

## Examples

The project includes examples showing how to:

- Connect to traffic generators
- Configure traffic flows
- Start and stop traffic
- Collect and analyze metrics

See the [Traffic Generator Test Examples](./src/examples/traffic_generator_tests/README.md) for examples demonstrating connectivity and traffic generation with various traffic generators.

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

### Running the Server

```bash
# Start the server
python -m otg_mcp.server
```

### Running Examples

```bash
# Run the traffic generator example
python src/examples/traffic_generator_tests/traffic_generator_test.py
```

## Development

### Project Structure

```
.
├── docs/                    # Documentation
│   └── traffic_generator_guide.md     # Traffic generator-specific documentation
├── src/                     # Source code
│   ├── otg_mcp/             # Main package
│   │   ├── models/          # Data models
│   │   ├── schemas/         # API schemas
│   │   └── client.py        # Traffic generator client
│   └── examples/            # Example scripts
│       └── traffic_generator_tests/   # Traffic generator examples
├── tests/                   # Test suite
├── memory-bank/             # Project documentation and context
└── requirements/            # Dependency specifications
```

### Key Components

1. **MCP Server**: Implements the Model Context Protocol interface
2. **Configuration Manager**: Handles traffic generator configuration and connections
3. **OTG Client**: Client for interacting with traffic generators
4. **Schema Registry**: Manages API schemas for different traffic generator versions

### Code Quality

The project maintains high code quality standards:

- **Type Safety**: Full mypy type hinting
- **Testing**: Comprehensive pytest coverage
- **Documentation**: Google docstring format for all code
- **Logging**: Preferred over comments throughout codebase
- **Data Models**: Pydantic models for validation and serialization

## Common Issues and Solutions

### Traffic Generator Connectivity

For issues connecting to traffic generators, see the [Traffic Generator Guide](./docs/traffic_generator_guide.md) which documents common issues and their solutions:

- Connection protocol issues (HTTP vs HTTPS)
- Port configuration format requirements
- Handling deprecated API methods
- Defensive programming techniques

## Contributing

1. Ensure all code includes proper type hints
2. Follow Google docstring format
3. Add comprehensive tests for new features
4. Use logging rather than comments for important operations
5. Update documentation for any API or behavior changes

## Future Development

### Dynamic Client Generation

In future versions, the project will move towards a dynamic client generation approach instead of relying directly on the snappi dependency. This will provide greater flexibility and reduce external dependencies.

The planned implementation will use code similar to this:

```python
# Define the OpenAPI specification URL
openapi_url = "https://raw.githubusercontent.com/open-traffic-generator/models/v0.12.5/artifacts/openapi.yaml"

# Set the output directory for the generated client
output_dir = Path("generated_client")

# Create a configuration for the generator
config = Config()

# Initialize the generator with the configuration
generator = Generator(config=config)

# Generate the client from the OpenAPI URL
result = generator.create_new_client_from_url(
    url=openapi_url,
    path=output_dir,
    config=config
)
```

This approach will allow the client to be dynamically generated from the latest OpenAPI specifications, ensuring compatibility with new versions of the traffic generator API without requiring manual updates to the client code. The generated client will replace the current direct dependency on snappi, making the system more flexible and maintainable.

## License

This project is licensed under the terms of the license included in the repository.
