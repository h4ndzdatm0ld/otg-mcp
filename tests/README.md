# Testing Guide for OTG MCP

## Running Tests

No environment variables or special setup are required — the suite runs entirely
against mocks and never talks to real traffic generator hardware.

```bash
# Install dev and test dependencies
uv venv && uv pip install -e ".[dev,test]"

# Run everything
uv run pytest

# Run a single file
uv run pytest tests/test_server.py

# Run a single test
uv run pytest tests/test_server.py::test_tool_registration

# Skip coverage while iterating (coverage is on by default via pyproject addopts)
uv run pytest --no-cov tests/test_config.py
```

Coverage reports are written to `coverage/` (HTML and XML) on every run because
`--cov` is baked into `[tool.pytest.ini_options] addopts`.

## Layout

| Path                | Covers                                                          |
| ------------------- | --------------------------------------------------------------- |
| `tests/schema/`     | `schema_registry.py` — version normalization, closest-version matching, component lookup |
| `tests/version/`    | Detecting a target's API version and mapping it to a schema      |
| `tests/functional/` | Repo-wide rules, currently the no-inline-comments check          |
| `tests/test_*.py`   | Config loading, server tool registration, health, client methods |
| `tests/fixtures/`   | `apiSchema.yml`, a trimmed OpenAPI document for schema tests     |

## Shared Fixtures

Defined in `tests/conftest.py`, which also puts `src/` on `sys.path`:

- `api_schema` — the parsed `tests/fixtures/apiSchema.yml` document
- `test_config` — a default `Config()` instance
- `router` — an `OtgClient` built from `test_config`
- `example_target_config` — adds `test-target.example.com:8443` with two ports to `test_config`

Most schema tests define their own local `mock_schema_registry` / `mock_api`
fixtures with `MagicMock` rather than using shared ones — follow the pattern in
the file you are editing.

## Integration Tests

`conftest.py` registers an `integration` marker and skips those tests unless
`RUN_INTEGRATION_TESTS=1` is set:

```bash
RUN_INTEGRATION_TESTS=1 uv run pytest -m integration
```

No integration tests exist yet. New ones need `@pytest.mark.integration` plus a
reachable generator — see `deploy/deployIxiaC.sh` for a local Ixia-C.

## Conventions

1. Production code in `src/` must not contain inline comments. Use logging
   statements and docstrings instead; `tests/functional/test_no_inline_comments.py`
   enforces this. Test files are exempt.
2. Mock the snappi API object rather than adding test-only branches to
   production code.
3. Type hints and Google-style docstrings on new code.
