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
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from plugwise_usb.api import NodeEvent, NodeFeature

from .const import NODES, STICK, UNSUB_NODE_LOADED
from .coordinator import PlugwiseUSBConfigEntry, PlugwiseUSBDataUpdateCoordinator
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(kw_only=True)
class PlugwiseSwitchEntityDescription(
    PlugwiseUSBEntityDescription, SwitchEntityDescription
):
    """Describes Plugwise switch entity."""

    api_attribute: str = ""
    async_switch_fn: str = ""


SWITCH_TYPES: tuple[PlugwiseSwitchEntityDescription, ...] = (
    PlugwiseSwitchEntityDescription(
        key="relay",
        translation_key="relay",
        device_class=SwitchDeviceClass.OUTLET,
        async_switch_fn="set_relay",
        node_feature=NodeFeature.RELAY,
        api_attribute="state",
    ),
    PlugwiseSwitchEntityDescription(
        key="relay_init",
        translation_key="relay_init",
        async_switch_fn="set_relay_init",
        entity_category=EntityCategory.CONFIG,
        node_feature=NodeFeature.RELAY_INIT,
        api_attribute="state",
    ),
    PlugwiseSwitchEntityDescription(
        key="daylight_mode",
        translation_key="motion_daylight_mode",
        async_switch_fn="set_motion_daylight_mode",
        entity_category=EntityCategory.CONFIG,
        node_feature=NodeFeature.MOTION_CONFIG,
        api_attribute="daylight_mode",
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
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
        if node.is_loaded:
            await async_add_switch(NodeEvent.LOADED, mac)


async def async_unload_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
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
        data = self.coordinator.data.get(self.entity_description.node_feature, None)
        if data is None:
            _LOGGER.debug(
                "No switch data for %s", str(self.entity_description.node_feature)
            )
            return
        self._attr_is_on = getattr(
            self.coordinator.data[self.entity_description.node_feature],
            self.entity_description.api_attribute,
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
