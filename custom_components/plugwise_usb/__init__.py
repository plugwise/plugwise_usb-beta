"""Support for Plugwise devices connected to a Plugwise USB-stick."""

import asyncio
import logging
from typing import Any, TypedDict

from plugwise_usb import Stick
from plugwise_usb.api import NodeEvent
from plugwise_usb.exceptions import NodeError, StickError

from homeassistant.components.device_tracker import ATTR_MAC
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_USB_PATH,
    DOMAIN,
    NODES,
    PLUGWISE_USB_PLATFORMS,
    SERVICE_DISABLE_PRODUCTION,
    SERVICE_ENABLE_PRODUCTION,
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

    api_stick = Stick(config_entry.data[CONF_USB_PATH])
    api_stick.cache_folder = hass.config.path(
        STORAGE_DIR, f"plugwisecache-{config_entry.entry_id}"
    )
    config_entry.runtime_data = {STICK: api_stick}

    _LOGGER.info("Connect & initialize Plugwise USB-Stick...")
    try:
        await api_stick.connect()
        await api_stick.initialize(create_root_cache_folder=True)
    except StickError as exc:
        raise ConfigEntryNotReady(
            f"Failed to open connection to Plugwise USB stick at {config_entry.data[CONF_USB_PATH]}"
        ) from exc

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

    config_entry.runtime_data[NODES] = {}

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
    except StickError as exc:
        await api_stick.disconnect()
        raise ConfigEntryNotReady("Failed to connect to Circle+") from exc

    # Load platforms to allow them to register for node events
    await hass.config_entries.async_forward_entry_setups(
        config_entry, PLUGWISE_USB_PLATFORMS
    )

    async def enable_production(call: ServiceCall) -> bool:
        """Enable production-logging for a Node."""
        mac = call.data[ATTR_MAC]
        try:
            result = await api_stick.set_energy_intervals(mac, 60, 60)
        except (NodeError, StickError) as exc:
            raise HomeAssistantError(
                f"Enable production logs failed for {mac}: {exc}"
            ) from exc
        return result

    async def disable_production(call: ServiceCall) -> bool:
        """Disable production-logging for a Node."""
        mac = call.data[ATTR_MAC]
        try:
            result = await api_stick.set_energy_intervals(mac, 60, 0)
        except (NodeError, StickError) as exc:
            raise HomeAssistantError(
                f"Disable production logs failed for {mac}: {exc}"
            ) from exc
        return result

    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE_PRODUCTION, enable_production, SERVICE_USB_DEVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_PRODUCTION,
        disable_production,
        SERVICE_USB_DEVICE_SCHEMA,
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

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: PlugwiseUSBConfigEntry
) -> bool:
    """Unload the Plugwise USB stick connection."""
    config_entry.runtime_data[UNSUBSCRIBE_DISCOVERY]()
    for coordinator in config_entry.runtime_data[NODES].values():
        await coordinator.unsubscribe_all_nodefeatures()
    unload = await hass.config_entries.async_unload_platforms(
        config_entry, PLUGWISE_USB_PLATFORMS
    )
    await config_entry.runtime_data[STICK].disconnect()
    return unload


async def async_remove_config_entry_device(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    api_stick = config_entry.runtime_data[STICK]
    removable = False
    for identifier in device_entry.identifiers:
        if (
            identifier[0] == DOMAIN
            and identifier[1] not in (str(api_stick.mac_stick), str(api_stick.mac_coordinator))
        ):
            mac = identifier[1]
            removable = True
            break

    if removable:
        try:
            await api_stick.unregister_node(mac)
        except NodeError as exc:
            _LOGGER.warning("Plugwise node %s unregistering failed: %s", mac, exc)
            return True # Must return True for device_registry removal to happen!

        _LOGGER.debug("Plugwise device %s successfully removed", mac)
        return True

    return False


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
