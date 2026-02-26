"""Test the Plugwise config flow."""

from typing import Final
from unittest.mock import MagicMock, patch

import pytest

from custom_components.plugwise_usb.config_flow import CONF_MANUAL_PATH
from custom_components.plugwise_usb.const import CONF_USB_PATH, DOMAIN
from plugwise_usb.exceptions import StickError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SOURCE
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry
import serial.tools.list_ports

TEST_MAC: Final[str] = "01:23:45:67:AB"
TEST_PORT_PATH: Final[str] = "/dev/ttyUSB1"
TEST_PORT2_PATH: Final[str] = "/dev/ttyUSB2"


def com_port():
    """Mock of a serial port."""

    port = serial.tools.list_ports_common.ListPortInfo(TEST_PORT_PATH)
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = TEST_PORT_PATH
    port.description = "Some serial port"
    return port


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_flow_select(hass, mock_usb_stick: MagicMock):
    """Test user flow when USB-stick is selected from list."""
    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}
    assert result.get("step_id") == "user"
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: port_select}
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_USB_PATH: TEST_PORT_PATH}

    # Retry to ensure configuring the same port is not allowed
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: port_select}
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "already_configured"}


async def test_user_flow_manual_selected_show_form(hass):
    """Test user step form when manual path is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "manual_path"


async def test_user_flow_manual(
    hass, mock_usb_stick: MagicMock, init_integration: MockConfigEntry
):
    """Test user flow when USB-stick is manually entered."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: TEST_PORT2_PATH},
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_USB_PATH: TEST_PORT2_PATH}


async def test_invalid_connection(hass):
    """Test invalid connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USB_PATH: "/dev/null"},
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_empty_connection(hass):
    """Test empty connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    await hass.async_block_till_done()

    try:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USB_PATH: None},
        )
        pytest.fail("Empty connection was accepted")
    except InvalidData:
        assert True

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}


async def test_failed_connect(hass, mock_usb_stick_error: MagicMock):
    """Test we handle failed connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: "/dev/null"},
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_failed_initialization(hass, mock_usb_stick_init_error: MagicMock):
    """Test we handle failed initialization of Plugwise USB-stick."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: "/dev/null"},
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "stick_init"}


async def _start_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_path: str,
) -> ConfigFlowResult:
    """Initialize a reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    reconfigure_result = await mock_config_entry.start_reconfigure_flow(hass)

    assert reconfigure_result["type"] is FlowResultType.FORM
    assert reconfigure_result["step_id"] == "reconfigure"

    return await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"], {CONF_USB_PATH: device_path}
    )


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    result = await _start_reconfigure_flow(hass, mock_config_entry, TEST_PORT_PATH)

    assert result["type"] is FlowResultType.FORM
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data.get(CONF_HOST) == TEST_PORT_PATH


async def test_reconfigure_flow_other_stick(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_usb_stick: AsyncMock,
) -> None:
    """Test reconfigure flow aborts on other Smile ID."""
    mock_usb_stick.mac_stick = TEST_MAC

    result = await _start_reconfigure_flow(hass, mock_config_entry, TEST_PORT_PATH)

    assert result["type"] is FlowResultType.FORM
    assert result["reason"] == "not_the_same_stick"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (None, "already_configured"),
        (StickError, "cannot_connect"),
        (StickError, "stick_init"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_usb_stick: AsyncMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test we handle each reconfigure exception error."""

    mock_usb_stick.connect.side_effect = side_effect

    result = await _start_reconfigure_flow(hass, mock_config_entry, TEST_PORT_PATH)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": reason}
    assert result.get("step_id") == "reconfigure"