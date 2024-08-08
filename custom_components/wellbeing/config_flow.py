"""Adds config flow for Wellbeing."""
from typing import Mapping, Any

import voluptuous as vol
import logging

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession, async_get_clientsession
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.token_manager import TokenManager

from . import CONF_REFRESH_TOKEN
from .api import WellbeingApiClient
from .const import CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .const import CONF_USERNAME
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)

class WellbeingFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for wellbeing."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
            else:
                self._errors["base"] = "auth"

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_validate()

    async def async_step_reauth_validate(self, user_input=None):
        """Handle reauth and validation."""
        errors = {}
        if user_input is not None:
            return await self._test_credentials(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )

        return self.async_show_form(
            step_id="reauth_validate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                CONF_USERNAME: user_input[CONF_USERNAME],
            },
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
            errors=self._errors,
        )

    async def _test_credentials(self, access_token: str, refresh_token: str, api_key: str):
        """Return true if credentials is valid."""
        try:
            token_manager = WellBeingConfigFlowTokenManager(access_token, refresh_token, api_key)
            client = ElectroluxHubAPI(
                session=async_get_clientsession(self.hass),
                token_manager=token_manager
            )
            return await client.async_get_appliances()
        except Exception:  # pylint: disable=broad-except
            pass
        return False

class WellBeingConfigFlowTokenManager(TokenManager):
    """TokenManager implementation for config flow """
    def __init__(self, access_token: str, refresh_token: str, api_key: str):
        super().__init__(access_token, refresh_token, api_key)

    def update(self, access_token: str, refresh_token: str, api_key: str | None = None):
        pass


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
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): cv.positive_int,
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_USERNAME), data=self.options
        )
