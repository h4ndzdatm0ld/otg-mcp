"""
Tests for validating that apiVersion field is properly rejected in configurations.
"""

import pytest

from otg_mcp.config import TargetConfig


def test_target_config_rejects_api_version():
    """Test that TargetConfig model rejects apiVersion field."""
    target_data = {
        "apiVersion": "1.30.0",  # This should be rejected
        "ports": {
            "p1": {"location": "localhost:5555", "name": "p1"}
        }
    }

    with pytest.raises(ValueError) as exc_info:
        target = TargetConfig(**target_data)

    assert "Extra inputs are not permitted" in str(exc_info.value)
    assert "apiVersion" in str(exc_info.value)

    valid_data = {
        "ports": {
            "p1": {"location": "localhost:5555", "name": "p1"}
        }
    }
    target = TargetConfig.model_validate(valid_data)
    assert "p1" in target.ports
    assert target.ports["p1"].location == "localhost:5555"
