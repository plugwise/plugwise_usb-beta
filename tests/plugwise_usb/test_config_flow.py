"""Test the Plugwise config flow."""

from collections.abc import Generator
from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

from plugwise_usb.exceptions import StickError
import pytest

from homeassistant.components.plugwise_usb.config_flow import CONF_MANUAL_PATH
from homeassistant.components.plugwise_usb.const import CONF_USB_PATH, DOMAIN
from homeassistant.components.usb import USBDevice
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
# from pytest_homeassistant_custom_component.common import MockConfigEntry
from tests.common import MockConfigEntry

type MockFixture = Generator[MagicMock | AsyncMock]

TEST_MAC: Final[str] = "01:23:45:67:AB"
TEST_MAC2: Final[str] = "02:23:45:67:AB"
TEST_USB_PATH: Final[str] = "/dev/ttyUSB1"
TEST_USB2_PATH: Final[str] = "/dev/ttyUSB2"


@pytest.fixture(name="serial_ports", autouse=True)
def usb_comports() -> MockFixture:
    """Mock scan_serial_ports."""
    with patch(
        "homeassistant.components.plugwise_usb.config_flow.usb.async_scan_serial_ports",
        AsyncMock(return_value=[mocked_com_port()]),
    ) as comports_mock:
        yield comports_mock


def mocked_com_port()-> USBDevice:
    """Mock of a serial port."""
    return USBDevice(
        device=TEST_USB_PATH,
        vid="04D2",
        pid="162E",
        serial_number="1234",
        manufacturer="Virtual serial port",
        description="Some serial port",
    )


async def test_user_flow_select(hass, mock_usb_stick: MagicMock):
    """Test user flow when USB-stick is selected from list."""
    port = mocked_com_port()
    port_select = f"{port.device}, s/n: {port.serial_number} - {port.manufacturer}"

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
    assert result.get("data") == {CONF_USB_PATH: TEST_USB_PATH}

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
    hass, mock_usb_stick_not_setup: MagicMock, init_integration: MockConfigEntry
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
        user_input={CONF_USB_PATH: TEST_USB2_PATH},
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_USB_PATH: TEST_USB2_PATH}


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
        user_input={CONF_USB_PATH: "null"},
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

    with pytest.raises(InvalidData):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USB_PATH: None},
        )

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
    mock_usb_stick: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    result = await _start_reconfigure_flow(hass, mock_config_entry, TEST_USB2_PATH)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data.get(CONF_USB_PATH) == TEST_USB2_PATH



async def test_reconfigure_flow_same_path(
    hass: HomeAssistant,
    mock_usb_stick: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    result = await _start_reconfigure_flow(hass, mock_config_entry, TEST_USB_PATH)

    assert result["type"] is FlowResultType.FORM
    assert result.get("errors") == {"base": "already_configured"}


async def test_reconfigure_flow_other_stick(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_usb_stick: AsyncMock,
) -> None:
    """Test reconfigure flow aborts on other Smile ID."""
    mock_usb_stick.mac_stick = TEST_MAC2

    result = await _start_reconfigure_flow(hass, mock_config_entry, TEST_USB2_PATH)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_the_same_stick"


@pytest.mark.parametrize(
    ("side_effect", "reason"),[(StickError, "cannot_connect")],
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

    result = await _start_reconfigure_flow(hass, mock_config_entry, TEST_USB2_PATH)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": reason}
    assert result.get("step_id") == "reconfigure"
