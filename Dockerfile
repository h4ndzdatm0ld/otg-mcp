# Single source of dependency truth: pyproject.toml plus uv.lock.
#
# This image used to install from a generated requirements.txt while developers
# and CI used uv.lock, so the two drifted badly - the image shipped fastmcp
# 2.14.7 while uv.lock pinned 2.2.5 - and dependabot kept opening PRs against
# the generated file that were stale before anyone read them.
FROM python:3.12-slim

# uv resolves and installs from the lockfile; copied from its own published image
# so there is no bootstrap pip install to keep current.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # Use the interpreter already in the image rather than downloading one.
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, without the project itself, so editing source does not
# invalidate the dependency layer. --frozen fails if uv.lock disagrees with
# pyproject.toml, which is exactly the drift this image used to hide.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .

# The project itself, still from the lockfile.
RUN uv sync --frozen --no-dev

EXPOSE 3000

CMD ["python", "-m", "otg_mcp"]
