"""Plugwise USB Number component for HomeAssistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from plugwise_usb.api import NodeEvent, NodeFeature

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, Platform, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NODES, STICK, UNSUB_NODE_LOADED
from .coordinator import PlugwiseUSBConfigEntry, PlugwiseUSBDataUpdateCoordinator
from .entity import PlugwiseUSBEntity, PlugwiseUSBEntityDescription

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(kw_only=True)
class PlugwiseNumberEntityDescription(
    PlugwiseUSBEntityDescription, NumberEntityDescription
):
    """Describes Plugwise Number entity."""

    async_number_fn: str = ""
    async_number_type: str = "int"


NUMBER_TYPES: tuple[PlugwiseNumberEntityDescription, ...] = (
    PlugwiseNumberEntityDescription(
        key="reset_timer",
        translation_key="motion_reset_timer",
        async_number_fn="set_motion_reset_timer",
        node_feature=NodeFeature.MOTION_CONFIG,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_max_value=255,
        native_min_value=1,
	mode="box",
    ),
    PlugwiseNumberEntityDescription(
        key="maintenance_interval",
        translation_key="sed_maintenance_interval",
        async_number_fn="set_maintenance_interval",
        node_feature=NodeFeature.BATTERY,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_max_value=1440,
        native_min_value=5,
    ),
    PlugwiseNumberEntityDescription(
        key="sleep_duration",
        translation_key="sed_sleep_duration",
        async_number_fn="set_sleep_duration",
        node_feature=NodeFeature.BATTERY,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.CONFIG,
        native_max_value=1440,
        native_min_value=60,
    ),
    PlugwiseNumberEntityDescription(
        key="awake_duration",
        translation_key="sed_awake_duration",
        async_number_fn="set_awake_duration",
        node_feature=NodeFeature.BATTERY,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.CONFIG,
        native_max_value=60,
        native_min_value=1,
	mode="box",
    ),
    PlugwiseNumberEntityDescription(
        key="clock_interval",
        translation_key="sed_clock_interval",
        async_number_fn="set_clock_interval",
        node_feature=NodeFeature.BATTERY,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_max_value=65535,
        native_min_value=1,
    ),
    PlugwiseNumberEntityDescription(
        key="humidity_upper_bound",
        translation_key="sense_humidity_upper_bound",
        async_number_fn="set_hysteresis_humidity_upper_bound",
        node_feature=NodeFeature.SENSE_HYSTERESIS,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.HUMIDITY,
        native_max_value=99,
        native_min_value=1,
        native_step=0.1,
        async_number_type="float",
	mode="box",
    ),
    PlugwiseNumberEntityDescription(
        key="humidity_lower_bound",
        translation_key="sense_humidity_lower_bound",
        async_number_fn="set_hysteresis_humidity_lower_bound",
        node_feature=NodeFeature.SENSE_HYSTERESIS,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.HUMIDITY,
        native_max_value=99,
        native_min_value=1,
        native_step=0.1,
        async_number_type="float",
	mode="box",
    ),
    PlugwiseNumberEntityDescription(
        key="temperature_upper_bound",
        translation_key="sense_temperature_upper_bound",
        async_number_fn="set_hysteresis_temperature_upper_bound",
        node_feature=NodeFeature.SENSE_HYSTERESIS,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_max_value=60,
        native_min_value=1,
        native_step=0.1,
        async_number_type="float",
	mode="box",
    ),
    PlugwiseNumberEntityDescription(
        key="temperature_lower_bound",
        translation_key="sense_temperature_lower_bound",
        async_number_fn="set_hysteresis_temperature_lower_bound",
        node_feature=NodeFeature.SENSE_HYSTERESIS,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_max_value=60,
        native_min_value=1,
        native_step=0.1,
        async_number_type="float",
	mode="box",
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the USB Number from a config entry."""

    async def async_add_number(node_event: NodeEvent, mac: str) -> None:
        """Initialize DUC for number."""
        if node_event != NodeEvent.LOADED:
            return
        entities: list[PlugwiseUSBEntity] = []
        if (node_duc := config_entry.runtime_data[NODES].get(mac)) is not None:
            for entity_description in NUMBER_TYPES:
                if entity_description.node_feature not in node_duc.node.features:
                    continue
                entities.append(PlugwiseUSBNumberEntity(node_duc, entity_description))
                _LOGGER.debug(
                    "Add %s number for node %s",
                    entity_description.translation_key,
                    node_duc.node.name,
                )
        if entities:
            async_add_entities(entities)

    api_stick = config_entry.runtime_data[STICK]

    # Listen for loaded nodes
    config_entry.runtime_data[Platform.NUMBER] = {}
    config_entry.runtime_data[Platform.NUMBER][UNSUB_NODE_LOADED] = (
        api_stick.subscribe_to_node_events(
            async_add_number,
            (NodeEvent.LOADED,),
        )
    )

    # load any current nodes
    for mac, node in api_stick.nodes.items():
        if node.is_loaded:
            await async_add_number(NodeEvent.LOADED, mac)
        else:
            _LOGGER.debug("Adding number(s) for node %s failed, not loaded", mac)

async def async_unload_entry(
    _hass: HomeAssistant,
    config_entry: PlugwiseUSBConfigEntry,
) -> None:
    """Unload a config entry."""
    config_entry.runtime_data[Platform.NUMBER][UNSUB_NODE_LOADED]()


class PlugwiseUSBNumberEntity(PlugwiseUSBEntity, NumberEntity):
    """Representation of a Plugwise USB Data Update Coordinator Number entity."""

    def __init__(
        self,
        node_duc: PlugwiseUSBDataUpdateCoordinator,
        entity_description: PlugwiseNumberEntityDescription,
    ) -> None:
        """Initialize a number entity."""
        super().__init__(node_duc, entity_description)
        self.async_number_fn = getattr(
            node_duc.node, entity_description.async_number_fn
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data.get(self.entity_description.node_feature, None)
        if data is None:
            _LOGGER.debug(
                "No %s number data for %s",
                self.entity_description.node_feature,
                self._node_info.mac,
            )
            return
        self._attr_native_value = getattr(
            self.coordinator.data[self.entity_description.node_feature],
            self.entity_description.key,
        )
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if self.entity_description.async_number_type == "float":
            await self.async_number_fn(float(value))
        else:
            await self.async_number_fn(int(value))
        self.async_write_ha_state()
