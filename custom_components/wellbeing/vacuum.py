"""Vacuum platform for Wellbeing."""

import asyncio
import logging
import math

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_PAUSED,
    STATE_RETURNING,
    STATE_IDLE,
    STATE_DOCKED,
    STATE_ERROR,
)
from homeassistant.const import Platform
from homeassistant.util.percentage import ranged_value_to_percentage

from . import WellbeingDataUpdateCoordinator
from .const import DOMAIN
from .entity import WellbeingEntity
from .api import Model

_LOGGER: logging.Logger = logging.getLogger(__package__)

SUPPORTED_FEATURES = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.BATTERY
)

VACUUM_STATES = {
    1: STATE_CLEANING,  # Regular Cleaning
    2: STATE_PAUSED,
    3: STATE_CLEANING,  # Stop cleaning
    4: STATE_PAUSED,  # Pause Spot cleaning
    5: STATE_RETURNING,
    6: STATE_PAUSED,  # Paused returning
    7: STATE_RETURNING,  # Returning for pitstop
    8: STATE_PAUSED,  # Paused returning for pitstop
    9: STATE_DOCKED,  # Charging
    10: STATE_IDLE,
    11: STATE_ERROR,
    12: STATE_DOCKED,  # Pitstop
    13: STATE_IDLE,  # Manual stearing
    14: STATE_IDLE,  # Firmware upgrading
    "idle": STATE_IDLE,            # robot700series idle
    "inProgress": STATE_CLEANING,  # robot700series cleaning
    "goingHome": STATE_RETURNING,  # robot700series returning
    "paused": STATE_PAUSED,        # robot700series paused
    "sleeping": STATE_DOCKED,      # robot700series sleeping
}

VACUUM_CHARGING_STATES = [9, 'idle']


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup vacuum platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingVacuum(
                        coordinator, entry, pnc_id, entity.entity_type, entity.attr
                    )
                    for entity in appliance.entities
                    if entity.entity_type == Platform.VACUUM
                ]
            )


class WellbeingVacuum(WellbeingEntity, StateVacuumEntity):
    """wellbeing Sensor class."""

    def __init__(
        self,
        coordinator: WellbeingDataUpdateCoordinator,
        config_entry,
        pnc_id,
        entity_type,
        entity_attr,
    ):
        super().__init__(coordinator, config_entry, pnc_id, entity_type, entity_attr)
        self._fan_speeds = self.get_appliance.vacuum_fan_speeds
        self.entity_model = self.get_appliance.model

    @property
    def _battery_range(self) -> tuple[int, int]:
        return self.get_appliance.battery_range

    @property
    def supported_features(self) -> int:
        return SUPPORTED_FEATURES

    @property
    def state(self):
        """Return the state of the vacuum."""
        return VACUUM_STATES.get(self.get_entity.state, STATE_ERROR)

    @property
    def battery_level(self):
        """Return the battery level of the vacuum."""
        return ranged_value_to_percentage(self._battery_range, self.get_appliance.battery_status)

    @property
    def battery_icon(self):
        """Return the battery icon of the vacuum based on the battery level."""
        level = self.battery_level

        charging = self.get_entity.state in VACUUM_CHARGING_STATES

        level = 10*round(level / 10) # Round level to nearest 10 for icon selection

        # Special cases given available icons
        if level == 100 and charging:
            return "mdi:battery-charging-100"
        if level == 100 and not charging:
            return "mdi:battery"
        if level == 0 and charging:
            return "mdi:battery-charging-outline"
        if level == 0 and not charging:
            return "mdi:battery-alert-variant-outline"
        # General case
        if level > 0 and level < 100:
            return "mdi:battery-" + ("charging-" if charging else "") + f"{level}"
        else:
            return "mdi:battery-unknown"

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self._fan_speeds.get(self.get_appliance.power_mode, "Unknown")

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(self._fan_speeds.values())

    async def async_start(self):
        command=""
        match self.entity_model:
            case Model.PUREi9.value:
                command="play"
            case Model.Robot700series.value:
                command="startGlobalClean"
        await self.api.command_vacuum(self.pnc_id, command)

    async def async_stop(self):
        command=""
        match self.entity_model:
            case Model.PUREi9.value:
                command="stop"
            case Model.Robot700series.value:
                command="stopClean"
        await self.api.command_vacuum(self.pnc_id, command)

    async def async_pause(self):
        command=""
        match self.entity_model:
            case Model.PUREi9.value:
                command="pause"
            case Model.Robot700series.value:
                command="pauseClean"
        await self.api.command_vacuum(self.pnc_id, command)

    async def async_return_to_base(self):
        command=""
        match self.entity_model:
            case Model.PUREi9.value:
                command="home"
            case Model.Robot700series.value:
                command="startGoToCharger"
        await self.api.command_vacuum(self.pnc_id, command)

    async def async_set_fan_speed(self, fan_speed: str):
        """Set the fan speed of the vacuum cleaner."""
        for mode, name in FAN_SPEEDS.items():
            if name == fan_speed:
                await self.api.set_vacuum_power_mode(self.pnc_id, mode)
                break
