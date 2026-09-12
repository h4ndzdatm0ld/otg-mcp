"""
Tests for the ``python -m otg_mcp`` entry point.

``__main__.py`` is what every documented invocation of this server goes through,
and its whole job is exit-code discipline: a clean shutdown must exit 0, and a
failure to start must exit non-zero so a supervisor or CI job notices. The module
body only runs under ``__name__ == "__main__"``, so it is executed here with
``runpy`` and with ``run_server`` stubbed — nothing binds a port or talks to a
traffic generator.
"""

import runpy
import sys
from unittest import mock

import pytest


def run_entry_point():
    """Execute ``otg_mcp.__main__`` as if started with ``python -m otg_mcp``.

    Returns:
        The module globals left behind by the run.
    """
    sys.modules.pop("otg_mcp.__main__", None)
    return runpy.run_module("otg_mcp", run_name="__main__")


def test_clean_shutdown_exits_zero():
    """A normal ``run_server()`` return exits with status 0.

    Exiting non-zero on a clean shutdown would make every graceful stop look like
    a crash to whatever supervises the process.
    """
    with mock.patch("otg_mcp.server.run_server") as run_server:
        with pytest.raises(SystemExit) as exit_info:
            run_entry_point()

    assert exit_info.value.code == 0
    run_server.assert_called_once_with()


def test_import_error_during_startup_exits_one():
    """A missing dependency surfaced as ImportError exits with status 1.

    ImportError has its own branch because a broken install is the most common
    startup failure, and it must not be mistaken for a successful run.
    """
    with mock.patch(
        "otg_mcp.server.run_server", side_effect=ImportError("no module named snappi")
    ):
        with pytest.raises(SystemExit) as exit_info:
            run_entry_point()

    assert exit_info.value.code == 1


def test_unexpected_exception_during_startup_exits_one():
    """Any other startup exception also exits with status 1.

    The generic handler is the backstop that keeps a traceback from escaping as an
    unhandled crash with an arbitrary exit status.
    """
    with mock.patch(
        "otg_mcp.server.run_server", side_effect=RuntimeError("config file missing")
    ):
        with pytest.raises(SystemExit) as exit_info:
            run_entry_point()

    assert exit_info.value.code == 1


def test_otg_mcp_loggers_are_raised_to_info():
    """Running the entry point sets every ``otg_mcp`` logger to INFO.

    The module has no inline comments by policy, so its logging is the only
    explanation of what it does at runtime; that output disappears if the levels
    are not raised.
    """
    import logging

    probe = logging.getLogger("otg_mcp.probe_for_entry_point_test")
    probe.setLevel(logging.WARNING)

    with mock.patch("otg_mcp.server.run_server"):
        with pytest.raises(SystemExit):
            run_entry_point()

    assert probe.level == logging.INFO
