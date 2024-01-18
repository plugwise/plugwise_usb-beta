"""DataUpdateCoordinator for Plugwise USB-Stick."""

import async_timeout
from asyncio import TimeoutError
from datetime import timedelta
from typing import Any
import logging

from .plugwise_usb.api import NodeFeature, PUSHING_FEATURES
from .plugwise_usb.nodes import PlugwiseNode
from .plugwise_usb.exceptions import NodeError, NodeTimeout, StickError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

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
        if node.node_info.battery_powered:
            _LOGGER.debug("Create battery powered DUC for %s", node.mac)
            super().__init__(
                hass,
                _LOGGER,
                name=f"Plugwise USB node {node.mac}",
                update_method=self.async_node_update,
                always_update=False,
            )
        else:
            _LOGGER.debug("Create normal powered DUC for %s", node.mac)
            super().__init__(
                hass,
                _LOGGER,
                name=f"Plugwise USB node {node.mac}",
                update_interval=update_interval,
                update_method=self.async_node_update,
                always_update=False,
            )
        self.node = node
        # self._initial_update = True

        # Subscribe to events
        self.event_subscription_ids: list[int] = [
            node.subscribe_to_event(
                push_feature,
                self.async_push_event,
            )
            for push_feature in PUSHING_FEATURES
            if push_feature in node.features
        ]

    async def async_push_event(self, feature: NodeFeature, state: Any) -> None:
        """"Callback to be notified for subscribed events."""
        await self.async_set_updated_data(
            {
                feature: state,
            }
        )

    async def async_node_update(self) -> dict[NodeFeature, Any]:
        """Request status update for Plugwise Node."""
        try:
            async with async_timeout.timeout(30):
                # if self._initial_update:
                #     _LOGGER.debug(
                #         "Initial coordinator update for %s", self.node.mac
                #     )
                #     self._initial_update = await self.node.async_load(
                #         from_cache=True, lazy_load=True
                #     )
                #     return await self.node.async_get_state((NodeFeature.INFO,))

                features = tuple(self.async_contexts())
                if not features:
                    _LOGGER.debug(
                        "Coordinator update for %s, context=<empty>",
                        self.node.mac,
                    )   
                    features += (NodeFeature.INFO,)
                _LOGGER.debug(
                    "Coordinator update for %s, context=%s",
                    self.node.mac,
                    str(features),
                )
                return await self.node.async_get_state(features)
        except StickError as err:
            raise ConfigEntryNotReady from err
        except NodeTimeout as err:
            raise TimeoutError from err
        except NodeError as err:
            raise UpdateFailed(
                f"Failed to retrieve data from Plugwise node: {err}"
            ) from err

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        for subscription_id in self.event_subscription_ids:
            self.node.unsubscribe(subscription_id)
        await super().async_shutdown()
