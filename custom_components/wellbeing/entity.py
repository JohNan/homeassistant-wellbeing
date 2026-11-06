"""WellbeingEntity class"""

import asyncio

from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import WellbeingDataUpdateCoordinator
from .api import Appliance, ApplianceEntity
from .const import DEFAULT_NAME, DOMAIN


class WellbeingEntity(CoordinatorEntity):
    def __init__(
        self,
        coordinator: WellbeingDataUpdateCoordinator,
        config_entry,
        pnc_id,
        entity_type,
        entity_attr,
    ):
        super().__init__(coordinator)
        self.api = coordinator.api
        self.entity_attr = entity_attr
        self.entity_type = entity_type
        self.config_entry = config_entry
        self.pnc_id = pnc_id
        expected_domain = self.__class__.__module__.split(".")[-1]
        self.entity_id = f"{expected_domain}.{slugify(f'{DEFAULT_NAME}_{self.get_appliance.display_name}_{self.entity_attr}')}"

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
        appliance = self.get_appliance
        model_name = getattr(appliance, "model_name", None)
        return {
            "identifiers": {(DOMAIN, self.pnc_id)},
            "name": appliance.display_name,
            "model": model_name or appliance.model,
            "model_id": appliance.model.value,
            "manufacturer": appliance.brand,
            "sw_version": appliance.firmware,
        }

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "integration": DOMAIN,
            "capabilities": [
                key
                for key, value in self.get_appliance.capabilities.items()
                if isinstance(value, dict) and value.get("access") == "readwrite"
            ],
        }

    # The cloud takes a few seconds to report a command back; keep the local
    # state in sync meanwhile and fetch the real state afterwards.
    REFRESH_DELAY = 15

    def set_optimistic_state(self, entity_type, entity_attr, value) -> None:
        """Update a sibling entity's state locally until the next refresh."""
        entity = self.get_appliance.get_entity_or_none(entity_type, entity_attr)
        if entity is not None:
            entity._state = value
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_refresh_later(self, delay: float | None = None) -> None:
        """Request a coordinator refresh once the appliance has caught up."""
        await asyncio.sleep(self.REFRESH_DELAY if delay is None else delay)
        await self.coordinator.async_request_refresh()

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self.get_entity.device_class

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category."""
        return self.get_entity.entity_category
