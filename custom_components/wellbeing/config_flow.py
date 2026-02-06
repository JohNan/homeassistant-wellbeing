"""Adds config flow for Wellbeing."""

import logging
from typing import Mapping, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, ConfigEntry, ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.token_manager import TokenManager

from . import CONF_REFRESH_TOKEN
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, CONFIG_FLOW_TITLE
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)


class WellbeingFlowHandler(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Config flow for wellbeing."""

    entry: ConfigEntry

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._token_manager = WellBeingConfigFlowTokenManager()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}
        _LOGGER.debug(user_input)
        if user_input is not None:
            try:
                await self._test_credentials(
                    user_input[CONF_ACCESS_TOKEN], user_input[CONF_REFRESH_TOKEN], user_input[CONF_API_KEY]
                )

                # Copy the maybe possibly credentials
                user_input[CONF_ACCESS_TOKEN] = self._token_manager.access_token
                user_input[CONF_REFRESH_TOKEN] = self._token_manager.refresh_token
            except Exception as exp:  # pylint: disable=broad-except
                _LOGGER.error("Validating credentials failed - %s", exp)
                self._errors["base"] = "auth"
                return await self._show_config_form(user_input)

            return self.async_create_entry(title=CONFIG_FLOW_TITLE, data=user_input)

        return await self._show_config_form(user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        if entry := self.hass.config_entries.async_get_entry(self.context["entry_id"]):
            self.entry = entry
        return await self.async_step_reauth_validate()

    async def async_step_reauth_validate(self, user_input=None) -> ConfigFlowResult:
        """Handle reauth and validation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_credentials(
                    user_input[CONF_ACCESS_TOKEN], user_input[CONF_REFRESH_TOKEN], user_input[CONF_API_KEY]
                )

                # Copy the maybe possibly credentials
                user_input[CONF_ACCESS_TOKEN] = self._token_manager.access_token
                user_input[CONF_REFRESH_TOKEN] = self._token_manager.refresh_token
            except Exception as exp:  # pylint: disable=broad-except
                _LOGGER.error("Validating credentials failed - %s", exp)

            return self.async_update_reload_and_abort(
                self.entry,
                data={**user_input},
            )

        return self.async_show_form(
            step_id="reauth_validate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY, default=self.entry.data.get(CONF_API_KEY, "")): str,
                    vol.Required(CONF_ACCESS_TOKEN, default=self.entry.data.get(CONF_ACCESS_TOKEN, "")): str,
                    vol.Required(CONF_REFRESH_TOKEN, default=self.entry.data.get(CONF_REFRESH_TOKEN, "")): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WellbeingOptionsFlowHandler(config_entry)

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Required(CONF_REFRESH_TOKEN): str,
                }
            ),
            description_placeholders={
                "docs_url": "https://github.com/JohNan/homeassistant-wellbeing"
            },
            errors=self._errors,
        )

    async def _test_credentials(self, access_token: str, refresh_token: str, api_key: str):
        """Return true if credentials is valid."""

        self._token_manager.update(access_token, refresh_token, api_key)
        client = ElectroluxHubAPI(session=async_get_clientsession(self.hass), token_manager=self._token_manager)
        await client.async_get_appliances()


class WellBeingConfigFlowTokenManager(TokenManager):
    """TokenManager implementation for config flow"""

    def __init__(self):
        pass

    def update(self, access_token: str, refresh_token: str, api_key: str | None = None):
        super().update(access_token, refresh_token, api_key)


class WellbeingOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for wellbeing."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): cv.positive_int,
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title=CONFIG_FLOW_TITLE, data=self.options)
