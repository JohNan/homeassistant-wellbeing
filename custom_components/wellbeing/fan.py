"""Sensor platform for Wellbeing."""
from homeassistant.components.fan import FanEntity, SUPPORT_SET_SPEED
from homeassistant.util.percentage import ranged_value_to_percentage, int_states_in_range
from .const import DEFAULT_NAME, FAN
from .const import DOMAIN
from .const import ICON
from .const import SENSOR
from .entity import WellbeingEntity

SUPPORTED_FEATURES = SUPPORT_SET_SPEED
SPEED_RANGE = (1, 10)


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

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.get_entity.name

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def percentage(self):
        """Return the current speed percentage."""
        return ranged_value_to_percentage(SPEED_RANGE, self.get_entity.state)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES
