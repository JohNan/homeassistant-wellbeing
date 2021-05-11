"""WellbeingEntity class"""
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .api import Appliance, ApplianceEntity

from .const import ATTRIBUTION, DEFAULT_NAME
from .const import DOMAIN
from .const import NAME
from .const import VERSION


class WellbeingEntity(CoordinatorEntity):
    def __init__(self, coordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator)
        self.entity_attr = entity_attr
        self.entity_type = entity_type
        self.config_entry = config_entry
        self.pnc_id = pnc_id
        self.entity_id = ENTITY_ID_FORMAT.format(f"{DEFAULT_NAME}_{self.entity_attr}")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.get_entity.name

    @property
    def get_entity(self) -> ApplianceEntity:
        return self.get_appliance.get_entity(self.entity_type, self.entity_attr)

    @property
    def get_appliance(self) -> Appliance:
        return self.coordinator.data['appliances'].get_appliance(self.pnc_id)

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self.config_entry.entry_id}-{self.entity_attr}-{self.pnc_id}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.pnc_id)},
            "name": self.get_appliance.name,
            "model": self.get_appliance.model,
            "manufacturer": self.get_appliance.brand,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "id": str(self.pnc_id),
            "integration": DOMAIN,
        }

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return self.get_entity.device_class
