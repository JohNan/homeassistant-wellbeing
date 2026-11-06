"""Humidifier platform for Wellbeing."""

import logging

from homeassistant.components.humidifier import (
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
)
from homeassistant.const import Platform

from .api import WorkMode
from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

HUMIDIFIER_ATTR = "Humidification"
HUMIDITY_TARGET_ATTR = "HumidityTarget"
HUMIDITY_DEFAULT_RANGE = (30, 70, 5)


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup humidifier platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingHumidifier(
                        coordinator, entry, pnc_id, entity.entity_type, entity.attr
                    )
                    for entity in appliance.entities
                    if entity.entity_type == Platform.HUMIDIFIER
                    # Fuji firmware reports Humidification even on variants
                    # without a humidifier; only expose it when writable.
                    and appliance.has_capability(HUMIDIFIER_ATTR)
                ]
            )


class WellbeingHumidifier(WellbeingEntity, HumidifierEntity):
    """Humidifier function of an air purifier (Humidification + HumidityTarget)."""

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER

    @property
    def _range(self) -> tuple[float, float, float]:
        return self.get_appliance.capability_range(
            HUMIDITY_TARGET_ATTR, *HUMIDITY_DEFAULT_RANGE
        )

    @property
    def min_humidity(self) -> float:
        return self._range[0]

    @property
    def max_humidity(self) -> float:
        return self._range[1]

    @property
    def is_on(self) -> bool:
        entity = self.get_appliance.get_entity_or_none(
            Platform.BINARY_SENSOR, HUMIDIFIER_ATTR
        )
        return bool(entity.state) if entity is not None else False

    @property
    def action(self) -> HumidifierAction | None:
        if self.get_appliance.mode == WorkMode.OFF:
            return HumidifierAction.OFF
        return HumidifierAction.HUMIDIFYING if self.is_on else HumidifierAction.IDLE

    @property
    def target_humidity(self) -> float | None:
        entity = self.get_appliance.get_entity_or_none(
            Platform.SENSOR, HUMIDITY_TARGET_ATTR
        )
        return entity.state if entity is not None else None

    @property
    def current_humidity(self) -> float | None:
        entity = self.get_appliance.get_entity_or_none(Platform.SENSOR, "Humidity")
        return entity.state if entity is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn humidification on."""
        if self.get_appliance.mode == WorkMode.OFF:
            await self.api.set_work_mode(
                self.pnc_id, self.get_appliance.work_mode_from_preset_mode(None)
            )
        await self.api.set_property(self.pnc_id, HUMIDIFIER_ATTR, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn humidification off."""
        await self.api.set_property(self.pnc_id, HUMIDIFIER_ATTR, False)
        await self.coordinator.async_request_refresh()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity."""
        await self.api.set_property(self.pnc_id, HUMIDITY_TARGET_ATTR, int(humidity))
        await self.coordinator.async_request_refresh()
