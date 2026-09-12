#!/usr/bin/env python3
"""Write a new version into pyproject.toml, which is the single source of truth.

Used by .github/workflows/release.yml after computing an automated patch bump.
Rewrites only the first `version = "..."` line in the [project] table, so
dependency pins and tool configuration are untouched.
"""

from __future__ import annotations

import re
import sys

PATH = "pyproject.toml"


def set_version(version: str) -> None:
    """Replace the project version in pyproject.toml.

    Args:
        version: The version string to write, without a leading ``v``.

    Raises:
        SystemExit: If no version line was found, rather than writing a file
            that silently kept the old version.
    """
    text = open(PATH).read()
    updated, count = re.subn(
        r'^version = ".*"$', f'version = "{version}"', text, count=1, flags=re.M
    )
    if count != 1:
        raise SystemExit(f"no 'version = \"...\"' line found in {PATH}")
    open(PATH, "w").write(updated)


if __name__ == "__main__":
    set_version(sys.argv[1])
