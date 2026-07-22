"""Test Wellbeing setup process."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wellbeing.api import Appliances
from custom_components.wellbeing.const import DOMAIN


@pytest.mark.asyncio
async def test_setup_unload_entry(hass):
    """Test entry setup and unload."""
    # Create a mock entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test_api_key",
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        },
        options={
            "stream": False,
        },
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    # Mock the API client and update coordinator requests
    with (
        patch("custom_components.wellbeing.ElectroluxHubAPI") as mock_hub_class,
        patch(
            "custom_components.wellbeing.WellbeingApiClient.async_get_appliances"
        ) as mock_get_appliances,
    ):
        mock_hub = AsyncMock()
        mock_hub_class.return_value = mock_hub

        # Return a mock Appliances instance with empty dict
        mock_get_appliances.return_value = Appliances(appliances={})

        # Perform setup using standard HA config entry loading
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]
        assert entry.state is ConfigEntryState.LOADED

        # Perform unload
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.entry_id not in hass.data[DOMAIN]
        assert entry.state is ConfigEntryState.NOT_LOADED
