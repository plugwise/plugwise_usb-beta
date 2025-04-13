"""Plugwise USB stick base entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from plugwise_usb.api import PUSHING_FEATURES, NodeFeature, NodeInfo

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
        self.unsubscribe_push_events: Callable[[], None] | None = None
        self._node_info: NodeInfo = node_duc.node.node_info
        self._attr_unique_id = f"{self._node_info.mac}-{entity_description.key}"
        self._subscribe_to_feature_fn = node_duc.node.subscribe_to_feature_update
        self._via_device = (DOMAIN, str(node_duc.api_stick.mac_stick))

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
            sw_version=str(self._node_info.firmware),
            via_device=self._via_device,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.node_duc.node_info.available and super().available

    async def async_added_to_hass(self):
        """Subscribe for push updates."""
        await super().async_added_to_hass()
        push_features = tuple(
            push_feature
            for push_feature in PUSHING_FEATURES
            if push_feature in self._node_info.features
        )
        # Subscribe to events
        if push_features:
            self.unsubscribe_push_events = self._subscribe_to_feature_fn(
                self.async_push_event,
                push_features,
            )

    async def async_push_event(self, feature: NodeFeature, state: Any) -> None:
        """Update data on pushed event."""
        if self.node_duc is None:
            _LOGGER.warning(
                "Unable to push event=%s, state=%s, mac=%s",
                feature,
                state,
                self._node_info.mac,
            )
        else:
            self.node_duc.async_set_updated_data(
                {
                    feature: state,
                }
            )

    async def async_will_remove_from_hass(self):
        """Unsubscribe to updates."""
        if self.unsubscribe_push_events is not None:
            self.unsubscribe_push_events()
            self.unsubscribe_push_events = None
        await super().async_will_remove_from_hass()
