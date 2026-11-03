"""Test Wellbeing setup process."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientResponseError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pyelectroluxgroup.token_manager import TokenManager
from pytest_homeassistant_custom_component.common import MockConfigEntry
from yarl import URL

from custom_components.wellbeing import (
    WellbeingDataUpdateCoordinator,
    WellbeingHubAPI,
    WellBeingTokenManager,
)
from custom_components.wellbeing.api import Appliances, WellbeingApiClient
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
        patch("custom_components.wellbeing.WellbeingHubAPI") as mock_hub_class,
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


@pytest.mark.parametrize("error", [None, UpdateFailed, ConfigEntryAuthFailed])
async def test_state_forbidden_recovery(hass, monkeypatch, error):
    """Recover from a rejected state read while preserving genuine reauth."""
    monkeypatch.setattr(TokenManager, "is_token_valid", lambda self: True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "access_token": "old-access",
            "refresh_token": "old-refresh",
        },
    )
    entry.add_to_hass(hass)
    hub = WellbeingHubAPI(Mock(), WellBeingTokenManager(hass, entry))
    client = WellbeingApiClient(hub)
    coordinator = WellbeingDataUpdateCoordinator(
        hass, client, timedelta(seconds=60), entry
    )

    state_forbidden = ClientResponseError(
        Mock(
            real_url=URL(f"{hub.auth.host}/appliances/purifier/state"),
            headers={"Authorization": "Bearer old-access"},
        ),
        (),
        status=403,
    )
    response = Mock(
        json=AsyncMock(
            return_value={"accessToken": "new-access", "refreshToken": "new-refresh"}
        )
    )
    if error is ConfigEntryAuthFailed:
        response.raise_for_status.side_effect = ClientResponseError(
            Mock(real_url=URL(f"{hub.auth.host}/token/refresh")), (), status=403
        )
    polls = (
        [state_forbidden, Appliances({})] if error is None else [state_forbidden] * 3
    )
    with (
        patch.object(hub.auth, "request", return_value=response) as request,
        patch.object(client, "async_get_appliances", side_effect=polls),
    ):
        if error is None:
            assert (await coordinator._async_update_data())[
                "appliances"
            ].appliances == {}
        else:
            with pytest.raises(error):
                await coordinator._async_update_data()
            if error is UpdateFailed:
                with pytest.raises(UpdateFailed):
                    await coordinator._async_update_data()

    request.assert_awaited_once_with(
        "post",
        "token/refresh",
        json={"refreshToken": "old-refresh"},
        skip_auth_headers=True,
    )
    assert entry.data["refresh_token"] == (
        "old-refresh" if error is ConfigEntryAuthFailed else "new-refresh"
    )
