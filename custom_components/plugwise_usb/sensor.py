"""Plugwise USN Sensor component for Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from .plugwise_usb.api import NodeFeature

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
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const  import DOMAIN, NODES
from .entity import (
    PlugwiseUSBEntityDescription,
    PlugwiseUSBEntity,
)

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
        feature=NodeFeature.POWER,
    ),
    PlugwiseSensorEntityDescription(
        key="last_8_seconds",
        name="Power usage last 8 seconds",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        feature=NodeFeature.POWER,
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="day_consumption",
        name="Energy consumption today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        feature=NodeFeature.ENERGY,
    ),
    PlugwiseSensorEntityDescription(
        key="rtt",
        name="Network roundtrip",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        feature=NodeFeature.PING,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseSensorEntityDescription(
        key="RSSI_in",
        name="Inbound RSSI",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        feature=NodeFeature.PING,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseSensorEntityDescription(
        key="RSSI_out",
        name="Outbound RSSI",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        feature=NodeFeature.PING,
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
    for coordinator in hass.data[DOMAIN][config_entry.entry_id][NODES].values():
        if coordinator.data[NodeFeature.INFO] is not None:
            entities.extend(
                [
                    PlugwiseUSBSensorEntity(coordinator, entity_description)
                    for entity_description in SENSOR_TYPES
                    if entity_description.feature in coordinator.data[
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
        if self.coordinator.data[self.entity_description.feature] is None:
            _LOGGER.warning(
                "No sensor data for %s",
                str(self.entity_description.feature)
            )
            return
        self._attr_native_value = getattr(
            self.coordinator.data[
                self.entity_description.feature
            ],
            self.entity_description.key
        )
        if self.entity_description.feature == NodeFeature.ENERGY:
            self._attr_last_reset = getattr(
                self.coordinator.data[
                    self.entity_description.feature
                ],
                f"{self.entity_description.key}_reset"
            )
        self.async_write_ha_state()
