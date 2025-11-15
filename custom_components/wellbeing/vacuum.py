"""Vacuum platform for Wellbeing."""

import logging

from homeassistant.components.vacuum import StateVacuumEntity, VacuumActivity, VacuumEntityFeature
from homeassistant.const import Platform
from homeassistant.util.percentage import ranged_value_to_percentage

from . import WellbeingDataUpdateCoordinator
from .const import DOMAIN
from .entity import WellbeingEntity
from typing import Any

_LOGGER: logging.Logger = logging.getLogger(__package__)

SUPPORTED_FEATURES = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.SEND_COMMAND
)

VACUUM_ACTIVITIES = {
    1: VacuumActivity.CLEANING,  # Regular Cleaning
    2: VacuumActivity.PAUSED,
    3: VacuumActivity.CLEANING,  # Stop cleaning
    4: VacuumActivity.PAUSED,  # Pause Spot cleaning
    5: VacuumActivity.RETURNING,
    6: VacuumActivity.PAUSED,  # Paused returning
    7: VacuumActivity.RETURNING,  # Returning for pitstop
    8: VacuumActivity.PAUSED,  # Paused returning for pitstop
    9: VacuumActivity.DOCKED,  # Charging
    10: VacuumActivity.IDLE,
    11: VacuumActivity.ERROR,
    12: VacuumActivity.DOCKED,  # Pitstop
    13: VacuumActivity.IDLE,  # Manual stearing
    14: VacuumActivity.IDLE,  # Firmware upgrading
    "idle": VacuumActivity.IDLE,  # robot700series idle
    "inProgress": VacuumActivity.CLEANING,  # robot700series cleaning
    "goingHome": VacuumActivity.RETURNING,  # robot700series returning
    "paused": VacuumActivity.PAUSED,  # robot700series paused
    "sleeping": VacuumActivity.DOCKED,  # robot700series sleeping
}

VACUUM_CHARGING_STATES = [9, "idle"]


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup vacuum platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingVacuum(coordinator, entry, pnc_id, entity.entity_type, entity.attr)
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
        self.entity_model = self.get_appliance.model

    @property
    def _battery_range(self) -> tuple[int, int]:
        return self.get_appliance.battery_range

    @property
    def supported_features(self) -> int:
        return SUPPORTED_FEATURES

    @property
    def activity(self):
        """Return the current vacuum activity."""
        return VACUUM_ACTIVITIES.get(self.get_entity.state, VacuumActivity.ERROR)

    @property
    def battery_level(self):
        """Return the battery level of the vacuum."""
        return ranged_value_to_percentage(self._battery_range, self.get_appliance.battery_status)

    @property
    def battery_icon(self):
        """Return the battery icon of the vacuum based on the battery level."""
        level = self.battery_level

        charging = self.get_entity.state in VACUUM_CHARGING_STATES

        level = 10 * round(level / 10)  # Round level to nearest 10 for icon selection

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
        """Return the current fan speed of the vacuum."""
        return self.get_appliance.vacuum_fan_speed

    @property
    def fan_speed_list(self):
        """Return the list of available fan speeds."""
        return self.get_appliance.vacuum_fan_speed_list

    async def async_start(self):
        """Start the vacuum cleaner."""
        await self.api.vacuum_start(self.pnc_id)

    async def async_stop(self):
        """Stop the vacuum cleaner."""
        await self.api.vacuum_stop(self.pnc_id)

    async def async_pause(self):
        """Pause the vacuum cleaner."""
        await self.api.vacuum_pause(self.pnc_id)

    async def async_return_to_base(self):
        """Return the vacuum cleaner to its base."""
        await self.api.vacuum_return_to_base(self.pnc_id)

    async def async_set_fan_speed(self, fan_speed: str) -> None:
        """Set the fan speed of the vacuum cleaner."""
        await self.api.vacuum_set_fan_speed(self.pnc_id, self.get_appliance, fan_speed)
        self.async_write_ha_state()  # Optimistically update the state before the next coordinator refresh

    async def async_send_command(self, command: str, params: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Send a custom command to the vacuum cleaner."""
        await self.api.vacuum_send_command(self.pnc_id, command, params)
