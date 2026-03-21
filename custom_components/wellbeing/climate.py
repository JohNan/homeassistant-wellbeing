"""Climate platform for Wellbeing."""

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from homeassistant.const import UnitOfTemperature, Platform, ATTR_TEMPERATURE

from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

HVAC_MODES = {
    "auto": HVACMode.HEAT_COOL,
    "cool": HVACMode.COOL,
    "dry": HVACMode.DRY,
    "fanonly": HVACMode.FAN_ONLY,
}

FAN_MODES = {
    "auto": FAN_AUTO,
    "low": FAN_LOW,
    "middle": FAN_MEDIUM,
    "high": FAN_HIGH,
}

# Inverse mappings
TO_ELECTROLUX_HVAC = {v: k for k, v in HVAC_MODES.items()}
TO_ELECTROLUX_FAN = {v: k for k, v in FAN_MODES.items()}
# Special case for FAN_MEDIUM to "middle"
TO_ELECTROLUX_FAN[FAN_MEDIUM] = "middle"


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup climate platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingClimate(
                        coordinator, entry, pnc_id, entity.entity_type, entity.attr
                    )
                    for entity in appliance.entities
                    if entity.entity_type == Platform.CLIMATE
                ]
            )


class WellbeingClimate(WellbeingEntity, ClimateEntity):
    """Wellbeing Climate class."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = 16.0
    _attr_max_temp = 32.0
    _attr_fan_modes = list(FAN_MODES.values())
    _attr_swing_modes = ["on", "off"]
    _attr_hvac_modes = list(HVAC_MODES.values()) + [HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current hvac mode."""
        if (
            self.get_appliance.get_entity(
                Platform.BINARY_SENSOR, "applianceState"
            ).state
            is False
        ):
            return HVACMode.OFF
        return HVAC_MODES.get(self.get_entity.state, HVACMode.AUTO)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self.hvac_mode == HVACMode.COOL:
            return HVACAction.COOLING
        if self.hvac_mode == HVACMode.DRY:
            return HVACAction.DRYING
        if self.hvac_mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        if self.hvac_mode == HVACMode.HEAT_COOL:
            if self.get_appliance.get_entity(
                Platform.BINARY_SENSOR, "compressorState"
            ).state:
                return HVACAction.COOLING
            return HVACAction.IDLE
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.get_appliance.get_entity(
            Platform.SENSOR, "ambientTemperatureC"
        ).state

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.get_appliance.get_entity(
            Platform.SENSOR, "targetTemperatureC"
        ).state

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        fan_setting = self.get_appliance.get_entity(
            Platform.SENSOR, "fanSpeedSetting"
        ).state
        if fan_setting is None:
            return None
        return FAN_MODES.get(fan_setting.lower())

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return (
            "on"
            if self.get_appliance.get_entity(
                Platform.BINARY_SENSOR, "verticalSwing"
            ).state
            else "off"
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.api.ac_turn_off(self.pnc_id)
        else:
            if self.hvac_mode == HVACMode.OFF:
                await self.api.ac_turn_on(self.pnc_id)
            electrolux_mode = TO_ELECTROLUX_HVAC.get(hvac_mode)
            if electrolux_mode:
                await self.api.ac_set_mode(self.pnc_id, electrolux_mode)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.api.ac_set_temperature(self.pnc_id, temp)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        electrolux_fan = TO_ELECTROLUX_FAN.get(fan_mode)
        if electrolux_fan:
            await self.api.ac_set_fan_mode(self.pnc_id, electrolux_fan.upper())
        await self.coordinator.async_request_refresh()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        await self.api.ac_set_vertical_swing(self.pnc_id, swing_mode.upper())
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.api.ac_turn_on(self.pnc_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.api.ac_turn_off(self.pnc_id)
        await self.coordinator.async_request_refresh()
