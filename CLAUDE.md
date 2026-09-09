# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MCP server exposing Open Traffic Generator (OTG) operations — configure flows, start/stop traffic, capture packets, read metrics — against one or more traffic generators (Ixia-C, IxNetwork, anything snappi can talk to). Python 3.11–3.12, `src/` layout, package `otg_mcp`.

## Commands

CI uses `uv`; use it locally too.

```bash
uv venv && uv pip install -e ".[dev,test]"

uv run pytest                                  # full suite (pytest addopts always adds coverage)
uv run pytest tests/test_server.py             # one file
uv run pytest tests/test_server.py::test_name  # one test
uv run pytest -p no:cacheprovider --no-cov ... # skip coverage when iterating

uv run ruff check .
uv run mypy src/        # CI type-checks src/ only, not tests/
uv build
```

Caveat on `ruff`: the dependency is unpinned (`ruff>=0.11.7`) and no `select` is
configured, so a modern ruff (0.16.x) reports ~235 pre-existing violations across
`src/` and `tests/` that older versions did not flag. Judge your own changes with
`uv run ruff check --select E4,E7,E9,F <files>` and do not mass-fix the backlog as
a side effect of an unrelated change.

Run the server:

```bash
python -m otg_mcp --config-file examples/trafficGeneratorConfig.json [--transport stdio|sse]
```

Local Ixia-C for manual testing: `cd deploy && ./deployIxiaC.sh` (Docker required; see `docs/deployIxiaC_simple_testing.md`).

No integration tests exist. `tests/conftest.py` registers an `integration` marker
and skips such tests unless `RUN_INTEGRATION_TESTS=1`, but nothing is marked and CI
never sets it — the whole suite is mocked.

Known issue, unfixed: the `docker run ... <image> --config-file ...` command in
`README.md` cannot work, because the Dockerfile uses `CMD` and appended `docker run`
args replace it wholesale rather than being passed to `python -m otg_mcp`. Fixing it
means switching to `ENTRYPOINT`.

## Enforced style: no inline comments in `src/`

`tests/functional/test_no_inline_comments.py` fails the suite if any `.py` file under `src/` contains a line with `#`, except: the first 5 lines of a file, and lines containing `# noqa`, `# type:`, `# pragma:`, `#!/usr/bin/env`.

**Explain code with `logger.info(...)` calls and docstrings, never comments.** The existing dense per-step logging in `client.py` and `config.py` is a consequence of this rule, not accidental verbosity — match it. Google-style docstrings throughout.

## Architecture

Four modules, layered:

- **`server.py`** — `OtgMcpServer` wraps `FastMCP`. `_register_tools()` reflects over `dir(self)` and registers every method named `tool_<name>` as MCP tool `<name>`. **To add a tool, just add an `async def tool_foo(...)` method** — there is no registry to update. Tool bodies are one-liners delegating to `OtgClient`; keep the business logic in the client. Parameters use `Annotated[T, Field(description=...)]` since those descriptions become the MCP tool schema. Client-side autoApprove lists (e.g. the one in `README.md`) need updating by hand when tool names change.
- **`client.py`** — `OtgClient` (a `@dataclass`) is the whole OTG surface: one `snappi` API client per target, cached in `self.api_clients`. Sync `_private` helpers do the snappi work; `async` public methods are what tools call and return the Pydantic response models.
- **`schema_registry.py`** — resolves an API version string to an OpenAPI document and answers schema queries against it.
- **`config.py`** — JSON config file → `Config` holding `TargetsConfig` / `SchemaConfig` / `LoggingConfig`.

`models/models.py` holds every response model. All tool returns inherit `ApiResponse` (`success`/`error` fields) rather than raising to the MCP client.

### Targets

A target's config key *is* its address. `_get_location_for_target()` returns `https://{target}` verbatim, and version probing hits `https://{target}/capabilities/version`. Keys must therefore be resolvable `host:port` strings (`localhost:8443`, `fantasia-2x.heshlaw.local:8443`) — a symbolic label will not connect. TLS verification is deliberately off everywhere (`snappi.api(..., verify=False)`, `session.get(..., ssl=False)`) because lab gear uses self-signed certs.

### Two different "versions" — don't conflate them

1. `_discover_api_schema()` / `_get_api_version()` read the *local snappi library* version and feature-detect methods on the API object.
2. `get_target_version()` makes an HTTP call to the *remote generator's* `/capabilities/version`; that value is what `find_closest_schema_version()` maps onto a bundled schema.

### Schema resolution

Built-in schemas live at `src/otg_mcp/schemas/<major>_<minor>_<patch>/openapi.yaml` (currently 1.28.0, 1.29.0, 1.30.0) — add a version by dropping in a new directory in that exact naming form. `_normalize_version()` converts `1.30.0` ↔ `1_30_0`. A custom directory with the same layout can be supplied via config and takes priority over built-ins. When there is no exact match, `find_closest_schema_version()` degrades: same major.minor with patch ≤ requested → same major with highest minor → latest available.

A custom directory is configured as `{"schemas": {"schema_path": "/path"}}`. `Config._load_schema_path()` also accepts a legacy top-level `"schema_path"` key with a deprecation warning, and the nested form wins when both are present. A path that does not exist is warned about and ignored rather than raising.

### snappi version compatibility

Traffic control is written as feature-detection fallback chains rather than version checks, because snappi renamed these APIs across releases: start tries `start_transmit` → `set_flow_transmit` → `control_state`; stop tries `stop_transmit` → `set_flow_transmit` → `control_state` → flow-transmit, then `_verify_traffic_stopped()` polls metrics to confirm frame rates dropped below threshold. Preserve the chain shape when touching these — a target may only implement one branch.

`client.py` uses `aiohttp` for the raw `/capabilities/version` probe and `snappi` for everything else; both are declared dependencies.

## Testing conventions

`tests/conftest.py` inserts `src/` on `sys.path` and provides `api_schema` (parsed `tests/fixtures/apiSchema.yml`), `test_config`, `router` (an `OtgClient`), and `example_target_config`. Most schema tests define their own local `MagicMock`-based registry fixtures instead — follow whichever pattern the file you are editing already uses. Tests never touch real hardware; mock the snappi API object. The bulk of the suite (`tests/schema/`) targets `schema_registry.py` version-matching edge cases. See `tests/README.md`.

## Release

Version lives only in `pyproject.toml`. Tag `v<version>` and publish a GitHub Release; CI builds and pushes to PyPI. Details and semver/pre-release conventions in `RELEASE.md`.
