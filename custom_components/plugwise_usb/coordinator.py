"""DataUpdateCoordinator for Plugwise USB-Stick."""
from collections import Counter
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    ConfigEntryError,
    DataUpdateCoordinator,
    UpdateFailed,
)
from plugwise_usb.api import NodeFeature
from plugwise_usb.exceptions import NodeError, NodeTimeout, StickError, StickTimeout
from plugwise_usb.nodes import PlugwiseNode

_LOGGER = logging.getLogger(__name__)


class PlugwiseUSBDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from a Plugwise node."""

    def __init__(
        self,
        hass: HomeAssistant,
        node: PlugwiseNode,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize Plugwise USB data update coordinator."""
        self.node = node
        if node.node_info.battery_powered:
            _LOGGER.debug("Create battery powered DUC for %s", node.mac)
            super().__init__(
                hass,
                _LOGGER,
                name=node.node_info.name,
                update_method=self.async_node_update,
                always_update=True,
            )
        else:
            _LOGGER.debug("Create DUC for %s with update interval %s", node.mac, update_interval)
            super().__init__(
                hass,
                _LOGGER,
                name=node.node_info.name,
                update_interval=timedelta(seconds=15),
                update_method=self.async_node_update,
                always_update=True,
            )

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

        if not states[NodeFeature.AVAILABLE]:
            raise UpdateFailed("Device is not responding")
        return states
