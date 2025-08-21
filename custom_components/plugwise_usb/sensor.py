"""Plugwise USB Sensor component for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from plugwise_usb.api import NodeEvent, NodeFeature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    Platform,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NODES, STICK, UNSUB_NODE_LOADED
from .coordinator import PlugwiseUSBConfigEntry
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(kw_only=True)
class PlugwiseSensorEntityDescription(
    PlugwiseUSBEntityDescription, SensorEntityDescription
):
    """Describes Plugwise sensor entity."""


SENSOR_TYPES: tuple[PlugwiseSensorEntityDescription, ...] = (
    PlugwiseSensorEntityDescription(
        key="last_second",
        translation_key="power_last_second",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        node_feature=NodeFeature.POWER,
    ),
    PlugwiseSensorEntityDescription(
        key="last_8_seconds",
        translation_key="power_last_8_seconds",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        node_feature=NodeFeature.POWER,
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="hour_consumption",
        translation_key="energy_hour_consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        node_feature=NodeFeature.ENERGY,
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="hour_production",
        translation_key="energy_hour_production",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        node_feature=NodeFeature.ENERGY,
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="day_consumption",
        translation_key="energy_day_consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        node_feature=NodeFeature.ENERGY,
    ),
    PlugwiseSensorEntityDescription(
        key="day_production",
        translation_key="energy_day_production",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        node_feature=NodeFeature.ENERGY,
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="rtt",
        translation_key="ping_rrt",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        node_feature=NodeFeature.PING,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseSensorEntityDescription(
        key="rssi_in",
        translation_key="ping_rssi_in",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        node_feature=NodeFeature.PING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseSensorEntityDescription(
        key="rssi_out",
        translation_key="ping_rssi_out",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        node_feature=NodeFeature.PING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        node_feature=NodeFeature.SENSE,
        suggested_display_precision=2,
    ),
    PlugwiseSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        node_feature=NodeFeature.SENSE,
        suggested_display_precision=2,
    ),
    PlugwiseSensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        node_feature=NodeFeature.AVAILABLE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plugwise USB sensor based on config_entry."""

    async def async_add_sensor(node_event: NodeEvent, mac: str) -> None:
        """Initialize DUC for sensor."""
        _LOGGER.debug("async_add_sensor | %s | node_event=%s", mac, node_event)
        if node_event != NodeEvent.LOADED:
            return
        entities: list[PlugwiseUSBEntity] = []
        if (node_duc := config_entry.runtime_data[NODES].get(mac)) is not None:
            _LOGGER.debug("Add sensor entities for %s | duc=%s", mac, node_duc.node.name)
            entities.extend(
                [
                    PlugwiseUSBSensorEntity(node_duc, entity_description)
                    for entity_description in SENSOR_TYPES
                    if entity_description.node_feature in node_duc.node.features
                ]
            )
        else:
            _LOGGER.debug("async_add_sensor | %s | GET MAC FAILED", mac)

        if entities:
            async_add_entities(entities, update_before_add=True)

    api_stick = config_entry.runtime_data[STICK]

    # Listen for loaded nodes
    config_entry.runtime_data[Platform.SENSOR] = {}
    config_entry.runtime_data[Platform.SENSOR][UNSUB_NODE_LOADED] = (
        api_stick.subscribe_to_node_events(
            async_add_sensor,
            (NodeEvent.LOADED,),
        )
    )

    # load current nodes
    for mac, node in api_stick.nodes.items():
        if node.is_loaded:
            await async_add_sensor(NodeEvent.LOADED, mac)


async def async_unload_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
) -> None:
    """Unload a config entry."""
    config_entry.runtime_data[Platform.SENSOR][UNSUB_NODE_LOADED]()


class PlugwiseUSBSensorEntity(PlugwiseUSBEntity, SensorEntity):
    """Representation of a Plugwise USB Data Update Coordinator sensor."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.entity_description.node_feature, None)
        if data is None:
            _LOGGER.debug(
                "No %s sensor data for %s",
                self.entity_description.node_feature,
                self._node_info.mac,
            )
            return
        self._attr_native_value = getattr(
            self.coordinator.data[self.entity_description.node_feature],
            self.entity_description.key,
        )
        if self.entity_description.node_feature == NodeFeature.ENERGY:
            self._attr_last_reset = getattr(
                self.coordinator.data[self.entity_description.node_feature],
                f"{self.entity_description.key}_reset",
            )
        self.async_write_ha_state()
