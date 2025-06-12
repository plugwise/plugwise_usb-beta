"""Plugwise USB Button component for HomeAssistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from plugwise_usb.api import NodeEvent, NodeFeature, PUSHING_FEATURES

from .const import NODES, STICK, UNSUB_NODE_LOADED
from .coordinator import PlugwiseUSBConfigEntry, PlugwiseUSBDataUpdateCoordinator
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(kw_only=True)
class PlugwiseButtonEntityDescription(
    PlugwiseUSBEntityDescription, ButtonEntityDescription
):
    """Describes Plugwise button entity."""

    async_button_fn: str = ""


BUTTON_TYPES: tuple[PlugwiseButtonEntityDescription, ...] = (
    PlugwiseButtonEntityDescription(
        key="auto_join",
        translation_key="enable_auto_join",
        entity_category=EntityCategory.CONFIG,
        async_button_fn="enable_auto_join",
        node_feature=NodeFeature.CIRCLEPLUS,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the USB buttons from a config entry."""

    async def async_add_button(node_event: NodeEvent, mac: str) -> None:
        """Initialize DUC for button."""
        if node_event != NodeEvent.LOADED:
            return
        entities: list[PlugwiseUSBEntity] = []
        if (node_duc := config_entry.runtime_data[NODES].get(mac)) is not None:
            _LOGGER.debug("Add button entities for %s | duc=%s", mac, node_duc.name)
            entities.extend(
                [
                    PlugwiseUSBButtonEntity(node_duc, entity_description)
                    for entity_description in BUTTON_TYPES
                    if entity_description.node_feature in node_duc.node.features
                ]
            )
        if entities:
            async_add_entities(entities, update_before_add=True)

    api_stick = config_entry.runtime_data[STICK]

    # Listen for loaded nodes
    config_entry.runtime_data[Platform.BUTTON] = {}
    config_entry.runtime_data[Platform.BUTTON][UNSUB_NODE_LOADED] = (
        api_stick.subscribe_to_node_events(
            async_add_button,
            (NodeEvent.LOADED,),
        )
    )

    # load any current nodes
    for mac, node in api_stick.nodes.items():
        if node.is_loaded:
            await async_add_button(NodeEvent.LOADED, mac)


async def async_unload_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
) -> None:
    """Unload a config entry."""
    config_entry.runtime_data[Platform.BUTTON][UNSUB_NODE_LOADED]()


class PlugwiseUSBButtonEntity(PlugwiseUSBEntity, ButtonEntity):
    """Representation of a Plugwise USB Data Update Coordinator button."""

    def __init__(
        self,
        node_duc: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseButtonEntityDescription,
    ) -> None:
        """Initialize a button entity."""
        super().__init__(node_duc, entity_description)
        self.async_button_fn = getattr(
            node_duc.node, entity_description.async_button_fn
        )
        self._node_duc = node_duc

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    async def async_press(self) -> None:
        """Button was pressed."""
        await self.async_button_fn()

    async def async_added_to_hass(self):
        """Subscribe for push updates."""
        _LOGGER.warning("MDI: Button added to hass")
#        await super().async_added_to_hass()
        push_features = tuple(
            push_feature
            for push_feature in PUSHING_FEATURES
            if push_feature in self._node_info.features
        )
