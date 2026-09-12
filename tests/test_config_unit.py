"""Unit tests for otg_mcp.config.

These cover the JSON config loader's failure handling, the Pydantic validators
on LoggingConfig/PortConfig, and setup_logging. Nothing here touches a traffic
generator: config loading is pure file and model work.
"""

import json
import logging
import os
from unittest import mock

import pytest
from pydantic import ValidationError

from otg_mcp.config import Config, LoggingConfig, PortConfig, TargetConfig


@pytest.fixture
def preserve_root_logger():
    """Restore the root logger's handlers and level after a test.

    setup_logging mutates global logging state, which would otherwise leak into
    every test that runs afterwards in the same process.
    """
    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    saved_level = root_logger.level
    module_logger = logging.getLogger("otg_mcp")
    saved_module_level = module_logger.level
    try:
        yield root_logger
    finally:
        root_logger.handlers = saved_handlers
        root_logger.setLevel(saved_level)
        module_logger.setLevel(saved_module_level)


def write_config(tmp_path, payload):
    """Write a config document to a temp file and return its path.

    Args:
        tmp_path: pytest temp directory
        payload: Object to serialise, or a raw string to write verbatim

    Returns:
        str: Path to the written file
    """
    config_file = tmp_path / "trafficGeneratorConfig.json"
    if isinstance(payload, str):
        config_file.write_text(payload)
    else:
        config_file.write_text(json.dumps(payload))
    return str(config_file)


class TestLoggingConfigValidator:
    """Tests for the LOG_LEVEL validator on LoggingConfig."""

    def test_lowercase_level_is_normalised(self):
        """A lower-case level is accepted and upper-cased.

        setup_logging resolves the level with getattr(logging, LOG_LEVEL), which
        only works for the upper-case spelling, so normalising here is what keeps
        a lower-case config value usable.
        """
        assert LoggingConfig(LOG_LEVEL="debug").LOG_LEVEL == "DEBUG"

    @pytest.mark.parametrize(
        "level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )
    def test_every_standard_level_is_accepted(self, level):
        """All five standard logging levels pass validation."""
        assert LoggingConfig(LOG_LEVEL=level).LOG_LEVEL == level

    def test_unknown_level_is_rejected(self):
        """An unknown level raises rather than silently defaulting.

        A typo would otherwise resolve to an AttributeError deep inside
        setup_logging, which swallows exceptions, leaving logging misconfigured.
        """
        with pytest.raises(ValueError):
            LoggingConfig(LOG_LEVEL="TRACE")


class TestPortConfigValidators:
    """Tests for the fallback validators on PortConfig."""

    def test_explicit_values_are_kept(self):
        """Supplied location, name and interface are all preserved as given."""
        port = PortConfig(location="localhost:5555", name="p1", interface="eth0")

        assert (port.location, port.name, port.interface) == (
            "localhost:5555",
            "p1",
            "eth0",
        )

    def test_name_falls_back_to_location(self):
        """An omitted name is derived from location.

        Ports are addressed by name downstream, so a config that only states a
        location still has to yield a usable name.
        """
        port = PortConfig(location="localhost:5555")

        assert port.name == "localhost:5555"

    def test_interface_only_port_derives_location_and_name(self):
        """A port given only an interface derives both location and name from it.

        This is the backward compatibility PortConfig exists to provide. It used
        to silently fail: the fallbacks were per-field validators, which run in
        field-declaration order and see only earlier fields, and interface is
        declared last - so info.data never contained it and a port configured
        with just an interface came out with location=None and name=None.
        """
        port = PortConfig(interface="eth0")

        assert port.location == "eth0"
        assert port.name == "eth0"

    def test_non_mapping_input_is_passed_through_untouched(self):
        """A non-mapping input reaches Pydantic's own error handling unchanged.

        The model validator runs before Pydantic has coerced the input, so it can
        be handed something that is not a dict. It must not try to index that,
        and must let Pydantic raise the normal validation error instead.
        """
        with pytest.raises(ValidationError):
            PortConfig.model_validate("not-a-mapping")

    def test_explicit_values_are_not_overwritten_by_interface(self):
        """An explicit location and name win over the interface fallback.

        The fallback fills gaps; it must never override what the operator wrote.
        """
        port = PortConfig(location="host:5555", name="p1", interface="eth0")

        assert port.location == "host:5555"
        assert port.name == "p1"


class TestConfigDefaults:
    """Tests for Config construction without a config file."""

    def test_default_target_is_added_when_nothing_is_configured(self):
        """With no file and no targets, a localhost development target is seeded."""
        config = Config()

        assert "localhost:8443" in config.targets.targets
        assert set(config.targets.targets["localhost:8443"].ports) == {"p1", "p2"}

    def test_env_supplied_targets_suppress_the_default_target(self):
        """Targets already present from the environment are left untouched.

        TargetsConfig is a BaseSettings, so targets can arrive from the
        environment; when they do, Config must not inject the localhost
        development target on top of them.
        """
        env_targets = json.dumps({"gen.example.com:8443": {"ports": {}}})
        with mock.patch.dict(os.environ, {"targets": env_targets}):
            config = Config()

        assert list(config.targets.targets) == ["gen.example.com:8443"]


class TestLoadConfigFile:
    """Tests for Config.load_config_file."""

    def test_targets_are_loaded_from_file(self, tmp_path):
        """A well-formed file replaces the default targets with its own."""
        path = write_config(
            tmp_path,
            {
                "targets": {
                    "gen.example.com:8443": {
                        "ports": {"p1": {"location": "localhost:5555", "name": "p1"}}
                    }
                }
            },
        )

        config = Config(path)

        assert list(config.targets.targets) == ["gen.example.com:8443"]
        assert config.targets.targets["gen.example.com:8443"].ports["p1"].name == "p1"

    def test_missing_file_raises_file_not_found(self, tmp_path):
        """A nonexistent config path fails loudly instead of running target-less.

        The server surfaces this at startup, which is the only place an operator
        can still fix the path.
        """
        with pytest.raises(FileNotFoundError):
            Config(str(tmp_path / "does-not-exist.json"))

    def test_invalid_json_propagates_decode_error(self, tmp_path):
        """A malformed document propagates json.JSONDecodeError."""
        path = write_config(tmp_path, "{not json")

        with pytest.raises(json.JSONDecodeError):
            Config(path)

    def test_document_without_targets_key_raises_value_error(self, tmp_path):
        """A document missing the 'targets' property is rejected."""
        path = write_config(tmp_path, {"logging": {"LOG_LEVEL": "INFO"}})

        with pytest.raises(ValueError):
            Config(path)

    def test_non_mapping_targets_value_propagates(self, tmp_path):
        """A 'targets' value that is not a mapping propagates the resulting error.

        The loader iterates targets.items(); a list here must not be swallowed
        into a silently empty target set.
        """
        path = write_config(tmp_path, {"targets": ["gen.example.com:8443"]})

        with pytest.raises(AttributeError):
            Config(path)

    @pytest.mark.parametrize(
        "target_data",
        ["not-a-dict", {"apiVersion": "1.0"}],
        ids=["not_a_mapping", "no_ports_key"],
    )
    def test_target_without_ports_is_skipped(self, tmp_path, target_data):
        """A target lacking a ports dictionary is skipped, not fatal.

        One malformed entry must not take down the whole server, so the good
        targets in the same file still load.
        """
        path = write_config(
            tmp_path,
            {
                "targets": {
                    "bad.example.com:8443": target_data,
                    "good.example.com:8443": {"ports": {"p1": {"name": "p1"}}},
                }
            },
        )

        config = Config(path)

        assert list(config.targets.targets) == ["good.example.com:8443"]

    def test_target_with_extra_fields_is_skipped(self, tmp_path):
        """A target carrying forbidden extra fields is skipped, not fatal.

        TargetConfig forbids extras (apiVersion is the historical offender), so
        this pins that such a target is dropped while its siblings still load.
        """
        path = write_config(
            tmp_path,
            {
                "targets": {
                    "bad.example.com:8443": {"ports": {}, "apiVersion": "1.0"},
                    "good.example.com:8443": {"ports": {"p1": {"name": "p1"}}},
                }
            },
        )

        config = Config(path)

        assert list(config.targets.targets) == ["good.example.com:8443"]

    def test_pydantic_v1_extra_field_wording_is_also_skipped(self, tmp_path):
        """A validation error phrased the Pydantic V1 way is skipped too.

        load_config_file special-cases the V1 message 'extra fields not
        permitted'; installed Pydantic V2 says 'Extra inputs are not permitted',
        so that path is only reachable with a synthesised error. This pins the
        skip-and-continue behaviour of that branch.
        """
        real_target_config = TargetConfig

        def fake_target_config(**target_data):
            if "apiVersion" in target_data:
                raise ValueError("extra fields not permitted")
            return real_target_config(**target_data)

        path = write_config(
            tmp_path,
            {
                "targets": {
                    "bad.example.com:8443": {"ports": {}, "apiVersion": "1.0"},
                    "good.example.com:8443": {"ports": {"p1": {"name": "p1"}}},
                }
            },
        )

        with mock.patch("otg_mcp.config.TargetConfig", side_effect=fake_target_config):
            with mock.patch("otg_mcp.config.ValidationError", ValueError):
                config = Config(path)

        assert list(config.targets.targets) == ["good.example.com:8443"]


class TestSetupLogging:
    """Tests for Config.setup_logging."""

    def test_configured_level_is_applied_and_logging_is_handled(
        self, preserve_root_logger
    ):
        """The configured level reaches the root and otg_mcp loggers, with a handler.

        This is the whole point of setup_logging: without it the server would
        emit nothing in a process that has not configured logging itself.
        """
        root_logger = preserve_root_logger
        root_logger.handlers = []

        config = Config()
        config.logging.LOG_LEVEL = "DEBUG"
        config.setup_logging()

        assert root_logger.level == logging.DEBUG
        assert logging.getLogger("otg_mcp").level == logging.DEBUG
        assert root_logger.handlers

    def test_existing_handlers_are_levelled_to_the_configured_level(
        self, preserve_root_logger
    ):
        """Handlers already on the root logger are raised or lowered to the level.

        Setting only the logger's level is not enough: a handler left at its own
        level silently filters records the logger allowed through. There used to
        be a branch here that installed a console handler when the root had none,
        but logging.basicConfig above always does that, so it was unreachable.
        """
        root_logger = preserve_root_logger
        noisy = logging.StreamHandler()
        noisy.setLevel(logging.CRITICAL)
        root_logger.handlers = [noisy]

        config = Config()
        config.logging.LOG_LEVEL = "WARNING"
        config.setup_logging()

        assert noisy.level == logging.WARNING

    def test_existing_handlers_are_not_duplicated(self, preserve_root_logger):
        """An already-configured root logger keeps exactly its own handlers.

        Adding another handler on every call would double every log line in
        hosts that configure logging before starting the server.
        """
        root_logger = preserve_root_logger
        existing = logging.StreamHandler()
        root_logger.handlers = [existing]

        config = Config()
        config.setup_logging()

        assert root_logger.handlers == [existing]

    def test_unresolvable_level_does_not_raise(self, preserve_root_logger):
        """A level that logging cannot resolve is reported, not raised.

        Logging setup is best-effort: the server must still come up, so this
        pins that a bad level leaves the root logger untouched instead of
        aborting startup.
        """
        root_logger = preserve_root_logger
        root_logger.setLevel(logging.WARNING)

        config = Config()
        config.logging.LOG_LEVEL = "NOT_A_LEVEL"
        config.setup_logging()

        assert root_logger.level == logging.WARNING
