"""Plugwise USB Switch component for HomeAssistant."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from .plugwise_usb.api import NodeFeature
from .plugwise_usb.nodes import PlugwiseNode

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NODES, STICK
from .coordinator import PlugwiseUSBDataUpdateCoordinator
from .entity import (
    PlugwiseUSBEntityDescription,
    PlugwiseUSBEntity,
)


@dataclass
class PlugwiseSwitchEntityDescription(
    SwitchEntityDescription, PlugwiseUSBEntityDescription
):
    """Describes Plugwise switch entity."""
    async_switch_method: str = ""


_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=30)
SWITCH_TYPES: tuple[PlugwiseSwitchEntityDescription, ...] = (
    PlugwiseSwitchEntityDescription(
        key="relay",
        name="Relay state",
        device_class=SwitchDeviceClass.OUTLET,
        async_switch_method="async_relay",
        feature=NodeFeature.RELAY,
    ),
    PlugwiseSwitchEntityDescription(
        key="relay init",
        name="Relay startup state",
        device_class=SwitchDeviceClass.OUTLET,
        async_switch_method="async_relay_init_set",
        entity_category=EntityCategory.CONFIG,
        feature=NodeFeature.RELAY_INIT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the USB switches from a config entry."""
    api_stick = hass.data[DOMAIN][config_entry.entry_id][STICK]

    entities: list[PlugwiseUSBEntity] = []
    for mac, coordinator in hass.data[DOMAIN][config_entry.entry_id][NODES].items():
        if coordinator.data[NodeFeature.INFO] is not None:
            entities.extend(
                [
                    PlugwiseUSBSwitchEntity(
                        coordinator, entity_description, api_stick.nodes[mac]
                    )
                    for entity_description in SWITCH_TYPES
                    if entity_description.feature in coordinator.data[
                        NodeFeature.INFO
                    ].features
                ]
            )
    if entities:
        async_add_entities(entities, update_before_add=True)


class PlugwiseUSBSwitchEntity(PlugwiseUSBEntity, SwitchEntity):
    """Representation of a Plugwise USB Data Update Coordinator switch."""

    def __init__(
        self,
        coordinator: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseSwitchEntityDescription,
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
                "No switch data for %s",
                str(self.entity_description.feature)
            )
            return
        self._attr_is_on = self.coordinator.data[self.entity_description.feature][self.entity_description.key]
        self.async_write_ha_state()

    async def async_switch_node(self, state: bool) -> bool:
        """Switch configuration of Node."""
        self._attr_is_on = await setattr(
            self.node, self.entity_description.async_switch_method, state
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on"""
        await self.async_switch_node(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off"""
        await self.async_switch_node(True)
