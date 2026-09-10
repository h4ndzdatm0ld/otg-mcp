import os
from unittest import mock

import pytest

from otg_mcp.config import (
    LoggingConfig,
)


class TestLogConfig:
    """Tests for LoggingConfig."""

    def test_default_log_level(self):
        """Test default log level is INFO."""
        log_config = LoggingConfig()
        assert log_config.LOG_LEVEL == "INFO"

    def test_custom_log_level(self):
        """Test custom log level validation."""
        with mock.patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            log_config = LoggingConfig()
            assert log_config.LOG_LEVEL == "DEBUG"

    def test_invalid_log_level(self):
        """Test invalid log level validation."""
        with mock.patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}):
            with pytest.raises(ValueError):
                LoggingConfig()


class TestConfig:
    """Tests for Config."""

    # test_get_config has been removed since we no longer use a global config instance
    # Configuration is now created directly in the server and passed to components

    @pytest.fixture
    def mock_socket(self):
        """Mock socket for available port tests."""
        with mock.patch("socket.socket") as mock_socket:
            mock_socket_instance = mock.MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_socket_instance
            yield mock_socket_instance
