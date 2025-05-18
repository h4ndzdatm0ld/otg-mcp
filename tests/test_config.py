import os
from unittest import mock

import pytest

from otg_mcp.config import (
    Config,
    DirectConnectionConfig,
    LoggingConfig,
    get_config,
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


class TestDirectConnectionConfig:
    """Tests for DirectConnectionConfig."""

    def test_default_direct_connection_config(self):
        """Test default direct connection config."""
        direct_config = DirectConnectionConfig()
        assert direct_config.DEFAULT_HOST == "localhost"
        assert direct_config.DEFAULT_PORT == 443

    def test_custom_direct_connection_config(self):
        """Test custom direct connection config."""
        with mock.patch.dict(
            os.environ,
            {
                "DEFAULT_HOST": "test-host",
                "DEFAULT_PORT": "8080",
            },
        ):
            direct_config = DirectConnectionConfig()
            assert direct_config.DEFAULT_HOST == "test-host"
            assert direct_config.DEFAULT_PORT == 8080


class TestConfig:
    """Tests for Config."""

    def test_get_config(self):
        """Test get_config returns global config instance."""
        config = get_config()
        assert config is not None
        assert isinstance(config, Config)

        # Get it again, should be the same instance
        config2 = get_config()
        assert config is config2

    @pytest.fixture
    def mock_socket(self):
        """Mock socket for available port tests."""
        with mock.patch("socket.socket") as mock_socket:
            mock_socket_instance = mock.MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_socket_instance
            yield mock_socket_instance

    def test_get_available_port_first_try(self, mock_socket):
        """Test get_available_port when first port is available."""
        mock_socket.connect_ex.return_value = 1  # Port is available

        config = Config()

        port = config.get_available_port()
        assert port == 8000
        mock_socket.connect_ex.assert_called_once_with(("localhost", 8000))

    def test_get_available_port_second_try(self, mock_socket):
        """Test get_available_port when second port is available."""
        mock_socket.connect_ex.side_effect = [
            0,
            1,
        ]  # First port unavailable, second available

        config = Config()

        port = config.get_available_port()
        assert port == 8001
        assert mock_socket.connect_ex.call_count == 2
        mock_socket.connect_ex.assert_has_calls(
            [mock.call(("localhost", 8000)), mock.call(("localhost", 8001))]
        )

    def test_get_available_port_no_ports(self, mock_socket):
        """Test get_available_port when no ports are available."""
        mock_socket.connect_ex.return_value = 0  # All ports unavailable

        config = Config()

        with pytest.raises(RuntimeError) as excinfo:
            config.get_available_port()

        assert "No available ports found" in str(excinfo.value)

    def test_discover_instances(self):
        """Test discover_instances returns empty list in non-AWS mode."""
        config = Config()
        instances = config.discover_instances()
        assert instances == []
