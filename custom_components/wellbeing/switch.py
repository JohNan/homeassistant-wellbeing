"""Switch platform for Wellbeing."""
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .entity import WellbeingEntity

async def async_setup_entry(hass, entry, async_add_devices):
    """Setup switch platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get('appliances', None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            # Assuming that the appliance supports these features
            async_add_devices([
                WellbeingSwitch(coordinator, entry, pnc_id, "Ionizer"),
                WellbeingSwitch(coordinator, entry, pnc_id, "UILight"),
                WellbeingSwitch(coordinator, entry, pnc_id, "SafetyLock"),
            ])

class WellbeingSwitch(WellbeingEntity, SwitchEntity):
    """Wellbeing Switch class."""

    def __init__(self, coordinator, config_entry, pnc_id, function):
        super().__init__(coordinator, config_entry, pnc_id, "binary_sensor", function)
        self._function = function
        self._is_on = self.get_entity.state

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.coordinator.api.set_feature_state(self.pnc_id, self._function, True)
        self._is_on = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.coordinator.api.set_feature_state(self.pnc_id, self._function, False)
        self._is_on = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
