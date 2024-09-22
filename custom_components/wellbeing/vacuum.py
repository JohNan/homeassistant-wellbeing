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
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import WellbeingDataUpdateCoordinator
from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

SUPPORTED_FEATURES = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.BATTERY
)

VACUUM_STATES = {
    1: STATE_CLEANING,
    2: STATE_PAUSED,
    5: STATE_RETURNING,
    10: STATE_IDLE,
}

BATTERY_LEVELS = {
    0: 0,
    1: 10,
    2: 30,
    3: 50,
    4: 70,
    5: 90,
    6: 100,
}

BATTERY_ICONS = {
    0: "mdi:battery-alert-variant-outline",
    1: "mdi:battery-10",
    2: "mdi:battery-30",
    3: "mdi:battery-50",
    4: "mdi:battery-70",
    5: "mdi:battery-90",
    6: "mdi:battery",
}


FAN_SPEEDS = {
    1: "Quiet",
    2: "Smart",
    3: "Power",
}


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

    @property
    def supported_features(self) -> int:
        return SUPPORTED_FEATURES

    @property
    def state(self):
        """Return the state of the vacuum."""
        return VACUUM_STATES.get(self.get_entity.state, STATE_ERROR)

    @property
    def battery_level(self):
        """Return the battery level of the vacuum based on the status from 0-6."""
        return BATTERY_LEVELS.get(self.get_appliance.battery_status, 0)

    @property
    def battery_icon(self):
        """Return the battery icon of the vacuum based on the status from 0-6."""
        return BATTERY_ICONS.get(self.get_appliance.battery_status, "mdi:battery-unknown")

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return FAN_SPEEDS.get(self.get_appliance.power_mode, "Unknown")

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(FAN_SPEEDS.values())

    async def async_start(self):
        await self.api.command_vacuum(self.pnc_id, "play")

    async def async_stop(self):
        await self.api.command_vacuum(self.pnc_id, "stop")

    async def async_pause(self):
        await self.api.command_vacuum(self.pnc_id, "pause")

    async def async_return_to_base(self):
        await self.api.command_vacuum(self.pnc_id, "home")

    async def async_set_fan_speed(self, fan_speed: str):
        """Set the fan speed of the vacuum cleaner."""
        for mode, name in FAN_SPEEDS.items():
            if name == fan_speed:
                await self.api.set_vacuum_power_mode(self.pnc_id, mode)
                break
