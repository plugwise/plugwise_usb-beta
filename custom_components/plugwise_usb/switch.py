"""Plugwise USB Switch component for HomeAssistant."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from plugwise_usb.api import NodeEvent, NodeFeature

from .const import DOMAIN, NODES, STICK, UNSUB_NODE_LOADED
from .coordinator import PlugwiseUSBDataUpdateCoordinator
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(kw_only=True)
class PlugwiseSwitchEntityDescription(PlugwiseUSBEntityDescription, SwitchEntityDescription):
    """Describes Plugwise switch entity."""

    async_switch_fn: str = ""


SWITCH_TYPES: tuple[PlugwiseSwitchEntityDescription, ...] = (
    PlugwiseSwitchEntityDescription(
        key="relay_state",
        translation_key="relay",
        device_class=SwitchDeviceClass.OUTLET,
        async_switch_fn="switch_relay",
        node_feature=NodeFeature.RELAY,
    ),
    PlugwiseSwitchEntityDescription(
        key="relay_init_state",
        translation_key="relay_init",
        device_class=SwitchDeviceClass.OUTLET,
        async_switch_fn="switch_relay_init",
        entity_category=EntityCategory.CONFIG,
        node_feature=NodeFeature.RELAY_INIT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the USB switches from a config entry."""

    async def async_add_switch(node_event: NodeEvent, mac: str) -> None:
        """Initialize DUC for switch."""
        if node_event != NodeEvent.LOADED:
            return
        entities: list[PlugwiseUSBEntity] = []
        if (node_duc := config_entry.runtime_data[NODES].get(mac)) is not None:
            _LOGGER.debug("Add switch entities for %s | duc=%s", mac, node_duc.name)
            entities.extend(
                [
                    PlugwiseUSBSwitchEntity(node_duc, entity_description)
                    for entity_description in SWITCH_TYPES
                    if entity_description.node_feature in node_duc.node.features
                ]
            )
        if entities:
            async_add_entities(entities, update_before_add=True)

    api_stick = config_entry.runtime_data[STICK]

    # Listen for loaded nodes
    config_entry.runtime_data[Platform.SWITCH] = {}
    config_entry.runtime_data[Platform.SWITCH][UNSUB_NODE_LOADED] = (
        api_stick.subscribe_to_node_events(
            async_add_switch,
            (NodeEvent.LOADED,),
            )
    )

    # load any current nodes
    for mac, node in api_stick.nodes.items():
        if node.loaded:
            await async_add_switch(NodeEvent.LOADED, mac)


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Unload a config entry."""
    config_entry.runtime_data[Platform.SWITCH][UNSUB_NODE_LOADED]()


class PlugwiseUSBSwitchEntity(PlugwiseUSBEntity, SwitchEntity):
    """Representation of a Plugwise USB Data Update Coordinator switch."""

    def __init__(
        self,
        node_duc: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseSwitchEntityDescription,
    ) -> None:
        """Initialize a switch entity."""
        super().__init__(node_duc, entity_description)
        self.async_switch_fn = getattr(
            node_duc.node, entity_description.async_switch_fn
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data[self.entity_description.node_feature] is None:
            _LOGGER.info(
                "No switch data for %s",
                str(self.entity_description.node_feature)
            )
            return
        self._attr_is_on = getattr(
            self.coordinator.data[self.entity_description.node_feature],
            self.entity_description.key
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._attr_is_on = await self.async_switch_fn(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._attr_is_on = await self.async_switch_fn(False)
        self.async_write_ha_state()
