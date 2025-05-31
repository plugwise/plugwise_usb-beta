"""Constants for Plugwise USB component."""

import logging
from typing import Final

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

DOMAIN: Final = "plugwise_usb"

LOGGER = logging.getLogger(__package__)
UNSUB_NODE_LOADED: Final = "Unsubcribe_from_node_loaded_event"
COORDINATOR: Final = "coordinator"
CONF_MANUAL_PATH: Final = "Enter Manually"
MANUAL_PATH: Final = "manual_path"
STICK: Final = "stick"
NODES: Final = "nodes"
USB: Final = "usb"

UNDO_UPDATE_LISTENER: Final = "undo_update_listener"

PLUGWISE_USB_PLATFORMS: Final[list[str]] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
CONF_USB_PATH: Final = "usb_path"

ATTR_MAC_ADDRESS: Final = "mac"

SERVICE_AUTO_JOIN: Final = "enable_auto_joining"
SERVICE_DISABLE_PRODUCTION: Final = "disable_production"
SERVICE_ENABLE_PRODUCTION: Final = "enable_production"
SERVICE_USB_DEVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_MAC_ADDRESS): vol.All(
            cv.string,
            vol.Match(r"^[0-9A-Fa-f]{16}$")
        )
    }
)

# USB SED (battery powered) device constants
ATTR_SED_STAY_ACTIVE: Final = "stay_active"
ATTR_SED_SLEEP_FOR: Final = "sleep_for"
ATTR_SED_MAINTENANCE_INTERVAL: Final = "maintenance_interval"
ATTR_SED_CLOCK_SYNC: Final = "clock_sync"
ATTR_SED_CLOCK_INTERVAL: Final = "clock_interval"

SERVICE_USB_SED_BATTERY_CONFIG: Final = "configure_battery_savings"
SERVICE_USB_SED_BATTERY_CONFIG_SCHEMA: Final = {
    vol.Required(ATTR_SED_STAY_ACTIVE): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=120)
    ),
    vol.Required(ATTR_SED_SLEEP_FOR): vol.All(
        vol.Coerce(int), vol.Range(min=10, max=60)
    ),
    vol.Required(ATTR_SED_MAINTENANCE_INTERVAL): vol.All(
        vol.Coerce(int), vol.Range(min=5, max=1440)
    ),
    vol.Required(ATTR_SED_CLOCK_SYNC): cv.boolean,
    vol.Required(ATTR_SED_CLOCK_INTERVAL): vol.All(
        vol.Coerce(int), vol.Range(min=60, max=10080)
    ),
}


# USB Scan device constants
ATTR_SCAN_DAYLIGHT_MODE: Final = "day_light"
ATTR_SCAN_SENSITIVITY_MODE: Final = "sensitivity_mode"
ATTR_SCAN_RESET_TIMER: Final = "reset_timer"

SCAN_SENSITIVITY_HIGH: Final = "high"
SCAN_SENSITIVITY_MEDIUM: Final = "medium"
SCAN_SENSITIVITY_OFF: Final = "off"
SCAN_SENSITIVITY_MODES = [
    SCAN_SENSITIVITY_HIGH,
    SCAN_SENSITIVITY_MEDIUM,
    SCAN_SENSITIVITY_OFF,
]

SERVICE_USB_SCAN_CONFIG: Final = "configure_scan"
SERVICE_USB_SCAN_CONFIG_SCHEMA = (
    {
        vol.Required(ATTR_SCAN_SENSITIVITY_MODE): vol.In(SCAN_SENSITIVITY_MODES),
        vol.Required(ATTR_SCAN_RESET_TIMER): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=240)
        ),
        vol.Required(ATTR_SCAN_DAYLIGHT_MODE): cv.boolean,
    },
)
