"""Plugwise USB stick base entity."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from plugwise_usb.api import NodeFeature, NodeInfo

from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlugwiseUSBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class PlugwiseUSBEntityDescription(EntityDescription):
    """Describes Plugwise sensor entity."""

    node_feature: NodeFeature


class PlugwiseUSBEntity(CoordinatorEntity):
    """Representation of a base class for Plugwise USB entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        node_duc: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseUSBEntityDescription,
    ) -> None:
        """Initialize a Plugwise USB entity."""
        super().__init__(node_duc, context=entity_description.node_feature)
        self.node_duc = node_duc
        self.entity_description = entity_description
        self._node_info: NodeInfo = node_duc.node.node_info
        self._attr_unique_id = f"{self._node_info.mac}-{entity_description.key}"
        self._via_device = (DOMAIN, str(node_duc.api_stick.mac_stick))

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.node_duc.node.available and super().available

    @property
    def device_info(self) -> DeviceInfo:
        """Return DeviceInfo for each created entity."""
        return DeviceInfo(
            connections={(CONNECTION_ZIGBEE, str(self._node_info.mac))},
            hw_version=str(self._node_info.version),
            identifiers={(DOMAIN, str(self._node_info.mac))},
            manufacturer="Plugwise",
            model=str(self._node_info.model),
            model_id=self._node_info.model_type,
            name=str(self._node_info.name),
            serial_number=str(self._node_info.mac),
            sw_version=str(self._node_info.firmware),
            via_device=self._via_device,
        )

    async def async_added_to_hass(self):
        """Subscribe for push updates."""
        await super().async_added_to_hass()
        await self.node_duc.subscribe_nodefeature(
                 self.entity_description.node_feature
              )

    async def async_will_remove_from_hass(self):
        """Unsubscribe to updates."""
        await super().async_will_remove_from_hass()
