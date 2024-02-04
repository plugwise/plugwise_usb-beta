"""Plugwise USN Sensor component for Home Assistant."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from plugwise_usb.nodes import PlugwiseNode

from . import PlugwiseUSBEntity
from .const import CB_NEW_NODE, DOMAIN, STICK
from .models import PW_SENSOR_TYPES, PlugwiseSensorEntityDescription

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plugwise USB sensor based on config_entry."""
    api_stick = hass.data[DOMAIN][config_entry.entry_id][STICK]

    async def async_add_sensors(mac: str):
        """Add plugwise sensors for device."""
        entities: list[USBSensor] = []
        entities.extend(
            [
                USBSensor(api_stick.devices[mac], description)
                for description in PW_SENSOR_TYPES
                if description.key in api_stick.devices[mac].features
            ]
        )
        if entities:
            async_add_entities(entities)

    for mac in hass.data[DOMAIN][config_entry.entry_id][Platform.SENSOR]:
        hass.async_create_task(async_add_sensors(mac))

    def discovered_device(mac: str):
        """Add sensors for newly discovered device."""
        hass.async_create_task(async_add_sensors(mac))

    # Listen for discovered nodes
    api_stick.subscribe_stick_callback(discovered_device, CB_NEW_NODE)


class USBSensor(PlugwiseUSBEntity, SensorEntity):  # type: ignore[misc]
    """Representation of a Plugwise USB sensor."""

    def __init__(
        self, node: PlugwiseNode, description: PlugwiseSensorEntityDescription
    ) -> None:
        """Initialize sensor entity."""
        super().__init__(node, description)

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        state_value = getattr(self._node, self.entity_description.state_request_method)
        if state_value is not None:
            return float(round(state_value, 3))
        return None
