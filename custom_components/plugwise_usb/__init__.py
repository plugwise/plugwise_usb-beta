"""Support for Plugwise devices connected to a Plugwise USB-stick."""

import logging
from typing import Any, TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR
from plugwise_usb import Stick
from plugwise_usb.api import NodeEvent
from plugwise_usb.exceptions import StickError

from .const import (
    CONF_USB_PATH,
    DOMAIN,
    NODES,
    PLUGWISE_USB_PLATFORMS,
    STICK,
)
from .coordinator import PlugwiseUSBConfigEntry, PlugwiseUSBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
UNSUBSCRIBE_DISCOVERY = "unsubscribe_discovery"


class NodeConfigEntry(TypedDict):
    """Plugwise node config entry."""

    mac: str
    coordinator: PlugwiseUSBDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: PlugwiseUSBConfigEntry):
    """Establish connection with plugwise USB-stick."""

    @callback
    def _async_migrate_entity_entry(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, Any] | None:
        """Migrate Plugwise entity entry."""
        return async_migrate_entity_entry(config_entry, entity_entry)

    await er.async_migrate_entries(
        hass, config_entry.entry_id, _async_migrate_entity_entry
    )

    api_stick = Stick(config_entry.data[CONF_USB_PATH])
    api_stick.cache_folder = hass.config.path(
        STORAGE_DIR, f"plugwisecache-{config_entry.entry_id}"
    )
    config_entry.runtime_data = {STICK: api_stick}

    _LOGGER.info("Connect & initialize Plugwise USB-Stick...")
    try:
        await api_stick.connect()
        await api_stick.initialize(create_root_cache_folder=True)
    except StickError:
        raise ConfigEntryNotReady(
            f"Failed to open connection to Plugwise USB stick at {config_entry.data[CONF_USB_PATH]}"
        ) from StickError

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_ZIGBEE, str(api_stick.mac_stick))},
        hw_version=str(api_stick.hardware),
        identifiers={(DOMAIN, str(api_stick.mac_stick))},
        manufacturer="Plugwise",
        model="Stick",
        name=str(api_stick.name),
        serial_number=str(api_stick.mac_stick),
        sw_version=str(api_stick.firmware),
    )

    config_entry.runtime_data[NODES]: NodeConfigEntry = {}

    async def async_node_discovered(node_event: NodeEvent, mac: str) -> None:
        """Node is detected."""
        if node_event != NodeEvent.DISCOVERED:
            return
        _LOGGER.debug("async_node_discovered | mac=%s", mac)
        node = api_stick.nodes[mac]
        _LOGGER.debug("async_node_discovered | node_info=%s", node.node_info)
        coordinator = PlugwiseUSBDataUpdateCoordinator(hass, config_entry, node)
        config_entry.runtime_data[NODES][mac] = coordinator
        await node.load()

    config_entry.runtime_data[UNSUBSCRIBE_DISCOVERY] = (
        api_stick.subscribe_to_node_events(
            async_node_discovered,
            (NodeEvent.DISCOVERED,),
        )
    )

    _LOGGER.info("Start to discover the Plugwise network coordinator (Circle+)")
    try:
        await api_stick.discover_coordinator(load=False)
    except StickError:
        await api_stick.disconnect()
        raise ConfigEntryNotReady("Failed to connect to Circle+") from StickError

    # Load platforms to allow them to register for node events
    await hass.config_entries.async_forward_entry_setups(
        config_entry, PLUGWISE_USB_PLATFORMS
    )

    # Initiate background discovery task
    discover_nodes_task = config_entry.async_create_background_task(
        hass,
        api_stick.discover_nodes(load=True),
        f"{DOMAIN}_{config_entry.title}_discover_nodes",
    )

    done, pending = await asyncio.wait(discover_nodes_task, return_when=asyncio.ALL_COMPLETED)

    # Enable/disable automatic joining of available devices when discover_nodes has finished
    if discover_nodes_task.done():
        if config_entry.pref_disable_new_entities:
            _LOGGER.debug("Configuring Circle + NOT to accept any new join requests")
            api_stick.accept_join_request = False
        else:
            _LOGGER.debug("Configuring Circle + to automatically accept new join requests")
            api_stick.accept_join_request = True

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: PlugwiseUSBConfigEntry):
    """Unload the Plugwise USB stick connection."""
    config_entry.runtime_data[UNSUBSCRIBE_DISCOVERY]()
    unload = await hass.config_entries.async_unload_platforms(
        config_entry, PLUGWISE_USB_PLATFORMS
    )
    await config_entry.runtime_data[STICK].disconnect()
    return unload


@callback
def async_migrate_entity_entry(
    config_entry: PlugwiseUSBConfigEntry, entity_entry: er.RegistryEntry
) -> dict[str, Any] | None:
    """Migrate Plugwise USB entity entries.

    - Migrates unique ID for sensors based on entity description name to key.
    """

    # Conversion list of unique ID suffixes
    for old, new in (
        ("power_1s", "last_second"),
        ("power_8s", "last_8_seconds"),
        ("energy_consumption_today", "day_consumption"),
        ("ping", "rtt"),
        ("RSSI_in", "rssi_in"),
        ("RSSI_out", "rssi_out"),
        ("relay_state", "relay"),
    ):
        if entity_entry.unique_id.endswith(old):
            return {"new_unique_id": entity_entry.unique_id.replace(old, new)}

    # No migration needed
    return None
