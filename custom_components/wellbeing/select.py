"""Select platform for Wellbeing."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import Platform

from .api import ApplianceSelect
from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingSelect(
                        coordinator, entry, pnc_id, entity.entity_type, entity.attr
                    )
                    for entity in appliance.entities
                    if entity.entity_type == Platform.SELECT
                    # Only expose a select when the API lets us write the property.
                    and appliance.has_capability(entity.attr)
                ]
            )


class WellbeingSelect(WellbeingEntity, SelectEntity):
    """Select for string properties such as LouverSwing or PMLeadingMode."""

    @property
    def options(self) -> list[str]:
        entity = self.get_entity
        defaults = entity.options if isinstance(entity, ApplianceSelect) else []
        options = self.get_appliance.capability_values(self.entity_attr, defaults)
        current = self.current_option
        if current is not None and current not in options:
            options = [*options, current]
        return options

    @property
    def current_option(self) -> str | None:
        state = self.get_entity.state
        return None if state is None else str(state)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.api.set_property(self.pnc_id, self.entity_attr, option)
        self.set_optimistic_state(Platform.SELECT, self.entity_attr, option)
        self.set_optimistic_state(Platform.SENSOR, self.entity_attr, option)
        await self.async_refresh_later()
