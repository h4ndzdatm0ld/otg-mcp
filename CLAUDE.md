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

Deploying a generator: `cd ansible && docker compose run --rm ansible deploy`
(Ansible roles, runs in a container; see `ansible/README.md`). Ansible is
deliberately absent from `pyproject.toml` — it is pinned in `ansible/requirements.txt`
and installed only into that container, so the production and test dependency sets
are unaffected.

The playbook declares interfaces explicitly rather than auto-detecting them.
The shell script this replaced guessed, and its guess could select the host's
management NIC; it also silently accepted dead links (on one host it chose
`eth1`/`eth2`/`eth3`, which do not exist there, leaving a traffic engine bound to
nothing while every check still passed).

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
- **`schema.py`** — `extract_component`, dotted-path navigation over a fetched OpenAPI document. No version resolution, no local files.
- **`config.py`** — JSON config file → `Config` holding `TargetsConfig` / `LoggingConfig`.

`models/models.py` holds every response model. All tool returns inherit `ApiResponse` (`success`/`error` fields) rather than raising to the MCP client.

### Targets

A target's config key *is* its address. `_get_location_for_target()` returns `https://{target}` verbatim, and version probing hits `https://{target}/capabilities/version`. Keys must therefore be resolvable `host:port` strings (`localhost:8443`, `fantasia-2x.heshlaw.local:8443`) — a symbolic label will not connect. TLS verification is deliberately off everywhere (`snappi.api(..., verify=False)`, `session.get(..., ssl=False)`) because lab gear uses self-signed certs.

### Two different "versions" — don't conflate them

1. `_discover_api_schema()` / `_get_api_version()` read the *local snappi library* version and feature-detect methods on the API object.
2. `get_target_version()` makes an HTTP call to the *remote generator's* `/capabilities/version`; that value is reported verbatim as `apiVersion` and is not matched against anything local.

### Schemas come from the target

There are no bundled schema files and no `schema_path` setting. `_fetch_remote_schema`
GETs `https://<target>/docs/openapi.json`; `_get_schema_for_target` caches the result
in `target_schemas` keyed by target for the process lifetime, so generators on
different software versions stay independent. A target that serves no usable document
raises `ValueError` naming the endpoint — nothing is substituted, because there is
nothing local to substitute. `schema.py` holds `extract_component`, the only schema
logic left: dotted-path navigation over an already-fetched document.

Note the served spec's `info.version` does not necessarily match the target's
`app_version` from `/capabilities/version` (fantasia-2x reports spec 1.20.0 while
running 1.28.0-33), so don't treat them as interchangeable.

### Traffic engine packet paths

The traffic engine runs one of two packet paths, and the difference is large:
`af_packet` is a kernel socket path that is CPU-bound at roughly 3 Gbps, while
DPDK polls in userspace and reaches line rate (measured 2.86 vs 9.85 Gbps on the
same Intel X540 port). DPDK requires the NIC bound to `vfio-pci`, hugepages, and
a `memlock` ulimit the Docker default (8 MB) does not provide.

Two consequences worth knowing when reading `client.py` behaviour against a real
target: a DPDK-bound NIC has no kernel interface at all, and a DPDK port reports
no line speed, so any config using a percentage rate must also set `layer1`
speed or the controller rejects it with "Port line speed not found".

### snappi version compatibility

Traffic control is written as feature-detection fallback chains rather than version checks, because snappi renamed these APIs across releases: start tries `start_transmit` → `set_flow_transmit` → `control_state`; stop tries `stop_transmit` → `set_flow_transmit` → `control_state` → flow-transmit, then `_verify_traffic_stopped()` polls metrics to confirm frame rates dropped below threshold. Preserve the chain shape when touching these — a target may only implement one branch.

`client.py` uses `aiohttp` for the raw `/capabilities/version` probe and `snappi` for everything else; both are declared dependencies.

## Testing conventions

`tests/conftest.py` inserts `src/` on `sys.path` and provides `api_schema` (parsed `tests/fixtures/apiSchema.yml`), `test_config`, `router` (an `OtgClient`), and `example_target_config`. Tests never touch real hardware; stub `_fetch_remote_schema` rather than reaching for a network, and mock the snappi API object. `tests/schema/` covers per-target fetch, caching, isolation and malformed-document handling. See `tests/README.md`.

## Release

Releases are automatic and version numbers are not chosen by hand:
release-please derives them from Conventional Commits, opens a release PR that
bumps `pyproject.toml` and writes `CHANGELOG.md`, and merging that PR triggers
the tag, GitHub Release, PyPI publish and semver Docker images
(`.github/workflows/release.yml`). `fix:` is a patch, `feat:` a minor, and a
non-conventional commit produces no release at all. Versions are plain semver;
the pre-1.0 PEP 440 style (`0.1.3a0`, tagged `v0.1.3a`) is history. State lives in
`.release-please-manifest.json`. Conventions in `RELEASE.md`.
