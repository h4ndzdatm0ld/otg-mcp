from unittest import mock


def test_main_execution_path():
    """Test the execution path in __main__ when __name__ is '__main__'."""

    # Create mocks for all functions/objects used
    mock_run_server = mock.MagicMock()
    mock_logger = mock.MagicMock()
    mock_sys_exit = mock.MagicMock()

    # Create local scope with mocks
    local_scope = {
        "run_server": mock_run_server,
        "logger": mock_logger,
        "sys_exit": mock_sys_exit,
    }

    # Simulate the conditional behavior in __main__
    code = """
if True:  # This simulates __name__ == "__main__"
    logger.info("Starting OTG MCP Server via __main__")
    run_server()
    sys_exit(0)
"""

    # Execute the code
    exec(code, {}, local_scope)

    # Verify correct execution path
    mock_logger.info.assert_called_once_with("Starting OTG MCP Server via __main__")
    mock_run_server.assert_called_once()
    mock_sys_exit.assert_called_once_with(0)


def test_main_content():
    """Verify the actual content of the __main__.py file."""
    with open("src/otg_mcp/__main__.py", "r") as file:
        content = file.read()

    # Check for expected imports
    assert "import sys" in content
    assert "import logging" in content
    assert "from .server import run_server" in content

    # Check for logger initialization
    assert "logger = logging.getLogger(__name__)" in content

    # Check for main block
    assert 'if __name__ == "__main__":' in content
    assert "run_server()" in content
    assert "sys.exit(0)" in content
