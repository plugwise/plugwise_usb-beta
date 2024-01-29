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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (  # noqa: F401
    DOMAIN,
    NODES,
)
from .coordinator import PlugwiseUSBDataUpdateCoordinator
from .entity import (
    PlugwiseUSBEntity,
    PlugwiseUSBEntityDescription,
)
from .plugwise_usb.api import NodeFeature
from .plugwise_usb.nodes import PlugwiseNode

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlugwiseBinarySensorEntityDescription(
    BinarySensorEntityDescription, PlugwiseUSBEntityDescription
):
    """Describes Plugwise switch entity."""

    has_entity_name: bool = True


PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=60)
BINARY_SENSOR_TYPES: tuple[PlugwiseBinarySensorEntityDescription, ...] = (
    PlugwiseBinarySensorEntityDescription(
        key="Motion",
        name=None,
        device_class=BinarySensorDeviceClass.MOTION,
        feature=NodeFeature.MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plugwise USB binary sensor based on config_entry."""

    entities: list[PlugwiseUSBEntity] = []
    plugwise_nodes = hass.data[DOMAIN][config_entry.entry_id][NODES]
    for mac, node in plugwise_nodes.items():
        _LOGGER.debug("Check for binary_sensor setup for %s", mac)
        if node.data[NodeFeature.INFO] is not None:
            _LOGGER.debug("- NodeFeature.INFO: %s", str(node.data[NodeFeature.INFO].features))

            entities.extend(
                [
                    PlugwiseUSBBinarySensor(node, entity_description)
                    for entity_description in BINARY_SENSOR_TYPES
                    if entity_description.feature in node.data[
                        NodeFeature.INFO
                    ].features
                ]
            )
    if entities:
        async_add_entities(entities, update_before_add=True)


class PlugwiseUSBBinarySensor(PlugwiseUSBEntity, BinarySensorEntity):
    """Representation of a Plugwise USB Binary Sensor."""

    def __init__(
        self,
        coordinator: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseBinarySensorEntityDescription,
        node: PlugwiseNode,
    ) -> None:
        """Initialize a switch entity."""
        super().__init__(coordinator, entity_description)
        self.node = node

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data[self.entity_description.feature] is None:
            _LOGGER.warning(
                "No binary sensor data for %s",
                str(self.entity_description.feature)
            )
            return
        self._attr_is_on = getattr(
            self.coordinator.data[self.entity_description.feature],
            self.entity_description.key
        )
        self.async_write_ha_state()
