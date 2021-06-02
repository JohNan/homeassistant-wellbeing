"""Sensor platform for Wellbeing."""
import math

import logging

from typing import Any

import asyncio

from homeassistant.components.fan import FanEntity, SUPPORT_SET_SPEED, SUPPORT_PRESET_MODE
from homeassistant.util.percentage import percentage_to_ordered_list_item, \
    percentage_to_ranged_value, ordered_list_item_to_percentage, ranged_value_to_percentage
from . import WellbeingDataUpdateCoordinator
from .api import Mode
from .const import DEFAULT_NAME, FAN
from .const import DOMAIN
from .const import ICON
from .const import SENSOR
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

SUPPORTED_FEATURES = SUPPORT_SET_SPEED | SUPPORT_PRESET_MODE

PRESET_MODES = [
    Mode.OFF,
    Mode.AUTO,
    Mode.MANUAL
]

async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get('appliances', None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingFan(coordinator, entry, pnc_id, entity.entity_type, entity.attr)
                    for entity in appliance.entities if entity.entity_type == FAN
                ]
            )

class WellbeingFan(WellbeingEntity, FanEntity):
    """wellbeing Sensor class."""

    def __init__(self, coordinator: WellbeingDataUpdateCoordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator, config_entry, pnc_id, entity_type, entity_attr)
        self._preset_mode = str(self.get_appliance.mode)
        self._speed = self.get_entity.state

    @property
    def _speed_range(self):
        return self.get_appliance.speed_range

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.get_entity.name

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(self.speed_list)
    
    @property
    def percentage(self):
        """Return the current speed percentage."""
        speed = self._speed if self.get_entity.state is None else self.get_entity.state
        percentage = ranged_value_to_percentage(self._speed_range, speed)
        _LOGGER.debug(f"percentage - speed: {speed} percentage: {percentage}")
        return percentage

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        self._speed = math.floor(percentage_to_ranged_value(self._speed_range, percentage))
        self.get_entity.clear_state()
        self.async_write_ha_state()

        _LOGGER.debug(f"async_set_percentage - speed: {self._speed} percentage: {percentage}")

        if percentage == 0:
            await self.async_turn_off()
            return

        is_manual = self.preset_mode is Mode.MANUAL
        # make sure manual is set before setting speed
        if not is_manual:
            await self.async_set_preset_mode(Mode.MANUAL)

        await self.api.set_fan_speed(self.pnc_id, self._speed)

        if is_manual:
            await asyncio.sleep(10)
            await self.coordinator.async_request_refresh()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., auto, smart, interval, favorite."""
        return self._preset_mode if self.get_appliance.mode is Mode.UNDEFINED else self.get_appliance.mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return PRESET_MODES

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._valid_preset_mode_or_raise(preset_mode)
        self._preset_mode = Mode(preset_mode)
        self.get_appliance.clear_mode()
        self.async_write_ha_state()
        await self.api.set_work_mode(self.pnc_id, self._preset_mode)
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self):
        return self.preset_mode is not Mode.OFF

    async def async_turn_on(self, speed: str = None, percentage: int = None,
                            preset_mode: str = None, **kwargs) -> None:
        self._preset_mode = Mode(preset_mode or Mode.AUTO.value)
        self._speed = percentage_to_ranged_value(self._speed_range, percentage or 10)
        self.get_appliance.clear_mode()
        self.get_entity.clear_state()
        self.async_write_ha_state()

        await self.api.set_work_mode(self.pnc_id, self._preset_mode)
        await self.api.set_fan_speed(self.pnc_id, int(percentage_to_ordered_list_item(self._ordered_named_fan_speeds, percentage or 10)))
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        self._preset_mode = Mode.OFF
        self._speed = 0
        self.get_appliance.clear_mode()
        self.get_entity.clear_state()
        self.async_write_ha_state()

        await self.api.set_work_mode(self.pnc_id, Mode.OFF)
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()
