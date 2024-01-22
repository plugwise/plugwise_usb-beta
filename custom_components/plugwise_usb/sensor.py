"""Plugwise USN Sensor component for Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NODES
from .entity import (
    PlugwiseUSBEntity,
    PlugwiseUSBEntityDescription,
)
from .plugwise_usb.api import NodeFeature


@dataclass
class PlugwiseSensorEntityDescription(
    SensorEntityDescription, PlugwiseUSBEntityDescription
):
    """Describes Plugwise sensor entity."""

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=30)
SENSOR_TYPES: tuple[PlugwiseSensorEntityDescription, ...] = (
    PlugwiseSensorEntityDescription(
        key="last_second",
        name="Power usage",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        feature=NodeFeature.POWER,
    ),
    PlugwiseSensorEntityDescription(
        key="last_8_seconds",
        name="Power usage last 8 seconds",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        feature=NodeFeature.POWER,
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="day_consumption",
        name="Energy consumption today",
        device_class=SensorDeviceClass.ENERGY,
        #state_class=SensorStateClass.TOTAL_INCREASING,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        feature=NodeFeature.ENERGY,
    ),
    PlugwiseSensorEntityDescription(
        key="rtt",
        name="Network roundtrip",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        feature=NodeFeature.PING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseSensorEntityDescription(
        key="RSSI_in",
        name="Inbound RSSI",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        feature=NodeFeature.PING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseSensorEntityDescription(
        key="RSSI_out",
        name="Outbound RSSI",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        feature=NodeFeature.PING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plugwise USB sensor based on config_entry."""

    entities: list[PlugwiseUSBEntity] = []
    plugwise_nodes = hass.data[DOMAIN][config_entry.entry_id][NODES]
    for node in plugwise_nodes.values():
        if node.data[NodeFeature.INFO] is not None:
            entities.extend(
                [
                    PlugwiseUSBSensorEntity(node, entity_description)
                    for entity_description in SENSOR_TYPES
                    if entity_description.feature in node.data[
                        NodeFeature.INFO
                    ].features
                ]
            )
    if entities:
        async_add_entities(entities, update_before_add=True)


class PlugwiseUSBSensorEntity(PlugwiseUSBEntity, SensorEntity):
    """Representation of a Plugwise USB Data Update Coordinator sensor."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.entity_description.feature, None)
        if data is None:
            _LOGGER.warning(
                "No sensor data for %s",
                str(self.entity_description.feature)
            )
            return
        self._attr_native_value = getattr(
            self.coordinator.data[
                self.entity_description.feature
            ],
            self.entity_description.key.lower()
        )
        if self.entity_description.feature == NodeFeature.ENERGY:
            self._attr_last_reset = getattr(
                self.coordinator.data[
                    self.entity_description.feature
                ],
                f"{self.entity_description.key}_reset"
            )
        self.async_write_ha_state()
