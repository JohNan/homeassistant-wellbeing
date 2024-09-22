"""
Custom integration to integrate Wellbeing with Home Assistant.

For more details about this integration, please refer to
https://github.com/JohNan/homeassistant-wellbeing
"""

import logging
from datetime import timedelta

from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.token_manager import TokenManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from .api import WellbeingApiClient
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, CONF_REFRESH_TOKEN
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)
PLATFORMS = [
    Platform.SENSOR,
    Platform.FAN,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    if entry.options.get(CONF_SCAN_INTERVAL):
        update_interval = timedelta(seconds=entry.options[CONF_SCAN_INTERVAL])
    else:
        update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

    token_manager = WellBeingTokenManager(hass, entry)
    try:
        hub = ElectroluxHubAPI(session=async_get_clientsession(hass), token_manager=token_manager)
    except Exception as exception:
        raise ConfigEntryAuthFailed("Failed to setup API") from exception

    client = WellbeingApiClient(hub)

    coordinator = WellbeingDataUpdateCoordinator(hass, client=client, update_interval=update_interval)

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady from coordinator.last_exception

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)


class WellbeingDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: WellbeingApiClient, update_interval: timedelta) -> None:
        """Initialize."""
        self.api = client
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            appliances = await self.api.async_get_appliances()
            return {"appliances": appliances}
        except Exception as exception:
            raise UpdateFailed(exception) from exception


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

        self._hass.config_entries.async_update_entry(
            data={CONF_API_KEY: self.api_key, CONF_REFRESH_TOKEN: refresh_token, CONF_ACCESS_TOKEN: access_token},
        )

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
