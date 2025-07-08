"""Plugwise USB Event component for HomeAssistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from plugwise_usb.api import NodeEvent, NodeFeature

from homeassistant.components.event import (
    EventDeviceClass, 
    EventEntity, 
    EventEntityDescription,
)
from homeassistant.const import EntityCategory, Platform, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NODES, STICK, UNSUB_NODE_LOADED
from .coordinator import PlugwiseUSBConfigEntry, PlugwiseUSBDataUpdateCoordinator
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(kw_only=True)
class PlugwiseEventEntityDescription(
    PlugwiseUSBEntityDescription, EventEntityDescription
):
    """Describes Plugwise Event entity."""

    api_attribute: str = ""
    event_types: list[str] = []


EVENT_TYPES: tuple[PlugwiseEventEntityDescription, ...] = (
    PlugwiseEventEntityDescription(
        key="button_press_i_group_1",
        translation_key="button_press_i_group_1",
        node_feature=NodeFeature.SWITCH,
        device_class=EventDeviceClass.BUTTON,
        api_attribute="state",
        event_types=["single_press"],
    ),
    PlugwiseEventEntityDescription(
        key="button_press_o_group_1",
        translation_key="button_press_o_group_1",
        node_feature=NodeFeature.SWITCH,
        device_class=EventDeviceClass.BUTTON,
        api_attribute="state",
        event_types=["single_press"],
    ),
    PlugwiseEventEntityDescription(
        key="button_press_i_group_2",
        translation_key="button_press_i_group_2",
        node_feature=NodeFeature.SWITCH,
        device_class=EventDeviceClass.BUTTON,
        api_attribute="state",
        event_types=["single_press"],
    ),
    PlugwiseEventEntityDescription(
        key="button_press_o_group_2",
        translation_key="button_press_o_group_2",
        node_feature=NodeFeature.SWITCH,
        device_class=EventDeviceClass.BUTTON,
        api_attribute="state",
        event_types=["single_press"],
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the USB Event from a config entry."""
    async def async_add_event(node_event: NodeEvent, mac: str) -> None:
        """Initialize DUC for event."""
        if node_event != NodeEvent.LOADED:
            return
        entities: list[PlugwiseUSBEntity] = []
        if (node_duc := config_entry.runtime_data[NODES].get(mac)) is not None:
            _LOGGER.debug("Add event entities for %s | duc=%s", mac, node_duc.name)
            entities.extend(
                [
                    PlugwiseUSBEventEntity(node_duc, entity_description)
                    for entity_description in EVENT_TYPES
                    if entity_description.node_feature in node_duc.node.features
                ]
            )
        if entities:
            async_add_entities(entities, update_before_add=True)

    api_stick = config_entry.runtime_data[STICK]

    # Listen for loaded nodes
    config_entry.runtime_data[Platform.EVENT] = {}
    config_entry.runtime_data[Platform.EVENT][UNSUB_NODE_LOADED] = (
        api_stick.subscribe_to_node_events(
            async_add_event,
            (NodeEvent.LOADED,),
        )
    )

    # load any current nodes
    for mac, node in api_stick.nodes.items():
        if node.is_loaded:
            await async_add_event(NodeEvent.LOADED, mac)


async def async_unload_entry(
    config_entry: PlugwiseUSBConfigEntry,
) -> None:
    """Unload a config entry."""
    config_entry.runtime_data[Platform.EVENT][UNSUB_NODE_LOADED]()


class PlugwiseUSBEventEntity(PlugwiseUSBEntity, EventEntity):
    """Representation of a Plugwise USB Data Update Coordinator Event entity."""

    def __init__(
        self,
        node_duc: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseEventEntityDescription,
    ) -> None:
        """Initialize a event entity."""
        super().__init__(node_duc, entity_description)
        self.event_types = entity_description.event_types

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.entity_description.node_feature, None)
        if data is None:
            _LOGGER.debug(
                "No %s event data for %s",
                self.entity_description.node_feature,
                self._node_info.mac,
            )
            return
        #SWITCH logic
        state_value = getattr( data, "state" )
        group_value = getattr( data, "group" )
        match self.entity_description.key:
            case "button_press_i_group_1":
                if state_value is True and group_value == 1:
                    self._trigger_event(self.entity_description.event_types[0])
                    self.async_write_ha_state()
                return
            case "button_press_o_group_1":
                if state_value is False and group_value == 1:
                    self._trigger_event(self.entity_description.event_types[0])
                    self.async_write_ha_state()
                return
            case "button_press_i_group_2":
                if state_value is True and group_value == 2:
                    self._trigger_event(self.entity_description.event_types[0])
                    self.async_write_ha_state()
                return
            case "button_press_o_group_2":
                if state_value is False and group_value == 2:
                    self._trigger_event(self.entity_description.event_types[0])
                    self.async_write_ha_state()
                return

