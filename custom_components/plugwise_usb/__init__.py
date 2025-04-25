"""Support for Plugwise devices connected to a Plugwise USB-stick."""

import asyncio
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
    ATTR_MAC_ADDRESS,
    CONF_USB_PATH,
    DOMAIN,
    NODES,
    PLUGWISE_USB_PLATFORMS,
    SERVICE_USB_DEVICE_ADD,
    SERVICE_USB_DEVICE_REMOVE,
    SERVICE_USB_DEVICE_SCHEMA,
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

    # Disable adding new entities
    hass.config_entries.async_update_entry(config_entry, pref_disable_new_entities=True)

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

    # Initiate background nodes discovery task
    config_entry.async_create_task(
        hass,
        api_stick.discover_nodes(load=True),
        "discover_nodes",
    )

    while True:
        await asyncio.sleep(1)
        if api_stick.network_discovered:
            break
    # Enable/disable automatic joining of available devices when the network is up
    if config_entry.pref_disable_new_entities:
        _LOGGER.debug("Configuring Circle + NOT to accept any new join requests")
        api_stick.accept_join_request = False
    else:
        _LOGGER.debug("Configuring Circle + to automatically accept new join requests")
        api_stick.accept_join_request = True

    async def device_add(service):
        """Manually add device to Plugwise zigbee network."""
        await api_stick.register_node(service.data[ATTR_MAC_ADDRESS])

    async def device_remove(service):
        """Manually remove device from Plugwise zigbee network."""
        await api_stick.unregister_node(service.data[ATTR_MAC_ADDRESS])
        _LOGGER.debug(
            "Send request to remove device using mac %s from Plugwise network",
            service.data[ATTR_MAC_ADDRESS],
        )
        device_entry = device_registry.async_get_device(
            {(DOMAIN, service.data[ATTR_MAC_ADDRESS])}, set()
        )
        if device_entry:
            _LOGGER.debug(
                "Remove device %s from Home Assistant", service.data[ATTR_MAC_ADDRESS]
            )
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )

    hass.services.async_register(
        DOMAIN, SERVICE_USB_DEVICE_ADD, device_add, SERVICE_USB_DEVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_USB_DEVICE_REMOVE, device_remove, SERVICE_USB_DEVICE_SCHEMA
    )

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
