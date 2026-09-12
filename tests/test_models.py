"""Tests for the response models in otg_mcp.models.models."""

from otg_mcp.models.models import PortInfo


class TestPortInfoInterfaceName:
    """Tests for the PortInfo.interface_name convenience property.

    Callers use interface_name to address a port without caring whether the
    config supplied a distinct interface, so the fallback to location is the
    behaviour that keeps port lookups working for configs that omit interface.
    """

    def test_interface_name_prefers_explicit_interface(self):
        """interface_name returns the interface when one is configured."""
        port = PortInfo(name="p1", location="localhost:5555", interface="enp0s31f6")

        assert port.interface_name == "enp0s31f6"

    def test_interface_name_falls_back_to_location(self):
        """interface_name returns the location when no interface is configured."""
        port = PortInfo(name="p1", location="localhost:5555", interface=None)

        assert port.interface_name == "localhost:5555"
