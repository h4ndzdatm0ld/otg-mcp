#!/usr/bin/env python3
"""Compute the next patch version, staying on the current release track.

Used by .github/workflows/release.yml when a merge to main did not bump the
version itself. It deliberately preserves a pre-release suffix: promoting an
alpha to a stable release declares the project stable and moves the `latest`
Docker tag, which is a decision for a human bumping pyproject.toml in a PR, not
a side effect of merging.

    0.1.4a0  -> 0.1.5a0
    0.9.0b2  -> 0.9.1b0
    2.0.0rc1 -> 2.0.1rc0
    1.2.3    -> 1.2.4

Run with no arguments to self-test.
"""

from __future__ import annotations

import re
import sys

PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$")


def next_version(current: str) -> str:
    """Return the next patch version for ``current``, keeping its track.

    Args:
        current: A version string such as ``0.1.4a0`` or ``1.2.3``.

    Returns:
        The next patch version, with any pre-release suffix reset to 0.

    Raises:
        ValueError: If ``current`` is not a recognised version string.
    """
    match = PATTERN.match(current.strip())
    if not match:
        raise ValueError(
            f"unrecognised version {current!r}; expected MAJOR.MINOR.PATCH "
            "optionally followed by a0, b0 or rc0"
        )
    major, minor, patch = (int(part) for part in match.group(1, 2, 3))
    pre = match.group(4)
    bumped = f"{major}.{minor}.{patch + 1}"
    return f"{bumped}{pre}0" if pre else bumped


def _self_test() -> int:
    cases = {
        "0.1.4a0": "0.1.5a0",
        "0.1.3a0": "0.1.4a0",
        "1.2.3": "1.2.4",
        "0.9.0b2": "0.9.1b0",
        "2.0.0rc1": "2.0.1rc0",
        "0.1.9a0": "0.1.10a0",
    }
    failures = 0
    for given, expected in cases.items():
        got = next_version(given)
        status = "ok " if got == expected else "FAIL"
        if got != expected:
            failures += 1
        print(f"{status} {given} -> {got} (expected {expected})")

    for bad in ("", "1.2", "v1.2.3", "1.2.3.dev0", "1.2.3alpha"):
        try:
            next_version(bad)
        except ValueError:
            print(f"ok  rejected {bad!r}")
        else:
            print(f"FAIL accepted {bad!r}")
            failures += 1

    print("all passed" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(_self_test())
    print(next_version(sys.argv[1]))
