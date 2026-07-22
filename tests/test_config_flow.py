"""Tests for the config flow of the Wellbeing integration."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wellbeing.const import DOMAIN


@pytest.mark.asyncio
async def test_flow_user(hass):
    """Test user step in config flow."""
    # Step 1: user initiates flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Step 2: user submits invalid credentials
    with patch("custom_components.wellbeing.config_flow.ElectroluxHubAPI") as mock_hub:
        mock_instance = AsyncMock()
        mock_instance.async_get_appliances.side_effect = Exception("Auth failed")
        mock_hub.return_value = mock_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "bad_key",
                "access_token": "bad_token",
                "refresh_token": "bad_refresh",
                "stream": True,
            },
        )
        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["errors"] == {"base": "auth"}

    # Step 3: user submits valid credentials
    with patch("custom_components.wellbeing.config_flow.ElectroluxHubAPI") as mock_hub:
        mock_instance = AsyncMock()
        mock_instance.async_get_appliances.return_value = []
        mock_hub.return_value = mock_instance

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "good_key",
                "access_token": "good_token",
                "refresh_token": "good_refresh",
                "stream": True,
            },
        )
        assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Electrolux Wellbeing"
        assert result3["data"] == {
            "api_key": "good_key",
            "access_token": "good_token",
            "refresh_token": "good_refresh",
        }
        assert result3["options"] == {"stream": True}


@pytest.mark.asyncio
async def test_flow_reauth(hass):
    """Test reauth step."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "old_key",
            "access_token": "old_token",
            "refresh_token": "old_refresh",
        },
        entry_id="reauth_entry_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_validate"

    # Failing reauth
    with patch("custom_components.wellbeing.config_flow.ElectroluxHubAPI") as mock_hub:
        mock_instance = AsyncMock()
        mock_instance.async_get_appliances.side_effect = Exception("Auth failed")
        mock_hub.return_value = mock_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "bad_key",
                "access_token": "bad_token",
                "refresh_token": "bad_refresh",
            },
        )
        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["errors"] == {"base": "auth"}

    # Successful reauth
    with patch("custom_components.wellbeing.config_flow.ElectroluxHubAPI") as mock_hub:
        mock_instance = AsyncMock()
        mock_instance.async_get_appliances.return_value = []
        mock_hub.return_value = mock_instance

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "new_key",
                "access_token": "new_token",
                "refresh_token": "new_refresh",
            },
        )
        assert result3["type"] == data_entry_flow.FlowResultType.ABORT
        assert result3["reason"] == "reauth_successful"


@pytest.mark.asyncio
async def test_options_flow(hass):
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test_key",
            "access_token": "test_token",
            "refresh_token": "test_refresh",
        },
        options={"stream": False},
        entry_id="options_entry_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 30,
            "stream": True,
            "map_rotation": 90,
        },
    )
    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "scan_interval": 30,
        "stream": True,
        "map_rotation": 90,
    }
