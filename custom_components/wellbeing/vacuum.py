"""Vacuum platform for Wellbeing."""

import logging
from typing import Any

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.const import Platform

from . import WellbeingDataUpdateCoordinator
from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

SUPPORTED_FEATURES = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.SEND_COMMAND
    | VacuumEntityFeature.CLEAN_AREA
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
    "vacuuming": VacuumActivity.CLEANING,  # Cybele vacuuming
    "mopping": VacuumActivity.CLEANING,  # Cybele mopping
    "vaccumAndMopping": VacuumActivity.CLEANING,  # Cybele combined cleaning
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

    _attr_translation_key = "vacuum"

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
    def supported_features(self) -> int:
        return SUPPORTED_FEATURES

    @property
    def activity(self):
        """Return the current vacuum activity."""
        return VACUUM_ACTIVITIES.get(self.get_entity.state, VacuumActivity.ERROR)

    @property
    def fan_speed(self):
        """Return the current fan speed of the vacuum."""
        return self.get_appliance.vacuum_fan_speed

    @property
    def fan_speed_list(self):
        """Return the list of available fan speeds."""
        return self.get_appliance.vacuum_fan_speed_list

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return map and zone attributes for automations and dashboards."""
        base = super().extra_state_attributes or {}
        maps = (
            self.api._interactive_maps.get(self.pnc_id, [])
            if hasattr(self.api, "_interactive_maps")
            else []
        )
        selected_name = (
            self.api.vacuum_get_selected_map(self.pnc_id)
            if hasattr(self.api, "vacuum_get_selected_map")
            else None
        )
        selected_map = (
            next(
                (m for m in maps if getattr(m, "name", None) == selected_name),
                None,
            )
            if selected_name
            else None
        )
        if selected_map is None and maps:
            selected_map = maps[0]

        zones = getattr(selected_map, "zones", []) if selected_map else []
        available_zones = [
            getattr(z, "name", None)
            for z in (zones or [])
            if getattr(z, "type", "clean") == "clean" and getattr(z, "name", None)
        ]
        avoid_zones = [
            getattr(z, "name", None)
            for z in (zones or [])
            if getattr(z, "type", "") == "avoid" and getattr(z, "name", None)
        ]
        return {
            **base,
            "active_map": getattr(selected_map, "name", None) if selected_map else None,
            "active_map_id": getattr(selected_map, "id", None)
            if selected_map
            else None,
            "available_maps": [
                getattr(m, "name", None) for m in maps if getattr(m, "name", None)
            ],
            "available_zones": available_zones,
            "avoid_zones": avoid_zones,
        }

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

    async def async_get_segments(self) -> list[Segment]:
        """Get the segments that can be cleaned."""
        return await self.api.vacuum_get_segments(self.pnc_id)

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Perform an area clean."""
        await self.api.vacuum_clean_segments(self.pnc_id, segment_ids)

    async def async_send_command(
        self, command: str, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        """Send a custom command to the vacuum cleaner."""
        await self.api.vacuum_send_command(self.pnc_id, command, params)
