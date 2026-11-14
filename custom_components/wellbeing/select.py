"""Select platform for Wellbeing."""

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.const import Platform

from .api import ApplianceSelect, Model
from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

VACUUM_MAP_MODELS = (
    Model.PUREi9,
    Model.Robot700series,
    Model.VacuumHygienic700,
    Model.Cybele,
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            devices: list[SelectEntity] = [
                WellbeingSelect(
                    coordinator, entry, pnc_id, entity.entity_type, entity.attr
                )
                for entity in appliance.entities
                if entity.entity_type == Platform.SELECT
                # Only expose a select when the API lets us write the property.
                and appliance.has_capability(entity.attr)
            ]
            if appliance.model in VACUUM_MAP_MODELS:
                devices.append(WellbeingMapSelect(coordinator, entry, pnc_id))
            async_add_devices(devices)


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


class WellbeingMapSelect(WellbeingEntity, SelectEntity):
    """Select entity for choosing the active map of a vacuum cleaner."""

    _attr_icon = "mdi:map-legend"
    _attr_translation_key = "active_map"

    def __init__(
        self,
        coordinator,
        config_entry,
        pnc_id: str,
    ) -> None:
        """Initialize the map select entity."""
        super().__init__(
            coordinator,
            config_entry,
            pnc_id,
            Platform.SELECT,
            "active_map",
        )
        self._options: list[str] = []

    @property
    def name(self) -> str:
        """Return the entity name."""
        return "Active Map"

    @property
    def device_class(self) -> str | None:
        """Return the device class."""
        return None

    @property
    def entity_category(self) -> None:
        """Return the entity category."""
        return None

    @property
    def get_entity(self):
        """Return None as this entity is dynamic and not backed by an ApplianceEntity."""
        return None

    @property
    def options(self) -> list[str]:
        """Return the available map names."""
        return self._options

    @property
    def current_option(self) -> str | None:
        """Return the current selected map."""
        selected = self.api.vacuum_get_selected_map(self.pnc_id)
        if selected in self._options:
            return selected
        return self._options[0] if self._options else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        attrs = super().extra_state_attributes or {}
        attrs["available_maps"] = self._options
        return attrs

    async def async_added_to_hass(self) -> None:
        """Fetch available maps when entity is added to hass."""
        await super().async_added_to_hass()
        await self._async_update_options()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        if self.hass is not None:
            self.hass.async_create_task(self._async_update_options())
        super()._handle_coordinator_update()

    async def _async_update_options(self) -> None:
        """Update available map options from API."""
        try:
            maps = await self.api.vacuum_get_maps(self.pnc_id)
        except Exception:
            _LOGGER.exception(
                "Failed to fetch available maps for vacuum with id %s", self.pnc_id
            )
            return

        if maps != self._options:
            self._options = maps
            if maps and not self.api.vacuum_get_selected_map(self.pnc_id):
                self.api.vacuum_set_selected_map(self.pnc_id, maps[0])
            if self.hass is not None:
                self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected map."""
        if option in self._options:
            self.api.vacuum_set_selected_map(self.pnc_id, option)
            if self.hass is not None:
                self.async_write_ha_state()
