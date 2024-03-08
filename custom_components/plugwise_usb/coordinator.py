"""DataUpdateCoordinator for Plugwise USB-Stick."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    ConfigEntryError,
    DataUpdateCoordinator,
    UpdateFailed,
)
from plugwise_usb.api import NodeFeature, NodeInfo
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
        self._initial_update_done = False
        self.node = node
        if node.node_info.battery_powered:
            _LOGGER.debug("Create battery powered DUC for %s", node.mac)
            super().__init__(
                hass,
                _LOGGER,
                name=f"Battery powered Plugwise node {node.mac}",
                update_method=self.async_node_update,
                always_update=True,
            )

        else:
            _LOGGER.debug("Create normal powered DUC for %s: %s", node.mac, str(update_interval))
            super().__init__(
                hass,
                _LOGGER,
                name=f"Normal powered Plugwise node {node.mac}",
                update_interval=timedelta(seconds=15),
                update_method=self.async_node_update,
                always_update=True,
            )

    async def get_node_info(self) -> NodeInfo:
        """Return node information."""
        node_info: NodeInfo | None = None
        if (node_info := await self.node.node_info_update()) is None:
            raise UpdateFailed(f"Failed to pull node information from Plugwise node: {self.node.mac}")
        if node_info.battery_powered:
            self.always_update = False
        return node_info

    async def async_node_update(self) -> dict[NodeFeature, Any]:
        """Request status update for Plugwise Node."""
        states: dict[NodeFeature, Any] = {}
        if not self._initial_update_done:
            _LOGGER.debug("Initial coordinator update for %s", self.node.mac)
            states[NodeFeature.INFO] = await self.get_node_info()
            self._initial_update_done = True
            return states

        features = tuple(self.async_contexts())
        _LOGGER.debug("Coordinator update for %s, context=%s", self.node.mac, features)
        try:
            states = await self.node.get_state(features)
        except StickError as err:
            raise ConfigEntryError from err
        except (StickTimeout, NodeTimeout) as err:
            raise asyncio.TimeoutError from err
        except NodeError as err:
            raise UpdateFailed from err

        if not states[NodeFeature.AVAILABLE]:
            raise UpdateFailed(f"Plugwise node {self.node.mac} is not on-line.")
        return states
