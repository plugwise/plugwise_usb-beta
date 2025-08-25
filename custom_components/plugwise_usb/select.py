"""Plugwise USB Select component for HomeAssistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
import logging

from plugwise_usb.api import MotionSensitivity, NodeEvent, NodeFeature

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NODES, STICK, UNSUB_NODE_LOADED
from .coordinator import PlugwiseUSBConfigEntry, PlugwiseUSBDataUpdateCoordinator
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(kw_only=True)
class PlugwiseSelectEntityDescription(
    PlugwiseUSBEntityDescription, SelectEntityDescription
):
    """Describes Plugwise select entity."""

    async_select_fn: str = ""
    options_enum: type[Enum]

SELECT_TYPES: tuple[PlugwiseSelectEntityDescription, ...] = (
    PlugwiseSelectEntityDescription(
        key="sensitivity_level",
        translation_key="motion_sensitivity_level",
        async_select_fn="set_motion_sensitivity_level",
        entity_category=EntityCategory.CONFIG,
        node_feature=NodeFeature.MOTION_CONFIG,
        options_enum = MotionSensitivity,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the USB selects from a config entry."""

    async def async_add_select(node_event: NodeEvent, mac: str) -> None:
        """Initialize DUC for select."""
        if node_event != NodeEvent.LOADED:
            return
        entities: list[PlugwiseUSBEntity] = []
        if (node_duc := config_entry.runtime_data[NODES].get(mac)) is not None:
            for entity_description in SELECT_TYPES:
                if entity_description.node_feature not in node_duc.node.features:
                    continue
                entities.append(PlugwiseUSBSelectEntity(node_duc, entity_description))
                LOGGER.debug(
                    "Add %s select for node %s",
                    entity_description.translation_key,
                    node_duc.node.name,
                )
        if entities:
            async_add_entities(entities)

    api_stick = config_entry.runtime_data[STICK]

    # Listen for loaded nodes
    config_entry.runtime_data[Platform.SELECT] = {}
    config_entry.runtime_data[Platform.SELECT][UNSUB_NODE_LOADED] = (
        api_stick.subscribe_to_node_events(
            async_add_select,
            (NodeEvent.LOADED,),
        )
    )

    # load any current nodes
    for mac, node in api_stick.nodes.items():
        if node.is_loaded:
            await async_add_select(NodeEvent.LOADED, mac)


async def async_unload_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
) -> None:
    """Unload a config entry."""
    config_entry.runtime_data[Platform.SELECT][UNSUB_NODE_LOADED]()


class PlugwiseUSBSelectEntity(PlugwiseUSBEntity, SelectEntity):
    """Representation of a Plugwise USB Data Update Coordinator select."""

    def __init__(
        self,
        node_duc: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseSelectEntityDescription,
    ) -> None:
        """Initialize a select entity."""
        super().__init__(node_duc, entity_description)
        self.async_select_fn = getattr(
            node_duc.node, entity_description.async_select_fn
        )
        self._attr_options = [o.name.lower() for o in entity_description.options_enum]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.entity_description.node_feature, None)
        if data is None:
            _LOGGER.debug(
                "No %s select data for %s",
                str(self.entity_description.node_feature),
                self._node_info.mac,
            )
            return

        current_option = getattr(
            data,
            self.entity_description.key,
        )
        self._attr_current_option = current_option.name.lower()
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change to the selected entity option."""
        normalized = option.strip().lower()
        if normalized not in self._attr_options:
            raise ValueError(f"Unsupported option: {option}")
        value = self.entity_description.options_enum[normalized.upper()]
        await self.async_select_fn(value)
        self._attr_current_option = normalized
        self.async_write_ha_state()
