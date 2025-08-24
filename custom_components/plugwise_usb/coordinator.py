"""DataUpdateCoordinator for Plugwise USB-Stick."""

from collections import Counter
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from plugwise_usb.api import PUSHING_FEATURES, NodeFeature, PlugwiseNode
from plugwise_usb.exceptions import NodeError, NodeTimeout, StickError, StickTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    ConfigEntryError,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import STICK

_LOGGER = logging.getLogger(__name__)

type PlugwiseUSBConfigEntry = ConfigEntry[PlugwiseUSBDataUpdateCoordinator]


class PlugwiseUSBDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from a Plugwise node."""

    config_entry: PlugwiseUSBConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PlugwiseUSBConfigEntry,
        node: PlugwiseNode,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize Plugwise USB data update coordinator."""
        self.node = node
        self.subscribed_nodefeatures: list[NodeFeature] = []
        self._subscribe_to_feature_fn = self.node.subscribe_to_feature_update
        self.unsubscribe_push_events: list[Callable[[], None]] = []
        if node.node_info.is_battery_powered:
            _LOGGER.debug("Create battery powered DUC for %s", node.mac)
            super().__init__(
                hass,
                _LOGGER,
                config_entry=config_entry,
                name=node.node_info.name,
                update_method=self.async_node_update,
                always_update=True,
            )
        else:
            _LOGGER.debug(
                "Create DUC for %s with update interval %s", node.mac, update_interval
            )
            super().__init__(
                hass,
                _LOGGER,
                name=node.node_info.name,
                update_interval=timedelta(seconds=15),
                update_method=self.async_node_update,
                always_update=True,
            )

        self.api_stick = config_entry.runtime_data[STICK]

    async def async_node_update(self) -> dict[NodeFeature, Any]:
        """Request status update for Plugwise Node."""
        states: dict[NodeFeature, Any] = {}

        # Only unique features
        freq_features = Counter(self.async_contexts())
        features = tuple(freq_features.keys())
        try:
            states = await self.node.get_state(features)
        except StickError as err:
            raise ConfigEntryError from err
        except (StickTimeout, NodeTimeout) as err:
            raise TimeoutError from err
        except NodeError as err:
            raise UpdateFailed from err

        if (
            not self.node.node_info.is_battery_powered
            and self.node.initialized
            and not states[NodeFeature.AVAILABLE].state
        ):
            raise UpdateFailed(
                f"Device '{self.node.node_info.mac}' is (temporarily) not available"
            )

        return states

    async def subscribe_nodefeature(self, node_feature: NodeFeature) -> None:
        """Subscribe to a nodefeature."""
        if (
            node_feature in PUSHING_FEATURES
            and node_feature in self.node.node_info.features
            and node_feature not in self.subscribed_nodefeatures
        ):
            self.unsubscribe_push_events.append(
                self._subscribe_to_feature_fn(
                    self.async_push_event,
                    node_feature,
                )
            )
            self.subscribed_nodefeatures.append(node_feature)

    async def async_push_event(self, feature: NodeFeature, state: Any) -> None:
        """Update data pushed by node."""
        self.async_set_updated_data(
            {
                feature: state,
            }
        )

    async def unsubscribe_all_nodefeatures(self) -> None:
        """Unsubscribe to updates."""
        for unsubscribe_push_event in self.unsubscribe_push_events:
            if unsubscribe_push_event is not None:
                unsubscribe_push_event()
        self.unsubscribe_push_events.clear()
        self.subscribed_nodefeatures.clear()

