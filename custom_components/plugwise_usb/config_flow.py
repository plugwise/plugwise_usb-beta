"""Config flow for Plugwise USB integration."""

from copy import deepcopy
from typing import Any, Final

from plugwise_usb import Stick
from plugwise_usb.exceptions import NodeError, StickError
import voluptuous as vol

from homeassistant.components import usb
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_BASE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_MANUAL_PATH, CONF_USB_PATH, DOMAIN, LOGGER, MANUAL_PATH
from .coordinator import PlugwiseUSBDataUpdateCoordinator
from .util import validate_mac

STICK_RECONF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USB_PATH): str,
    }
)
type PlugwiseUSBConfigEntry = ConfigEntry[PlugwiseUSBDataUpdateCoordinator]

CONF_ZIGBEE_MAC: Final[str] = "zigbee_mac"


@callback
def plugwise_stick_entries(hass):
    """Return existing connections for Plugwise USB-stick domain."""

    return [
        entry.data.get(CONF_USB_PATH)
        for entry in hass.config_entries.async_entries(DOMAIN)
    ]


async def validate_usb_connection(self, device_path=None) -> tuple[dict[str, str], str | None]:
    """Test if device_path is a real Plugwise USB-Stick."""
    errors = {}

    # Avoid creating a 2nd connection to an already configured stick
    if device_path in plugwise_stick_entries(self):
        errors[CONF_BASE] = "already_configured"
        return errors, None

    api_stick = Stick(device_path, cache_enabled=False)
    mac = ""
    try:
        await api_stick.connect()
    except StickError:
        errors[CONF_BASE] = "cannot_connect"
    else:
        try:
            await api_stick.initialize()
            mac = api_stick.mac_stick
        except StickError:
            errors[CONF_BASE] = "stick_init"
    await api_stick.disconnect()
    return errors, mac


class PlugwiseUSBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plugwise USB."""

    VERSION = 1
    MINOR_VERSION = 0

    # no async_step_zeroconf this USB is physical

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step when user initializes a integration."""
        errors: dict[str, str] = {}
        ports = [
            port
            for port in await usb.async_scan_serial_ports(self.hass)
            if isinstance(port, usb.USBDevice)
        ]
        list_of_ports = [
            f"{port.device}, s/n: {port.serial_number or 'n/a'}"
            + (f" - {port.manufacturer}" if port.manufacturer else "")
            for port in ports
        ]
        list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_selection = user_input[CONF_USB_PATH]

            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_manual_path()

            port = ports[list_of_ports.index(user_selection)]
            device_path = port.device
            errors, mac_stick = await validate_usb_connection(self.hass, device_path)
            if not errors:
                await self.async_set_unique_id(
                    unique_id=mac_stick, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Stick", data={CONF_USB_PATH: device_path}
                )

        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema(
                {vol.Required(CONF_USB_PATH): vol.In(list_of_ports)}
            ),
            errors=errors,
        )

    async def async_step_manual_path(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step when manual path to device."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_path = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_input.get(CONF_USB_PATH)
            )
            errors, mac_stick = await validate_usb_connection(self.hass, device_path)
            if not errors:
                await self.async_set_unique_id(
                    unique_id=mac_stick, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Stick", data={CONF_USB_PATH: device_path}
                )
        return self.async_show_form(
            step_id=MANUAL_PATH,
            data_schema=vol.Schema(
                {vol.Required(CONF_USB_PATH, default="/dev/ttyUSB0"): str}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            device_path = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_input.get(CONF_USB_PATH)
            )
            errors, mac_stick = await validate_usb_connection(self.hass, device_path)
            if not errors:
                await self.async_set_unique_id(
                    unique_id=mac_stick, raise_on_progress=False
                )
                self._abort_if_unique_id_mismatch(reason="not_the_same_stick")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_USB_PATH: device_path}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STICK_RECONF_SCHEMA,
                suggested_values=reconfigure_entry.data,
            ),
            description_placeholders={"title": reconfigure_entry.title},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: PlugwiseUSBConfigEntry
    ) -> PlugwiseUSBOptionsFlowHandler:
        """Get the options flow for this handler."""
        return PlugwiseUSBOptionsFlowHandler(config_entry)


class PlugwiseUSBOptionsFlowHandler(OptionsFlow):
    """Plugwise USB options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.coordinator = self.config_entry.runtime_data

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult | None:
        """Handle the input of the plus-device MAC address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            mac = user_input["zigbee_mac"]
            if validate_mac(mac):
                try:
                    self.coordinator.api_stick.plus_pair_request(mac)
                except NodeError as exc:
                    raise HomeAssistantError(f"Pairing of Plus-device {mac} failed") from exc
                return self.async_create_entry(title="", data=user_input)

            errors[CONF_BASE] = "invalid_mac"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_ZIGBEE_MAC): str}),
            errors=errors,
        )

