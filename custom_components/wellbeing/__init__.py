"""
Custom integration to integrate Wellbeing with Home Assistant.

For more details about this integration, please refer to
https://github.com/JohNan/homeassistant-wellbeing
"""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_ACCESS_TOKEN
from homeassistant.core import Config
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.hass_dict import HassKey
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.token_manager import TokenManager

from .api import WellbeingApiClient
from .const import CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, CONF_REFRESH_TOKEN
from .const import CONF_USERNAME
from .const import DOMAIN
from .const import PLATFORMS

_LOGGER: logging.Logger = logging.getLogger(__package__)


# noinspection PyUnusedLocal
async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True


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
        hub = ElectroluxHubAPI(
            session=async_get_clientsession(hass),
            token_manager=token_manager
        )
    except Exception:
        raise ConfigEntryAuthFailed

    client = WellbeingApiClient(hub)

    coordinator = WellbeingDataUpdateCoordinator(hass, client=client, update_interval=update_interval)

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    coordinator.platforms.extend(PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.add_update_listener(async_reload_entry)
    return True


class WellbeingDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: WellbeingApiClient, update_interval: timedelta) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)


    async def _async_update_data(self):
        """Update data via library."""
        try:
            appliances = await self.api.async_get_appliances()
            return {
                "appliances": appliances
            }
        except Exception as exception:
            raise UpdateFailed() from exception


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)

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

        self._hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                CONF_REFRESH_TOKEN: refresh_token,
                CONF_ACCESS_TOKEN: access_token
            },
        )
