"""Support for Plugwise devices connected to a Plugwise USB-stick."""
import logging
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_USB_PATH,
    DOMAIN,
    NODES,
    PLUGWISE_USB_PLATFORMS,
    STICK,
)
from .coordinator import PlugwiseUSBDataUpdateCoordinator
from .plugwise_usb import Stick
from .plugwise_usb.api import NodeEvent
from .plugwise_usb.exceptions import StickError

_LOGGER = logging.getLogger(__name__)
UNSUBSCRIBE_DISCOVERY = "unsubscribe_discovery"

class NodeConfigEntry(TypedDict):
    """Plugwise node config entry."""

    mac: str
    coordinator: PlugwiseUSBDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Establish connection with plugwise USB-stick."""

    @callback
    def _async_migrate_entity_entry(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        """Migrate Plugwise entity entry."""
        return async_migrate_entity_entry(config_entry, entity_entry)

    await er.async_migrate_entries(hass, config_entry.entry_id, _async_migrate_entity_entry)

    hass.data.setdefault(DOMAIN, {})
    api_stick = Stick(config_entry.data[CONF_USB_PATH])
    api_stick.cache_folder = hass.config.path(
        STORAGE_DIR, f"plugwisecache-{config_entry.entry_id}"
    )
    hass.data[DOMAIN][config_entry.entry_id] = {STICK: api_stick}

    _LOGGER.debug("Connect & initialize Plugwise USB-Stick")
    try:
        await api_stick.connect()
        await api_stick.initialize()
    except StickError:
        raise ConfigEntryNotReady(
            f"Failed to open connection to Plugwise USB stick at {config_entry.data[CONF_USB_PATH]}"
        ) from StickError

    hass.data[DOMAIN][config_entry.entry_id][NODES]: NodeConfigEntry = {}

    async def async_node_discovered(node_event: NodeEvent, mac: str) -> None:
        """Node is detected."""
        if node_event != NodeEvent.DISCOVERED:
            return
        _LOGGER.debug("async_node_discovered | mac=%s", mac)
        node = api_stick.nodes[mac]
        _LOGGER.debug("async_node_discovered | node_info=%s", node.node_info)
        coordinator = PlugwiseUSBDataUpdateCoordinator(hass, node)
        hass.data[DOMAIN][config_entry.entry_id][NODES][mac] = coordinator
        await coordinator.async_config_entry_first_refresh()
        await node.load()

    hass.data[DOMAIN][config_entry.entry_id][UNSUBSCRIBE_DISCOVERY] = (
        api_stick.subscribe_to_node_events(
            async_node_discovered,
            (NodeEvent.DISCOVERED,),
        )
    )

    _LOGGER.debug("Discover network coordinator")
    try:
        await api_stick.discover_coordinator(load=False)
    except StickError:
        await api_stick.disconnect()
        raise ConfigEntryNotReady(
            "Failed to connect to Circle+"
        ) from StickError

    # Load platforms to allow them to register for node events
    await hass.config_entries.async_forward_entry_setups(
        config_entry, PLUGWISE_USB_PLATFORMS
    )

    # Initiate background discovery task
    hass.async_create_task(
        api_stick.discover_nodes(load=True)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload the Plugwise USB stick connection."""
    hass.data[DOMAIN][config_entry.entry_id][UNSUBSCRIBE_DISCOVERY]()
    unload = await hass.config_entries.async_unload_platforms(
        config_entry, PLUGWISE_USB_PLATFORMS
    )
    api_stick = hass.data[DOMAIN][config_entry.entry_id][STICK]
    await api_stick.disconnect()
    return unload


@callback
def async_migrate_entity_entry(
    config_entry: ConfigEntry, entity_entry: er.RegistryEntry
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
        ("relay", "relay_state"),
    ):
        if entity_entry.unique_id.endswith(old):
            return {"new_unique_id": entity_entry.unique_id.replace(old, new)}

    # No migration needed
    return None
