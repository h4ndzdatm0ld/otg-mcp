"""
Tests for validating that apiVersion field is properly rejected in configurations.
"""

import json
import os
import tempfile

import pytest

from otg_mcp.config import Config, TargetConfig


class TestApiVersionValidation:
    """Tests for validating apiVersion field rejection."""

    def test_target_config_rejects_api_version(self):
        """Test that TargetConfig model rejects apiVersion field."""
        # Create a dictionary with apiVersion field
        target_data = {
            "apiVersion": "1.30.0",  # This should be rejected
            "ports": {
                "p1": {"location": "localhost:5555", "name": "p1"}
            }
        }
        
        # Attempt to create a TargetConfig with the apiVersion field
        with pytest.raises(ValueError) as exc_info:
            target = TargetConfig.model_validate(target_data)
        
        # Verify the error message contains information about extra fields
        assert "Extra inputs are not permitted" in str(exc_info.value)
        assert "apiVersion" in str(exc_info.value)
        
        # Verify that providing only valid fields works
        valid_data = {
            "ports": {
                "p1": {"location": "localhost:5555", "name": "p1"}
            }
        }
        target = TargetConfig.model_validate(valid_data)
        assert "p1" in target.ports
        assert target.ports["p1"].location == "localhost:5555"

    def test_config_file_with_api_version(self):
        """Test that Config rejects configuration files with apiVersion field."""
        # Create a temporary config file with apiVersion field
        config_data = {
            "targets": {
                "test-target": {
                    "apiVersion": "1.30.0",  # This should be rejected
                    "ports": {
                        "p1": {"location": "localhost:5555", "name": "p1"}
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as temp_file:
            json.dump(config_data, temp_file)
            temp_file_path = temp_file.name
        
        try:
            # Attempt to load the config file
            with pytest.raises(ValueError) as exc_info:
                config = Config(temp_file_path)
            
            # Check error message
            assert "apiVersion is no longer supported" in str(exc_info.value)
            assert "determined automatically" in str(exc_info.value)
            
            # Test with valid config (no apiVersion)
            valid_config = {
                "targets": {
                    "test-target": {
                        "ports": {
                            "p1": {"location": "localhost:5555", "name": "p1"}
                        }
                    }
                }
            }
            
            # Write valid config to a new temp file
            with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as valid_file:
                json.dump(valid_config, valid_file)
                valid_file_path = valid_file.name
            
            try:
                # This should succeed
                config = Config(valid_file_path)
                assert "test-target" in config.targets.targets
                assert "p1" in config.targets.targets["test-target"].ports
            finally:
                # Clean up the valid config temp file
                if os.path.exists(valid_file_path):
                    os.unlink(valid_file_path)
        
        finally:
            # Clean up the temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
