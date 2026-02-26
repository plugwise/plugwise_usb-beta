"""Setup mocks for the Plugwise USB integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

from plugwise_usb.exceptions import StickError
import pytest

from custom_components.plugwise_usb.const import CONF_USB_PATH, DOMAIN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

STICK_IMPORT_MOCK: Final[str] = "custom_components.plugwise_usb.config_flow.Stick"
TEST_MAC: Final[str] = "01:23:45:67:AB"
TEST_USB_PATH: Final[str] = "/dev/ttyUSB1"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.plugwise_usb.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked v1.2 config entry."""  # pw-beta only
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USB_PATH: TEST_USB_PATH},
        minor_version=1,
        version=1,
        unique_id=TEST_MAC,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Plugwise integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


# @pytest.fixture
# def mock_comport() -> Generator[MagicMock]:
#    """Return a mocked comport."""
#     with patch(
#         "serial.tools.list_ports.comports",
#     ) as port:
#         port = serial.tools.list_ports_common.ListPortInfo(TEST_USBPORT)
#         port.serial_number = "1234"
#         port.manufacturer = "Virtual serial port"
#         port.device = TEST_USBPORT
#         port.description = "Some serial port"
#         yield [port]


@pytest.fixture
def mock_usb_stick() -> Generator[MagicMock]:
    """Return a mocked usb_mock."""

    with patch(STICK_IMPORT_MOCK, autospec=True) as mock_usb:
        usb = mock_usb.return_value

        usb.connect = AsyncMock(return_value=None)
        usb.initialize = AsyncMock(return_value=None)
        usb.disconnect = AsyncMock(return_value=None)
        usb.mac_stick = TEST_MAC

        yield usb


@pytest.fixture
def mock_usb_stick_error() -> Generator[MagicMock]:
    """Return a mocked usb_mock."""

    with patch(STICK_IMPORT_MOCK, autospec=True) as mock_usb:
        usb = mock_usb.return_value

        usb.connect = AsyncMock(side_effect=(StickError))
        usb.initialize = AsyncMock(return_value=None)
        usb.disconnect = AsyncMock(return_value=None)
        usb.mac_stick = TEST_MAC

        yield usb


@pytest.fixture
def mock_usb_stick_init_error() -> Generator[MagicMock]:
    """Return a mocked usb_mock."""

    with patch(STICK_IMPORT_MOCK, autospec=True) as mock_usb:
        usb = mock_usb.return_value

        usb.connect = AsyncMock(return_value=None)
        usb.initialize = AsyncMock(side_effect=(StickError))
        usb.disconnect = AsyncMock(return_value=None)
        usb.mac_stick = TEST_MAC

        yield usb


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the usb integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return
