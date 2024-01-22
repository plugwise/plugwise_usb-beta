"""Plugwise USB stick base entity."""

from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN
from .coordinator import PlugwiseUSBDataUpdateCoordinator
from .plugwise_usb.api import (
    NodeFeature,
    NodeInfo,
)


@dataclass
class PlugwiseUSBRequiredKeysMixin:
    """Default mixin for required keys."""

    feature: NodeFeature


@dataclass
class PlugwiseUSBEntityDescription(EntityDescription, PlugwiseUSBRequiredKeysMixin):
    """Describes Toon sensor entity."""


class PlugwiseUSBEntity(CoordinatorEntity):
    """Representation of a base class for Plugwise USB entity."""

    entity_description: PlugwiseUSBEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseUSBEntityDescription,
    ) -> None:
        """Initialize a Plugwise USB entity."""
        super().__init__(coordinator, context=entity_description.feature)
        node_info: NodeInfo = self.coordinator.data[NodeFeature.INFO]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, node_info.mac)},
            "name": node_info.name,
            "manufacturer": "Plugwise",
            "model": node_info.model,
            "sw_version": f"{node_info.firmware}",
        }
        self._attr_name = entity_description.name
        self._attr_unique_id = f"{node_info.mac}-{entity_description.key}"
        self.entity_description = entity_description
