"""WellbeingEntity class"""

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from . import WellbeingDataUpdateCoordinator
from .api import Appliance, ApplianceEntity

from .const import DEFAULT_NAME
from .const import DOMAIN


class WellbeingEntity(CoordinatorEntity):
    def __init__(self, coordinator: WellbeingDataUpdateCoordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator)
        self.api = coordinator.api
        self.entity_attr = entity_attr
        self.entity_type = entity_type
        self.config_entry = config_entry
        self.pnc_id = pnc_id
        self.entity_id = ENTITY_ID_FORMAT.format(slugify(f"{DEFAULT_NAME}_{self.get_appliance.name}_{self.entity_attr}"))

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.get_entity.name

    @property
    def get_entity(self) -> ApplianceEntity:
        return self.get_appliance.get_entity(self.entity_type, self.entity_attr)

    @property
    def get_appliance(self) -> Appliance:
        return self.coordinator.data["appliances"].get_appliance(self.pnc_id)

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
            "sw_version": self.get_appliance.firmware,
        }

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "integration": DOMAIN,
            "capabilities": [
                key for key, value in self.get_appliance.capabilities.items() if value["access"] == "readwrite"
            ],
        }

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self.get_entity.device_class

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category."""
        return self.get_entity.entity_category
