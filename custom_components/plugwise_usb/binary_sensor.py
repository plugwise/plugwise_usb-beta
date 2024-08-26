"""Plugwise USB Binary Sensor component for Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from plugwise_usb.api import NodeEvent, NodeFeature

from .const import DOMAIN, NODES, STICK, UNSUB_NODE_LOADED
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=60)


@dataclass(kw_only=True)
class PlugwiseBinarySensorEntityDescription(PlugwiseUSBEntityDescription, BinarySensorEntityDescription):
    """Describes Plugwise binary sensor entity."""


BINARY_SENSOR_TYPES: tuple[PlugwiseBinarySensorEntityDescription, ...] = (
    PlugwiseBinarySensorEntityDescription(
        key="motion",
        name=None,
        device_class=BinarySensorDeviceClass.MOTION,
        node_feature=NodeFeature.MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plugwise USB binary sensor based on config_entry."""

    async def async_add_binary_sensor(node_event: NodeEvent, mac: str) -> None:
        """Initialize DUC for binary sensor."""
        if node_event != NodeEvent.LOADED:
            return
        entities: list[PlugwiseUSBEntity] = []
        if (node_duc := hass.data[DOMAIN][config_entry.entry_id][NODES].get(mac)) is not None:
            _LOGGER.debug("Add binary_sensor entities for %s | duc=%s", mac, node_duc.name)
            entities.extend(
                [
                    PlugwiseUSBBinarySensor(node_duc, entity_description)
                    for entity_description in BINARY_SENSOR_TYPES
                    if entity_description.node_feature in node_duc.node.features
                ]
            )
        if entities:
            async_add_entities(entities, update_before_add=True)

    api_stick = hass.data[DOMAIN][config_entry.entry_id][STICK]

    # Listen for loaded nodes
    hass.data[DOMAIN][config_entry.entry_id][Platform.BINARY_SENSOR] = {}
    hass.data[DOMAIN][config_entry.entry_id][Platform.BINARY_SENSOR][UNSUB_NODE_LOADED] = (
        api_stick.subscribe_to_node_events(
            async_add_binary_sensor,
            (NodeEvent.LOADED,),
            )
    )

    # load current nodes
    for mac, node in api_stick.nodes.items():
        if node.loaded:
            await async_add_binary_sensor(NodeEvent.LOADED, mac)


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Unload a config entry."""
    hass.data[DOMAIN][config_entry.entry_id][Platform.SENSOR][UNSUB_NODE_LOADED]()


class PlugwiseUSBBinarySensor(PlugwiseUSBEntity, BinarySensorEntity):
    """Representation of a Plugwise USB Binary Sensor."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data[self.entity_description.node_feature] is None:
            _LOGGER.info(
                "No binary sensor data for %s",
                str(self.entity_description.node_feature)
            )
            return
        self._attr_is_on = getattr(
            self.coordinator.data[self.entity_description.node_feature],
            self.entity_description.key
        )
        self.async_write_ha_state()
