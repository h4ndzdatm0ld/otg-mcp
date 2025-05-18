# Testing Guide for OTG MCP

This guide explains how to run tests for the OTG MCP project.

## Running Tests

To run the tests, you need to set certain environment variables that control the behavior of the code under test, rather than having the production code check for test framework-specific variables.

### Setting Test Mode

```bash
# Set test mode (required for all tests)
export USE_TEST_MODE=true

# Run tests
python -m pytest tests/
```

### Specific Test Cases

For specific test scenarios, you can set the `TEST_CASE` environment variable:

```bash
# For client tests
export TEST_CASE=client_test
python -m pytest tests/test_client.py

# For integration tests
export RUN_INTEGRATION_TESTS=1
python -m pytest tests/integration/test_router_set_get_config.py
python -m pytest tests/integration/test_integration_targets.py
```

### Test Case Values

- `config_get_test`: Returns a fixed config response for GET requests
- `config_post_test`: Uses the `config()` call explicitly for POST requests
- `control_stop_test`: Returns a simplified response for stop traffic requests

### Running All Tests

You can run all tests with this helper script:

```bash
#!/bin/bash
# Run all tests with proper environment variables set
export USE_TEST_MODE=true
export TEST_CASE=default  # Default test case

# Run all tests
python -m pytest tests/
```

## Best Practices

1. Keep production code clean of test framework references
2. Use environment variables for test-specific behavior
3. Mock dependencies in tests rather than adding test logic to production code
