"""
Custom integration to integrate Wellbeing with Home Assistant.

For more details about this integration, please refer to
https://github.com/JohNan/homeassistant-wellbeing
"""

import logging
from datetime import timedelta

from aiohttp import ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.token_manager import TokenManager

from .api import WellbeingApiClient
from .const import (
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_STREAM,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STREAM,
    DOMAIN,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)
AUTH_ERROR_STATUSES = {401, 403}
PLATFORMS = [
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.FAN,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    if entry.options.get(CONF_SCAN_INTERVAL):
        base_interval = entry.options[CONF_SCAN_INTERVAL]
    else:
        base_interval = DEFAULT_SCAN_INTERVAL

    # With the live stream enabled, polling is the slow path for full-state
    # refreshes - but the stream does not carry every property (e.g. the
    # vacuum map data only arrives via polling), so while a vacuum is active
    # the coordinator polls at the base interval to follow the cleaning session.
    use_stream = entry.options.get(CONF_STREAM, DEFAULT_STREAM)
    if use_stream:
        update_interval = timedelta(seconds=base_interval * 5)
    else:
        update_interval = timedelta(seconds=base_interval)
    active_update_interval = timedelta(seconds=base_interval)

    token_manager = WellBeingTokenManager(hass, entry)
    try:
        hub = ElectroluxHubAPI(
            session=async_get_clientsession(hass), token_manager=token_manager
        )
    except Exception as exception:
        raise ConfigEntryAuthFailed("Failed to setup API") from exception

    client = WellbeingApiClient(hub)

    coordinator = WellbeingDataUpdateCoordinator(
        hass,
        client=client,
        update_interval=update_interval,
        config_entry=entry,
        active_update_interval=active_update_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    if use_stream:
        entry.async_create_background_task(
            hass, coordinator._listen_for_changes(), "wellbeing_stream"
        )

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady from coordinator.last_exception

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class WellbeingDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WellbeingApiClient,
        update_interval: timedelta,
        config_entry: ConfigEntry,
        active_update_interval: timedelta | None = None,
    ) -> None:
        """Initialize."""
        self.api = client
        self._idle_update_interval = update_interval
        self._active_update_interval = active_update_interval or update_interval
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            config_entry=config_entry,
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            appliances = await self.api.async_get_appliances()
            self.update_interval = (
                self._active_update_interval
                if self._has_active_vacuum(appliances)
                else self._idle_update_interval
            )
            return {"appliances": appliances}
        except Exception as exception:
            if _is_authentication_error(exception):
                raise ConfigEntryAuthFailed from exception
            raise UpdateFailed(exception) from exception

    @staticmethod
    def _has_active_vacuum(appliances) -> bool:
        """Whether any robot vacuum is currently on a cleaning session."""
        from homeassistant.components.vacuum import VacuumActivity

        from .vacuum import (
            VACUUM_ACTIVITIES,
        )  # local import, vacuum.py imports this module

        active = {
            VacuumActivity.CLEANING,
            VacuumActivity.RETURNING,
            VacuumActivity.PAUSED,
        }
        return any(
            VACUUM_ACTIVITIES.get(entity.state) in active
            for appliance in appliances.appliances.values()
            for entity in appliance.entities
            if entity.entity_type == Platform.VACUUM
        )

    async def _listen_for_changes(self):
        """Listen to live stream for changes."""
        async for event in self.api._hub.watch_appliances():
            appliance_id = event.get("applianceId")
            property_name = event.get("property")
            value = event.get("value")

            if not appliance_id or not property_name:
                continue

            if self.api.update_appliance_state(
                self.data["appliances"], appliance_id, property_name, value
            ):
                # Notify entities without async_set_updated_data: that would
                # reset the polling schedule, and a steady trickle of stream
                # events (e.g. battery updates) would then postpone polling
                # indefinitely, freezing all properties that only arrive via
                # polling (such as the vacuum map data).
                self.async_update_listeners()


class WellBeingTokenManager(TokenManager):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self._hass = hass
        self._entry = entry
        api_key = entry.data.get(CONF_API_KEY)
        refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
        access_token = entry.data.get(CONF_ACCESS_TOKEN)
        super().__init__(access_token, refresh_token, api_key)

    def update(self, access_token: str, refresh_token: str, api_key: str | None = None):
        super().update(access_token, refresh_token, api_key)
        _LOGGER.debug("Tokens updated")
        _LOGGER.debug(f"Api key: {self._mask_access_token(self.api_key)}")
        _LOGGER.debug(f"Access token: {self._mask_access_token(access_token)}")
        _LOGGER.debug(f"Refresh token: {self._mask_access_token(refresh_token)}")

        data = {
            **self._entry.data,
            CONF_API_KEY: self.api_key,
            CONF_REFRESH_TOKEN: refresh_token,
            CONF_ACCESS_TOKEN: access_token,
        }
        if data != self._entry.data:
            self._hass.config_entries.async_update_entry(self._entry, data=data)

    @staticmethod
    def _mask_access_token(token: str):
        if len(token) == 1:
            return "*"
        elif len(token) < 4:
            return token[:2] + "*" * (len(token) - 2)
        elif len(token) < 10:
            return token[:2] + "*****" + token[-2:]
        else:
            return token[:5] + "*****" + token[-5:]


def _is_authentication_error(exception: BaseException) -> bool:
    """Return whether an exception chain contains an HTTP auth failure."""
    seen: set[int] = set()
    current: BaseException | None = exception

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if (
            isinstance(current, ClientResponseError)
            and current.status in AUTH_ERROR_STATUSES
        ):
            return True
        current = current.__cause__ or current.__context__

    return False
