"""DataUpdateCoordinator for Plugwise USB-Stick."""

from datetime import timedelta
import logging
from typing import Any

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from plugwise_usb.api import NodeFeature
from plugwise_usb.exceptions import NodeError, NodeTimeout, StickError
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

    async def async_node_update(self) -> dict[NodeFeature, Any]:
        """Request status update for Plugwise Node."""
        try:
            async with async_timeout.timeout(30):
                if not self._initial_update_done:
                    _LOGGER.debug(
                        "Initial coordinator update for %s", self.node.mac
                    )
                    self._initial_update_done = await self.node.node_info_update()
                    states: dict[NodeFeature, Any] = {}
                    states[NodeFeature.INFO] = self.node.node_info
                    if self.node.node_info.battery_powered:
                        self.always_update = False
                    return states
                features = set(self.async_contexts())
                _LOGGER.debug(
                    "Coordinator update for %s, context=%s",
                    self.node.mac,
                    str(features),
                )
                return await self.node.get_state(features)
        except StickError as err:
            raise ConfigEntryNotReady from err
        except NodeTimeout as err:
            raise TimeoutError from err
        except NodeError as err:
            raise UpdateFailed(
                f"Failed to pull data from Plugwise node: {err}"
            ) from err
