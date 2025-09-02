"""Plugwise USB Binary Sensor component for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from plugwise_usb.api import NodeEvent, NodeFeature

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NODES, STICK, UNSUB_NODE_LOADED
from .coordinator import PlugwiseUSBConfigEntry
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=60)


@dataclass(kw_only=True)
class PlugwiseBinarySensorEntityDescription(
    PlugwiseUSBEntityDescription, BinarySensorEntityDescription
):
    """Describes Plugwise binary sensor entity."""

    api_attribute: str = ""


BINARY_SENSOR_TYPES: tuple[PlugwiseBinarySensorEntityDescription, ...] = (
    PlugwiseBinarySensorEntityDescription(
        key="motion",
        name=None,
        device_class=BinarySensorDeviceClass.MOTION,
        node_feature=NodeFeature.MOTION,
        api_attribute="state",
    ),
    PlugwiseBinarySensorEntityDescription(
        key="motion_config_dirty",
        translation_key="motion_config_dirty",
        node_feature=NodeFeature.MOTION_CONFIG,
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        api_attribute="dirty",
    ),
    PlugwiseBinarySensorEntityDescription(
        key="battery_config_dirty",
        translation_key="battery_config_dirty",
        node_feature=NodeFeature.BATTERY,
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        api_attribute="dirty",
    ),
    PlugwiseBinarySensorEntityDescription(
        key="sense_config_dirty",
        translation_key="sense_config_dirty",
        node_feature=NodeFeature.SENSE_HYSTERESIS,
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        api_attribute="dirty",
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plugwise USB binary sensor based on config_entry."""

    async def async_add_binary_sensor(node_event: NodeEvent, mac: str) -> None:
        """Initialize DUC for binary sensor."""
        if node_event != NodeEvent.LOADED:
            return
        entities: list[PlugwiseUSBEntity] = []
        if (node_duc := config_entry.runtime_data[NODES].get(mac)) is not None:
            for entity_description in BINARY_SENSOR_TYPES:
                if entity_description.node_feature not in node_duc.node.features:
                    continue
                entities.append(PlugwiseUSBBinarySensor(node_duc, entity_description))
                _LOGGER.debug(
                    "Add %s binary sensor for node %s",
                    entity_description.translation_key,
                    node_duc.node.name,
                )

        if entities:
            async_add_entities(entities)

    api_stick = config_entry.runtime_data[STICK]

    # Listen for loaded nodes
    config_entry.runtime_data[Platform.BINARY_SENSOR] = {}
    config_entry.runtime_data[Platform.BINARY_SENSOR][UNSUB_NODE_LOADED] = (
        api_stick.subscribe_to_node_events(
            async_add_binary_sensor,
            (NodeEvent.LOADED,),
        )
    )

    # load current nodes
    for mac, node in api_stick.nodes.items():
        if node.is_loaded:
            await async_add_binary_sensor(NodeEvent.LOADED, mac)
        else:
            _LOGGER.debug("Adding binary_sensor(s) for node %s failed, not loaded", mac)

async def async_unload_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
) -> None:
    """Unload a config entry."""
    config_entry.runtime_data[Platform.BINARY_SENSOR][UNSUB_NODE_LOADED]()


class PlugwiseUSBBinarySensor(PlugwiseUSBEntity, BinarySensorEntity):
    """Representation of a Plugwise USB Binary Sensor."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.entity_description.node_feature, None)
        if data is None:
            _LOGGER.debug(
                "No %s binary sensor data for %s",
                self.entity_description.node_feature,
                self._node_info.mac,
            )
            return
        if self.coordinator.data[self.entity_description.node_feature] is None:
            _LOGGER.info(
                "No binary sensor data for %s",
                str(self.entity_description.node_feature),
            )
            return
        self._attr_is_on = getattr(
            self.coordinator.data[self.entity_description.node_feature],
            self.entity_description.api_attribute,
        )
        self.async_write_ha_state()
