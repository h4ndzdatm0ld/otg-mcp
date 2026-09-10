import json
import os
from unittest import mock

import pytest

from otg_mcp.config import (
    Config,
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


class TestSchemaPathLoading:
    """Tests for resolving the custom schema directory from a config file."""

    @staticmethod
    def _write_config(tmp_path, config_data):
        """Write config data to a temp file and return its path."""
        config_file = tmp_path / "trafficGeneratorConfig.json"
        config_file.write_text(json.dumps(config_data))
        return str(config_file)

    def test_nested_schemas_object(self, tmp_path):
        """The documented {"schemas": {"schema_path": ...}} form is honored."""
        schema_dir = tmp_path / "custom_schemas"
        schema_dir.mkdir()
        config_file = self._write_config(
            tmp_path,
            {"schemas": {"schema_path": str(schema_dir)}, "targets": {}},
        )

        config = Config(config_file)

        assert config.schemas.schema_path == str(schema_dir)

    def test_legacy_top_level_schema_path(self, tmp_path):
        """A top-level schema_path still works for backward compatibility."""
        schema_dir = tmp_path / "custom_schemas"
        schema_dir.mkdir()
        config_file = self._write_config(
            tmp_path,
            {"schema_path": str(schema_dir), "targets": {}},
        )

        config = Config(config_file)

        assert config.schemas.schema_path == str(schema_dir)

    def test_nested_takes_precedence_over_top_level(self, tmp_path):
        """The nested form wins when both are present."""
        nested_dir = tmp_path / "nested_schemas"
        nested_dir.mkdir()
        legacy_dir = tmp_path / "legacy_schemas"
        legacy_dir.mkdir()
        config_file = self._write_config(
            tmp_path,
            {
                "schemas": {"schema_path": str(nested_dir)},
                "schema_path": str(legacy_dir),
                "targets": {},
            },
        )

        config = Config(config_file)

        assert config.schemas.schema_path == str(nested_dir)

    def test_nonexistent_path_is_ignored(self, tmp_path):
        """A configured path that does not exist leaves schema_path unset."""
        config_file = self._write_config(
            tmp_path,
            {"schemas": {"schema_path": "/does/not/exist"}, "targets": {}},
        )

        config = Config(config_file)

        assert config.schemas.schema_path is None

    def test_missing_schemas_section(self, tmp_path):
        """A config with no schema settings leaves schema_path unset."""
        config_file = self._write_config(tmp_path, {"targets": {}})

        config = Config(config_file)

        assert config.schemas.schema_path is None

    def test_non_object_schemas_section_is_ignored(self, tmp_path):
        """A malformed "schemas" value is ignored rather than raising."""
        config_file = self._write_config(
            tmp_path, {"schemas": "not-an-object", "targets": {}}
        )

        config = Config(config_file)

        assert config.schemas.schema_path is None
