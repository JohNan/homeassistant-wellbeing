"""Sensor platform for Wellbeing."""

import asyncio
import logging
import math

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import Platform
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

from . import WellbeingDataUpdateCoordinator
from .api import WorkMode
from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

SUPPORTED_FEATURES = (
    FanEntityFeature.SET_SPEED
    | FanEntityFeature.PRESET_MODE
    | FanEntityFeature.TURN_OFF
    | FanEntityFeature.TURN_ON
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingFan(coordinator, entry, pnc_id, entity.entity_type, entity.attr)
                    for entity in appliance.entities
                    if entity.entity_type == Platform.FAN
                ]
            )


class WellbeingFan(WellbeingEntity, FanEntity):
    """wellbeing Sensor class."""
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: WellbeingDataUpdateCoordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator, config_entry, pnc_id, entity_type, entity_attr)
        self._preset_mode = self.get_appliance.mode
        self._speed = self.get_entity.state

    @property
    def _speed_range(self) -> tuple[int, int]:
        return self.get_appliance.speed_range

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_range[1]

    @property
    def percentage(self):
        """Return the current speed percentage."""
        if self._preset_mode == WorkMode.OFF:
            speed = 0
        else:
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

        is_manual = self.preset_mode == WorkMode.MANUAL
        # make sure manual is set before setting speed
        if not is_manual:
            await self.async_set_preset_mode(WorkMode.MANUAL)

        await self.api.set_fan_speed(self.pnc_id, self._speed)

        self.async_write_ha_state()
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., auto, smart, interval, favorite."""
        return (
            self._preset_mode.value
            if self.get_appliance.mode.value is WorkMode.UNDEFINED.value
            else self.get_appliance.mode.value
        )

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return self.get_appliance.preset_modes

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._valid_preset_mode_or_raise(preset_mode)
        self._preset_mode = WorkMode(preset_mode)

        self.get_appliance.set_mode(self._preset_mode)
        self.async_write_ha_state()
        await self.api.set_work_mode(self.pnc_id, self._preset_mode)
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self):
        return self.preset_mode != WorkMode.OFF

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs) -> None:
        self._preset_mode = self.get_appliance.work_mode_from_preset_mode(preset_mode)

        # Handle incorrect percentage
        if percentage is not None and isinstance(percentage, str):
            try:
                percentage = int(percentage)
            except ValueError:
                _LOGGER.error(f"Invalid percentage value: {percentage}")
                return

        # Proceed with the provided or default percentage
        self._speed = math.floor(percentage_to_ranged_value(self._speed_range, percentage or 10))
        self.get_appliance.set_mode(self._preset_mode)
        self.async_write_ha_state()

        await self.api.set_work_mode(self.pnc_id, self._preset_mode)
        
        if self._preset_mode != WorkMode.AUTO:
            await self.api.set_fan_speed(self.pnc_id, self._speed)
        
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        self._preset_mode = WorkMode.OFF
        self._speed = 0
        self.get_appliance.set_mode(self._preset_mode)
        self.async_write_ha_state()

        await self.api.set_work_mode(self.pnc_id, WorkMode.OFF)
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()
